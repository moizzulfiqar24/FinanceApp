# DB/database.py
"""
Database bootstrap & connection helpers for the FinanceApp.

Key improvements over the original:
- Enforce SSL by default (adds `sslmode=require` if missing).
- Prefer IPv4 when the runtime can't dial IPv6 by resolving the hostname
  and exporting PGHOSTADDR accordingly (safe no-op if resolution fails).
- Keep the public surface the same: ALLOWED_TYPES / ALLOWED_PAY_METHODS /
  ALLOWED_SUB_TYPES, get_conn(), init_db().
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse
import streamlit as st
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

# Load from .env for local development
load_dotenv()

# -------------------- Public constants (used by pages/queries) --------------------

ALLOWED_TYPES = ("Payroll", "Primary", "Secondary", "Mobile Wallet")
ALLOWED_PAY_METHODS = ("Online", "IBFT", "Cash")
ALLOWED_SUB_TYPES = ("single", "monthly", "yearly", "lifetime")


# ------------------------------ URL & DNS helpers --------------------------------

def _ensure_ssl(dsn: str | None) -> str | None:
    """
    Make sure sslmode=require is present in the DSN. If no DSN is provided, return None.
    """
    if not dsn:
        return None
    # Avoid adding twice
    if "sslmode=" not in dsn:
        sep = "&" if "?" in dsn else "?"
        dsn = f"{dsn}{sep}sslmode=require"
    return dsn


def _prefer_ipv4(dsn: str) -> None:
    """
    Resolve the DB hostname to an IPv4 address and set PGHOSTADDR so libpq uses it.
    This helps in environments where IPv6 egress is blocked.

    Safe no-op if:
      - PGHOSTADDR is already set,
      - the DSN has no hostname,
      - IPv4 resolution fails for any reason.
    """
    try:
        if os.environ.get("PGHOSTADDR"):
            return
        parsed = urlparse(dsn)
        host = parsed.hostname
        if not host:
            return
        # gethostbyname forces A-record (IPv4) resolution
        ipv4 = socket.gethostbyname(host)
        # Do not blindly overwrite if resolution returned the same hostname string
        if ipv4 and ipv4 != host:
            os.environ["PGHOSTADDR"] = ipv4
    except Exception:
        # Best-effort only; silently ignore
        pass


# ------------------------------ Connection helpers --------------------------------

def get_database_url() -> str | None:
    """
    Get DATABASE_URL from Streamlit secrets (cloud) or environment variables (local),
    and ensure it has sslmode=require.
    """
    url = None
    try:
        # Streamlit secrets take precedence when available
        url = st.secrets["DATABASE_URL"]  # type: ignore[index]
    except Exception:
        url = os.getenv("DATABASE_URL")
    return _ensure_ssl(url)


def get_conn() -> psycopg.Connection:
    """
    Return a *new* psycopg connection using a DSN from secrets/env.
    - autocommit=True because we run DDL in init_db().
    - row_factory=dict_row to return dict-like rows.
    - Prefer IPv4 via PGHOSTADDR when possible.
    """
    dsn = get_database_url()
    if not dsn:
        raise RuntimeError("DATABASE_URL not set in secrets or environment variables")

    # Prefer IPv4 in environments where IPv6 egress isn't available.
    _prefer_ipv4(dsn)

    # You can tune more libpq params via DSN query (e.g., connect_timeout=10).
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


# --------------------------------- Schema bootstrap --------------------------------

def init_db() -> None:
    """
    Create enums, tables, and seed data if needed.
    This function is idempotent and safe to call on every app run.
    """
    with get_conn() as conn, conn.cursor() as cur:
        # Enums (idempotent)
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bank_account_type') THEN
                    CREATE TYPE bank_account_type AS ENUM ('Payroll','Primary','Secondary','Mobile Wallet');
                END IF;

                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method') THEN
                    CREATE TYPE payment_method AS ENUM ('Online','IBFT','Cash');
                END IF;

                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_type') THEN
                    CREATE TYPE subscription_type AS ENUM ('single','monthly','yearly','lifetime');
                END IF;
            END $$;
            """
        )

        # Tables
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL UNIQUE,
                type bank_account_type NOT NULL,
                initial_balance NUMERIC
            );
            """
        )

        cur.execute(
            """
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
            """
        )

        # Seed banks (once)
        cur.execute("SELECT COUNT(*) AS c FROM bank_accounts;")
        row = cur.fetchone()
        if row and int(row["c"]) == 0:
            cur.executemany(
                "INSERT INTO bank_accounts (title, type, initial_balance) VALUES (%s,%s,%s)",
                [
                    ("Habib Metro", "Payroll", None),
                    ("Meezan Bank", "Primary", 1000),
                    ("HBL", "Secondary", None),
                ],
            )

        # Subscriptions
        cur.execute(
            """
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
            """
        )

        # Alert log (prevents duplicate sends per period)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_alerts (
                id SERIAL PRIMARY KEY,
                subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
                period_expiry DATE NOT NULL,
                alert_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (subscription_id, period_expiry)
            );
            """
        )
