import streamlit as st
from DB.queries import list_bank_accounts, create_bank_account, update_bank_account, delete_bank_account
from DB.database import ALLOWED_TYPES, init_db
from lock_manager import lock_guard

st.set_page_config(page_title="Bank Accounts", page_icon="🏦", layout="wide")
lock_guard()
init_db()

# Sidebar navigation
st.sidebar.page_link("main.py", label="📊 Dashboard")
st.sidebar.page_link("pages/1_Bank_Accounts.py", label="🏦 Bank Accounts")
st.sidebar.page_link("pages/2_Spendings.py", label="💸 Spendings")
st.sidebar.page_link("pages/3_Subscriptions.py", label="📬 Subscriptions")

st.title("🏦 Bank Accounts")

# List
df = list_bank_accounts()
st.subheader("All Accounts")
if df.empty:
    st.info("No bank accounts yet.")
else:
    st.dataframe(
        df.rename(columns={"id":"ID","title":"Title","type":"Type","initial_balance":"Initial Balance"}),
        hide_index=True, use_container_width=True
    )

st.divider()

# Add
st.subheader("Add Account")
with st.form("add_account_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([2,2,1.5])
    title = col1.text_input("Title", placeholder="Meezan Bank")
    acc_type = col2.selectbox("Type", ALLOWED_TYPES, index=1)
    init_bal_str = col3.text_input("Initial Balance (optional)", placeholder="e.g., 1000")
    submitted = st.form_submit_button("Add")

if submitted:
    init_bal = None
    if init_bal_str.strip():
        try: init_bal = float(init_bal_str)
        except: st.error("Initial Balance must be a number."); st.stop()
    err = create_bank_account(title, acc_type, init_bal)
    st.success("Account added.") if not err else st.error(f"Could not add account: {err}")
    if not err: st.rerun()

st.divider()

# Edit / Delete
st.subheader("Edit / Remove")
df = list_bank_accounts()
if df.empty:
    st.info("Nothing to edit yet.")
    st.stop()

by_title = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in df.iterrows()}
choice = st.selectbox("Select account", list(by_title.keys()))
acc_id = by_title[choice]
current = df[df["id"] == acc_id].iloc[0]

with st.form("edit_account_form"):
    col1, col2, col3 = st.columns([2,2,1.5])
    title = col1.text_input("Title", value=current["title"])
    acc_type = col2.selectbox("Type", ALLOWED_TYPES, index=ALLOWED_TYPES.index(current["type"]))
    init_bal_str = col3.text_input("Initial Balance (optional)", value=str(current["initial_balance"]))
    c1, c2 = st.columns(2)
    save = c1.form_submit_button("Save changes")
    delete = c2.form_submit_button("Delete", type="secondary")

if save:
    init_bal = None
    if init_bal_str.strip():
        try: init_bal = float(init_bal_str)
        except: st.error("Initial Balance must be a number."); st.stop()
    err = update_bank_account(acc_id, title, acc_type, init_bal)
    st.success("Updated.") if not err else st.error(f"Update failed: {err}")
    if not err: st.rerun()

if delete:
    err = delete_bank_account(acc_id)
    st.success("Deleted.") if not err else st.error(f"Delete failed: {err}")
    if not err: st.rerun()
