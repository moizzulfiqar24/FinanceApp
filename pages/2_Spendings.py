import streamlit as st
from datetime import date, datetime
import pandas as pd

from DB.queries import (
    add_spending, list_bank_accounts, get_spendings_month,
    update_spending, delete_spending
)
from DB.database import init_db
from lock_manager import lock_guard

st.set_page_config(page_title="Spendings", page_icon="💸", layout="wide")
lock_guard()
init_db()

# Sidebar navigation
st.sidebar.page_link("main.py", label="📊 Dashboard")
st.sidebar.page_link("pages/1_Bank_Accounts.py", label="🏦 Bank Accounts")
st.sidebar.page_link("pages/2_Spendings.py", label="💸 Spendings")
st.sidebar.page_link("pages/3_Subscriptions.py", label="📬 Subscriptions")

st.title("💸 Spendings")

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

# --- State for month navigation & edit row ---
today = date.today()
if "sp_month" not in st.session_state:
    st.session_state.sp_month = today.month
if "sp_year" not in st.session_state:
    st.session_state.sp_year = today.year
if "edit_spending_id" not in st.session_state:
    st.session_state.edit_spending_id = None

def move_month(delta: int):
    y, m = st.session_state.sp_year, st.session_state.sp_month
    dt = date(y, m, 15)
    new = (dt.replace(day=1) + pd.DateOffset(months=delta)).date()
    st.session_state.sp_year, st.session_state.sp_month = new.year, new.month

# ---------------------- Add Spending ----------------------
st.subheader("Add Spending")

accounts = list_bank_accounts()
account_options = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in accounts.iterrows()}

with st.form("spending_form", clear_on_submit=True):
    col1, col2 = st.columns([2, 2])
    title = col1.text_input("Title", placeholder="Groceries / AWS / Uber etc.")
    category_choice = col2.selectbox("Category", CATEGORIES, index=0)
    category = category_choice if category_choice != "Other" else st.text_input("Custom Category", placeholder="Enter category")

    col3, col4 = st.columns([1, 1])
    amt_usd_str = col3.text_input("Amount - USD (optional)", placeholder="e.g., 5.00")
    amt_pkr = col4.number_input("Amount - PKR (required)", min_value=0.0, step=100.0, value=0.0)

    col5, col6 = st.columns([1, 2])
    dt = col5.date_input("Date", value=today)
    pay_method = col6.radio("Payment Method", ["Online", "IBFT", "Cash"], horizontal=True)

    col7, col8 = st.columns([1, 1])
    in_office_choice = col7.selectbox("In-Office Purchase?", ["No", "Yes"], index=0)
    in_office = (in_office_choice == "Yes")

    # Bank account selection only for Online/IBFT
    bank_acc_id = None
    if pay_method in ("Online", "IBFT"):
        if accounts.empty:
            st.warning("No bank accounts available. Add one on the Bank Accounts page.")
        else:
            bank_label = col8.selectbox("Bank Account Used", list(account_options.keys()))
            bank_acc_id = account_options[bank_label]
    else:
        bank_acc_id = None

    save = st.form_submit_button("Save Spending", use_container_width=True)

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
        bank_account_id=bank_acc_id,
        in_office=in_office,
    )
    st.success("Spending saved.") if not err else st.error(f"Save failed: {err}")
    st.rerun()

st.divider()

# ---------------------- Month View (Current Month + Nav) ----------------------
st.subheader("Entries")

c_left, c_mid, c_right = st.columns([1,2,1])
with c_left:
    if st.button("◀ Previous Month"):
        move_month(-1); st.rerun()
with c_mid:
    st.markdown(f"### {date(st.session_state.sp_year, st.session_state.sp_month, 1):%B %Y}")
with c_right:
    if st.button("Next Month ▶"):
        move_month(+1); st.rerun()

month_df = get_spendings_month(st.session_state.sp_year, st.session_state.sp_month)

if month_df.empty:
    st.info("No entries for this month.")
