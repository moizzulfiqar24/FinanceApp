import os
import socket
import logging
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

# Load .env locally (has no effect on Render; that's fine)
load_dotenv()

# App-wide constants
ALLOWED_TYPES = ("Payroll", "Primary", "Secondary", "Mobile Wallet")
ALLOWED_PAY_METHODS = ("Online", "IBFT", "Cash")
ALLOWED_SUB_TYPES = ("single", "monthly", "yearly", "lifetime")

# Optional lightweight logging so you can see what config path was used
log = logging.getLogger("db")
logging.basicConfig(level=logging.INFO)

def _from_database_url():
    """Parse DATABASE_URL if provided (preferred for Aiven)."""
    dsn = (os.getenv("DATABASE_URL") or "").strip()
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
    """Support separate vars if you prefer not to use a single DATABASE_URL."""
    host = (os.getenv("DB_HOST") or "").strip()
    port = int(os.getenv("DB_PORT") or 5432)
    dbname = (os.getenv("DB_NAME") or "postgres").strip()
    user = (os.getenv("DB_USER") or "postgres").strip()
    password = os.getenv("DB_PASSWORD")
    if host and password:
        return dict(host=host, port=port, dbname=dbname, user=user, password=password)
    return None

def get_conn():
    cfg = _from_database_url() or _from_split_env()
    log.info("DB host seen: %r | via: %s",
             (cfg or {}).get("host"),
             "DATABASE_URL" if _from_database_url() else ("split" if _from_split_env() else "none"))
    if not cfg or not cfg.get("host") or not cfg.get("password"):
        raise RuntimeError("Database config not found. Set DATABASE_URL, or DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD")

    # Force IPv4 (Render egress is IPv4), require SSL
    return psycopg.connect(
        **cfg,
        sslmode="require",
        autocommit=True,
        row_factory=dict_row,
        gai_family=socket.AF_INET,
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
