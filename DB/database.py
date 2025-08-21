import os
import streamlit as st
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

# Load from .env for local development
load_dotenv()

ALLOWED_TYPES = ("Payroll", "Primary", "Secondary", "Mobile Wallet")
ALLOWED_PAY_METHODS = ("Online", "IBFT", "Cash")
ALLOWED_SUB_TYPES = ("single", "monthly", "yearly", "lifetime")

def get_database_url():
    """Get DATABASE_URL from Streamlit secrets (cloud) or environment variables (local)"""
    try:
        return st.secrets["DATABASE_URL"]
    except:
        return os.getenv("DATABASE_URL")

def get_conn():
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL not set in secrets or environment variables")
    return psycopg.connect(database_url, autocommit=True, row_factory=dict_row)

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