else:
    # Display table (descending by date already from SQL)
    show = month_df.assign(
        InOffice=month_df["in_office"].map({True:"Yes", False:"No"})
    )[["date","title","category","amount_pkr","amount_usd","payment_method","bank_title","InOffice","id"]]
    show = show.rename(columns={
        "date":"Date","title":"Title","category":"Category","amount_pkr":"PKR","amount_usd":"USD",
        "payment_method":"Method","bank_title":"Bank","id":"ID"
    })

    st.dataframe(show.drop(columns=["ID"]), hide_index=True, use_container_width=True)

    st.markdown("##### Click ✏️ to edit an entry")
    # Simple list with per-row pencil button
    for _, r in show.iterrows():
        colA, colB = st.columns([0.15, 0.85])
        if colA.button("✏️", key=f"edit_{int(r['ID'])}", help="Edit this entry"):
            st.session_state.edit_spending_id = int(r["ID"])
        with colB:
            st.write(f"**{r['Date'].date()}** — {r['Title']} | {r['Category']} | PKR {r['PKR']:,.0f} | {r['Method']} | {r.get('Bank') or '-'} | In-Office: {r['InOffice']}")

# ---------------------- Edit Form ----------------------
if st.session_state.edit_spending_id is not None:
    sid = st.session_state.edit_spending_id
    cur = month_df[month_df["id"] == sid]
    if cur.empty:
        # If selected from another month via session, reload from DB month again or clear
        st.session_state.edit_spending_id = None
        st.rerun()
    row = cur.iloc[0]

    st.markdown("---")
    st.markdown(f"### Edit Entry #{sid}")

    with st.form(f"edit_sp_{sid}"):
        e1, e2 = st.columns([2,2])
        title_e = e1.text_input("Title", value=row["title"])
        category_e = e2.text_input("Category", value=row["category"])

        e3, e4 = st.columns([1,1])
        usd_e = e3.text_input("Amount - USD (optional)", value="" if pd.isna(row["amount_usd"]) else str(row["amount_usd"]))
        pkr_e = e4.number_input("Amount - PKR (required)", min_value=0.0, step=100.0, value=float(row["amount_pkr"]))

        e5, e6 = st.columns([1,2])
        date_e = e5.date_input("Date", value=pd.to_datetime(row["date"]).date())
        method_e = e6.radio("Payment Method", ["Online","IBFT","Cash"], index=["Online","IBFT","Cash"].index(row["payment_method"]), horizontal=True)

        e7, e8 = st.columns([1,1])
        in_office_e = e7.selectbox("In-Office Purchase?", ["No","Yes"], index=1 if bool(row["in_office"]) else 0)

        bank_e_id = None
        if method_e in ("Online","IBFT"):
            banks_df = list_bank_accounts()
            bank_map = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in banks_df.iterrows()}
            default_label = next((k for k,v in bank_map.items() if v == (row["bank_account_id"] or -1)), None)
            bank_label_e = e8.selectbox("Bank Account Used", list(bank_map.keys()) or ["(No Banks)"], index=(list(bank_map.keys()).index(default_label) if default_label in bank_map else 0))
            bank_e_id = bank_map[bank_label_e] if bank_map else None
        else:
            bank_e_id = None

        b1, b2, b3 = st.columns([1,1,2])
        save_btn = b1.form_submit_button("Save changes")
        del_btn = b2.form_submit_button("Delete", type="secondary")

    if save_btn:
        usd_val = None
        if str(usd_e).strip():
            try:
                usd_val = float(usd_e)
            except:
                st.error("Amount - USD must be numeric."); st.stop()
        if float(pkr_e) <= 0:
            st.error("Amount - PKR must be greater than 0."); st.stop()

        err = update_spending(
            sid=sid, title=title_e, category=category_e, amount_pkr=float(pkr_e), amount_usd=usd_val,
            dt=date_e, payment_method=method_e, bank_account_id=bank_e_id, in_office=(in_office_e=="Yes")
        )
        if err:
            st.error(f"Update failed: {err}")
        else:
            st.success("Updated.")
            st.session_state.edit_spending_id = None
        st.rerun()

    if del_btn:
        err = delete_spending(sid)
        if err:
            st.error(f"Delete failed: {err}")
        else:
            st.success("Deleted.")
            st.session_state.edit_spending_id = None
        st.rerun()
