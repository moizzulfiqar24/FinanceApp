import os
import socket
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
import streamlit as st     

load_dotenv()

ALLOWED_TYPES = ("Payroll", "Primary", "Secondary", "Mobile Wallet")
ALLOWED_PAY_METHODS = ("Online", "IBFT", "Cash")
ALLOWED_SUB_TYPES = ("single", "monthly", "yearly", "lifetime")

def _get_secret(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def _from_database_url():
    dsn = (_get_secret("DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        return None
    u = urlparse(dsn)
    if not (u.scheme and u.hostname):
        return None
    return dict(
        host=u.hostname,
        port=u.port or 5432,
        dbname=(u.path.lstrip("/") or "postgres"),
        user=unquote(u.username) if u.username else "postgres",
        password=unquote(u.password) if u.password else None,
    )

def _from_split_env():
    host = (_get_secret("DB_HOST") or os.getenv("DB_HOST") or "").strip()
    port = int(_get_secret("DB_PORT") or os.getenv("DB_PORT") or 5432)
    dbname = (_get_secret("DB_NAME") or os.getenv("DB_NAME") or "postgres").strip()
    user = (_get_secret("DB_USER") or os.getenv("DB_USER") or "postgres").strip()
    password = _get_secret("DB_PASSWORD") or os.getenv("DB_PASSWORD")
    if host and password:
        return dict(host=host, port=port, dbname=dbname, user=user, password=password)
    return None

def _ipv4_hostaddr(host: str, port: int) -> str | None:
    try:
        infos = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except Exception:
        pass
    return None

def get_conn():
    cfg = _from_database_url() or _from_split_env()
    if not cfg or not cfg.get("host") or not cfg.get("password"):
        raise RuntimeError("Database config not found. Set DATABASE_URL, or DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD")
    hostaddr = _ipv4_hostaddr(cfg["host"], cfg["port"])
    return psycopg.connect(
        host=cfg["host"],
        hostaddr=hostaddr,         # forces IPv4 if available
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        sslmode="require",
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=15,
    )

def init_db():
    with get_conn() as conn, conn.cursor() as cur:
        # Enums
        cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='bank_account_type') THEN
                CREATE TYPE bank_account_type AS ENUM ('Payroll','Primary','Secondary','Mobile Wallet');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='payment_method') THEN
                CREATE TYPE payment_method AS ENUM ('Online','IBFT','Cash');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='subscription_type') THEN
                CREATE TYPE subscription_type AS ENUM ('single','monthly','yearly','lifetime');
            END IF;
        END $$;
        """)

        # Tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL UNIQUE,
            type bank_account_type NOT NULL,
            initial_balance NUMERIC
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS spendings (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount_usd NUMERIC,
            amount_pkr NUMERIC NOT NULL,
            date DATE NOT NULL,
            payment_method payment_method NOT NULL,
            bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL
        );
        """)

        # --- NEW COLUMN: in_office (Yes/No) ---
        cur.execute("""
            ALTER TABLE spendings
            ADD COLUMN IF NOT EXISTS in_office BOOLEAN NOT NULL DEFAULT FALSE;
        """)

        # seed banks
        cur.execute("SELECT COUNT(*) AS c FROM bank_accounts;")
        if cur.fetchone()["c"] == 0:
            cur.executemany(
                "INSERT INTO bank_accounts (title, type, initial_balance) VALUES (%s,%s,%s)",
                [
                    ("Habib Metro", "Payroll", None),
                    ("Meezan Bank", "Primary", 1000),
                    ("HBL", "Secondary", None),
                ],
            )

        # Subscriptions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount_usd NUMERIC,
            amount_pkr NUMERIC NOT NULL,
            start_date DATE NOT NULL,
            expiry_date DATE NOT NULL,
            payment_method payment_method NOT NULL,
            bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL,
            sub_type subscription_type NOT NULL,
            alert_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            pending_deactivate BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """)

        # Alert log (prevents duplicates)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS subscription_alerts (
            id SERIAL PRIMARY KEY,
            subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
            period_expiry DATE NOT NULL,
            alert_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (subscription_id, period_expiry)
        );
        """)
