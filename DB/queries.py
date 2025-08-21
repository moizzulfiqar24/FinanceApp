from typing import Optional, Dict
import os
import smtplib
from email.message import EmailMessage
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

from .database import get_conn, ALLOWED_TYPES, ALLOWED_PAY_METHODS, ALLOWED_SUB_TYPES

TZ = ZoneInfo("Asia/Karachi")
ALERT_HOUR = 21  # 9 PM PKT
ALERT_RECIPIENT = "moiz.zulfiqar@hotmail.com"
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS")

# ---------------- BANK ACCOUNTS ----------------
def list_bank_accounts() -> pd.DataFrame:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, type::text AS type, COALESCE(initial_balance,0) AS initial_balance "
            "FROM bank_accounts ORDER BY id"
        )
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    return df if not df.empty else pd.DataFrame(columns=["id","title","type","initial_balance"])

def create_bank_account(title: str, acc_type: str, initial_balance: Optional[float]) -> Optional[str]:
    if not title.strip():
        return "Title is required."
    if acc_type not in ALLOWED_TYPES:
        return "Invalid account type."
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bank_accounts (title, type, initial_balance) VALUES (%s,%s,%s)",
                (title.strip(), acc_type, initial_balance),
            )
    except Exception as e:
        return str(e)
    return None

def update_bank_account(acc_id: int, title: str, acc_type: str, initial_balance: Optional[float]) -> Optional[str]:
    if not title.strip():
        return "Title is required."
    if acc_type not in ALLOWED_TYPES:
        return "Invalid account type."
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE bank_accounts SET title=%s, type=%s, initial_balance=%s WHERE id=%s",
                (title.strip(), acc_type, initial_balance, acc_id),
            )
    except Exception as e:
        return str(e)
    return None

def delete_bank_account(acc_id: int) -> Optional[str]:
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM bank_accounts WHERE id=%s", (acc_id,))
    except Exception as e:
        return str(e)
    return None

# ---------------- SPENDINGS ----------------
def add_spending(title:str, category:str, amount_pkr:float, amount_usd:Optional[float],
                 dt:date, payment_method:str, bank_account_id:Optional[int]) -> Optional[str]:
    if payment_method not in ALLOWED_PAY_METHODS: return "Invalid payment method."
    if payment_method in ("Online","IBFT") and not bank_account_id:
        return "Bank account is required for Online or IBFT payments."
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO spendings (title, category, amount_usd, amount_pkr, date, payment_method, bank_account_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (title.strip(), category.strip(), amount_usd, amount_pkr, dt, payment_method, bank_account_id))
    except Exception as e:
        return str(e)
    return None

def get_spendings_df() -> pd.DataFrame:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT s.id, s.title, s.category, s.amount_usd, s.amount_pkr, s.date,
                   s.payment_method::text AS payment_method, s.bank_account_id, b.title AS bank_title
            FROM spendings s
            LEFT JOIN bank_accounts b ON b.id = s.bank_account_id
            ORDER BY s.date DESC, s.id DESC
        """)
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["id","title","category","amount_usd","amount_pkr","date","payment_method","bank_account_id","bank_title"])
    df["date"] = pd.to_datetime(df["date"])
    return df

# ---------------- SUBSCRIPTIONS ----------------
def _roll_expiry_once(old_expiry: date, sub_type: str) -> date:
    if sub_type == "monthly":
        return old_expiry + timedelta(days=30)
    if sub_type == "yearly":
        return old_expiry + timedelta(days=364)
    return old_expiry  # single/lifetime don't roll here

def _maintenance_update_subscriptions():
    today = date.today()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM subscriptions ORDER BY id")
        subs = cur.fetchall()

        for s in subs:
            sid = s["id"]; sub_type = s["sub_type"]; active = s["active"]
            pending = s["pending_deactivate"]; exp = s["expiry_date"]

            if sub_type == "single":
                if active and exp < today:
                    cur.execute("UPDATE subscriptions SET active=FALSE, updated_at=NOW() WHERE id=%s", (sid,))
                    continue

            if sub_type in ("monthly","yearly"):
                if active:
                    if pending and exp < today:
                        cur.execute("UPDATE subscriptions SET active=FALSE, updated_at=NOW() WHERE id=%s", (sid,))
                    else:
                        rolled = False
                        while exp < today and not pending:
                            exp = _roll_expiry_once(exp, sub_type)
                            rolled = True
                        if rolled:
                            cur.execute("UPDATE subscriptions SET expiry_date=%s, updated_at=NOW() WHERE id=%s", (exp, sid))

            if sub_type == "lifetime":
                if active and pending and exp < today:
                    cur.execute("UPDATE subscriptions SET active=FALSE, updated_at=NOW() WHERE id=%s", (sid,))

def create_subscription(
    title:str, category:str, amount_pkr:float, amount_usd:Optional[float],
    start_dt:date, payment_method:str, bank_account_id:Optional[int],
    sub_type:str, alert_enabled:bool
) -> Optional[str]:
    if payment_method not in ALLOWED_PAY_METHODS: return "Invalid payment method."
    if payment_method in ("Online","IBFT") and not bank_account_id:
        return "Bank account is required for Online or IBFT payments."
    if sub_type not in ALLOWED_SUB_TYPES: return "Invalid subscription type."
    expiry = start_dt + timedelta(days=30)  # per requirement
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO subscriptions
                (title, category, amount_usd, amount_pkr, start_date, expiry_date,
                 payment_method, bank_account_id, sub_type, alert_enabled, active, pending_deactivate)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, TRUE, FALSE)
            """, (title.strip(), category.strip(), amount_usd, amount_pkr,
                  start_dt, expiry, payment_method, bank_account_id, sub_type, alert_enabled))
    except Exception as e:
        return str(e)
    return None

