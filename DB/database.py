import os
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Enums (UI usage + seed)
ALLOWED_TYPES = ("Payroll", "Primary", "Secondary", "Mobile Wallet")
ALLOWED_PAY_METHODS = ("Online", "IBFT", "Cash")

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in .env")
    # autocommit=True keeps it simple for this app
    return psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)

def init_db():
    """Create enums, tables, and seed initial bank accounts if empty."""
    with get_conn() as conn, conn.cursor() as cur:
        # Create ENUM types if missing
        cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bank_account_type') THEN
                CREATE TYPE bank_account_type AS ENUM ('Payroll','Primary','Secondary','Mobile Wallet');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method') THEN
                CREATE TYPE payment_method AS ENUM ('Online','IBFT','Cash');
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
        # Seed 3 accounts if empty
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
