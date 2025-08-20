from typing import Optional
import pandas as pd
from .database import get_conn, ALLOWED_TYPES, ALLOWED_PAY_METHODS

# ---------- Bank Accounts ----------
def list_bank_accounts() -> pd.DataFrame:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, type::text AS type, COALESCE(initial_balance,0) AS initial_balance "
            "FROM bank_accounts ORDER BY id"
        )
        rows = cur.fetchall()  # list[dict]
    df = pd.DataFrame(rows)
    return df if not df.empty else pd.DataFrame(columns=["id","title","type","initial_balance"])

def create_bank_account(title: str, acc_type: str, initial_balance: Optional[float]) -> Optional[str]:
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

# ---------- Spendings ----------
def add_spending(
    title: str,
    category: str,
    amount_pkr: float,
    amount_usd: Optional[float],
    dt,
    payment_method: str,
    bank_account_id: Optional[int],
) -> Optional[str]:
    if payment_method not in ALLOWED_PAY_METHODS:
        return "Invalid payment method."
    if payment_method in ("Online", "IBFT") and not bank_account_id:
        return "Bank account is required for Online or IBFT payments."
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO spendings (title, category, amount_usd, amount_pkr, date, payment_method, bank_account_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (title.strip(), category.strip(), amount_usd, amount_pkr, dt, payment_method, bank_account_id),
            )
    except Exception as e:
        return str(e)
    return None

def get_spendings_df() -> pd.DataFrame:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.title, s.category, s.amount_usd, s.amount_pkr, s.date,
                   s.payment_method::text AS payment_method, s.bank_account_id, b.title AS bank_title
            FROM spendings s
            LEFT JOIN bank_accounts b ON b.id = s.bank_account_id
            ORDER BY s.date DESC, s.id DESC
            """
        )
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=[
            "id","title","category","amount_usd","amount_pkr","date",
            "payment_method","bank_account_id","bank_title"
        ])
    # ensure proper types
    df["date"] = pd.to_datetime(df["date"])
    return df