def list_subscriptions_df() -> pd.DataFrame:
    _maintenance_update_subscriptions()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT s.*,
                   s.payment_method::text AS payment_method,
                   s.sub_type::text AS sub_type,
                   b.title AS bank_title
            FROM subscriptions s
            LEFT JOIN bank_accounts b ON b.id = s.bank_account_id
            ORDER BY s.id DESC
        """)
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=[
            "id","title","category","amount_usd","amount_pkr","start_date","expiry_date",
            "payment_method","bank_account_id","sub_type","alert_enabled","active","pending_deactivate","bank_title"
        ])
    return df

def get_subscription(sid:int) -> Optional[Dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM subscriptions WHERE id=%s", (sid,))
        row = cur.fetchone()
    return row

def update_subscription(
    sid:int, title:str, category:str, amount_pkr:float, amount_usd:Optional[float],
    start_dt:date, expiry_dt:date, payment_method:str, bank_account_id:Optional[int],
    sub_type:str, alert_enabled:bool, active_flag:bool, pending_deactivate:bool
) -> Optional[str]:
    if payment_method not in ALLOWED_PAY_METHODS: return "Invalid payment method."
    if payment_method in ("Online","IBFT") and not bank_account_id:
        return "Bank account is required for Online or IBFT payments."
    if sub_type not in ALLOWED_SUB_TYPES: return "Invalid subscription type."
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE subscriptions SET
                    title=%s, category=%s, amount_usd=%s, amount_pkr=%s,
                    start_date=%s, expiry_date=%s,
                    payment_method=%s, bank_account_id=%s,
                    sub_type=%s, alert_enabled=%s,
                    active=%s, pending_deactivate=%s,
                    updated_at=NOW()
                WHERE id=%s
            """, (title.strip(), category.strip(), amount_usd, amount_pkr,
                  start_dt, expiry_dt, payment_method, bank_account_id,
                  sub_type, alert_enabled, active_flag, pending_deactivate, sid))
    except Exception as e:
        return str(e)
    return None

def delete_subscription(sid:int) -> Optional[str]:
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM subscriptions WHERE id=%s", (sid,))
    except Exception as e:
        return str(e)
    return None

# ---------------- ALERTS ----------------
def _alert_due_at(expiry: date) -> datetime:
    alert_day = expiry - timedelta(days=2)
    return datetime(alert_day.year, alert_day.month, alert_day.day, ALERT_HOUR, 0, 0, tzinfo=TZ)

def _send_email(subject:str, body:str) -> Optional[str]:
    if not (GMAIL_USER and GMAIL_APP_PASS):
        return "Email not configured"
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = ALERT_RECIPIENT
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASS)
            smtp.send_message(msg)
        return None
    except Exception as e:
        return str(e)

def _is_alert_time() -> bool:
    """Check if current time is exactly 9:00 PM PKT (within 1 hour window)"""
    now = datetime.now(TZ)
    return now.hour == ALERT_HOUR

def run_due_alerts():
    """Send due alerts ONLY at 9:00 PM PKT (idempotent via subscription_alerts uniqueness)."""
    
    # Only check/send alerts if it's the right time
    if not _is_alert_time():
        return
    
    now = datetime.now(TZ)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, category, amount_usd, amount_pkr,
                   sub_type::text AS sub_type, expiry_date, alert_enabled, active
            FROM subscriptions
            WHERE alert_enabled = TRUE
              AND active = TRUE
              AND sub_type IN ('single','monthly','yearly')
        """)
        subs = cur.fetchall()

        for s in subs:
            expiry = s["expiry_date"]
            due_at = _alert_due_at(expiry)
            
            # Only send if we're past the due time AND it's 9 PM
            if now >= due_at:
                cur.execute("""
                    SELECT 1 FROM subscription_alerts
                    WHERE subscription_id=%s AND period_expiry=%s
                """, (s["id"], expiry))
                if cur.fetchone():
                    continue

                if s["sub_type"] == "single":
                    subject = f"[Reminder] {s['title']} ends on {expiry}"
                    body = f"Your subscription '{s['title']}' (category: {s['category']}) ends on {expiry}."
                else:
                    subject = f"[Reminder] {s['title']} renews on {expiry}"
                    body = (
                        f"Title: {s['title']}\n"
                        f"Category: {s['category']}\n"
                        f"Amount PKR: {s['amount_pkr']}\n"
                        f"Amount USD: {s.get('amount_usd')}\n"
                        f"Type: {s['sub_type']}\n"
                        f"Renewal Date: {expiry}\n"
                    )

                err = _send_email(subject, body)
                if err is None:
                    cur.execute("""
                        INSERT INTO subscription_alerts (subscription_id, period_expiry)
                        VALUES (%s,%s) ON CONFLICT DO NOTHING
                    """, (s["id"], expiry))