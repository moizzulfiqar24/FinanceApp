import streamlit as st
from datetime import date
from DB.queries import add_spending, list_bank_accounts
from DB.database import init_db
from lock_manager import lock_guard

st.set_page_config(page_title="Spendings", page_icon="💸", layout="wide")
lock_guard()
init_db()

# Sidebar navigation
st.sidebar.page_link("main.py", label="📊 Dashboard")
st.sidebar.page_link("pages/1_Bank_Accounts.py", label="🏦 Bank Accounts")
st.sidebar.page_link("pages/2_Spendings.py", label="💸 Spendings")

st.title("💸 Add Spending")

# Categories
CATEGORIES = [
    "Bills & Utilities",
    "Food & Dining",
    "Fuel & Travel",
    "Productivity",
    "Shopping & Leisure",
    "Entertainment",
    "Health & Self Care",
    "Other",
]

accounts = list_bank_accounts()
account_options = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in accounts.iterrows()}

with st.form("spending_form", clear_on_submit=True):
    col1, col2 = st.columns([2, 2])
    title = col1.text_input("Title", placeholder="Groceries / AWS / Uber etc.")
    category_choice = col2.selectbox("Category", CATEGORIES, index=0)

    # "Other" -> custom category input
    category = category_choice
    if category_choice == "Other":
        category = st.text_input("Custom Category", placeholder="Enter category")

    col3, col4 = st.columns([1, 1])
    amt_usd_str = col3.text_input("Amount - USD (optional)", placeholder="e.g., 5.00")
    amt_pkr = col4.number_input("Amount - PKR (required)", min_value=0.0, step=100.0, value=0.0)

    col5, col6 = st.columns([1, 2])
    dt = col5.date_input("Date", value=date.today())
    pay_method = col6.radio("Payment Method", ["Online", "IBFT", "Cash"], horizontal=True)

    # Bank account selection only for Online/IBFT
    bank_acc_id = None
    if pay_method in ("Online", "IBFT"):
        if accounts.empty:
            st.warning("No bank accounts available. Add one on the Bank Accounts page.")
        else:
            bank_label = st.selectbox("Bank Account Used", list(account_options.keys()))
            bank_acc_id = account_options[bank_label]
    else:
        # Cash -> explicitly ensure NULL goes to DB
        bank_acc_id = None

    save = st.form_submit_button("Save Spending")

if save:
    if not title.strip():
        st.error("Title is required."); st.stop()
    if not category.strip():
        st.error("Category is required."); st.stop()
    if amt_pkr <= 0:
        st.error("Amount - PKR must be greater than 0."); st.stop()

    amt_usd = None
    if amt_usd_str.strip():
        try:
            amt_usd = float(amt_usd_str)
        except:
            st.error("Amount - USD must be a number (e.g., 12.50)."); st.stop()

    err = add_spending(
        title=title,
        category=category,
        amount_pkr=float(amt_pkr),
        amount_usd=amt_usd,
        dt=dt,
        payment_method=pay_method,
        bank_account_id=bank_acc_id,  # Cash => None (NULL)
    )
    st.success("Spending saved.") if not err else st.error(f"Save failed: {err}")
