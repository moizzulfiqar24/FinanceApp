import streamlit as st
from datetime import date, timedelta
import pandas as pd

from lock_manager import lock_guard
lock_guard()

from DB.database import init_db
from DB.queries import (
    list_bank_accounts, create_subscription, list_subscriptions_df,
    get_subscription, update_subscription, delete_subscription, run_due_alerts
)

st.set_page_config(page_title="Subscriptions", page_icon="📬", layout="wide")
init_db()

# Sidebar navigation
st.sidebar.page_link("main.py", label="📊 Dashboard")
st.sidebar.page_link("pages/1_Bank_Accounts.py", label="🏦 Bank Accounts")
st.sidebar.page_link("pages/2_Spendings.py", label="💸 Spendings")
st.sidebar.page_link("pages/3_Subscriptions.py", label="📬 Subscriptions")

st.title("📬 Subscriptions")

# Run auto-maintenance & any due alerts each load
run_due_alerts()

# ------- Add form -------
st.subheader("Add Subscription")

accounts = list_bank_accounts()
account_options = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in accounts.iterrows()}

CATEGORIES = [
    "Bills & Utilities", "Food & Dining", "Fuel & Travel", "Productivity",
    "Shopping & Leisure", "Entertainment", "Health & Self Care", "Other",
]
SUB_TYPES = ["single", "monthly", "yearly", "lifetime"]

with st.form("sub_form", clear_on_submit=True):
    c1, c2 = st.columns([2,2])
    title = c1.text_input("Title", placeholder="Netflix / One-time Course / Prime etc.")
    cat_choice = c2.selectbox("Category", CATEGORIES, index=0)
    category = cat_choice if cat_choice != "Other" else st.text_input("Custom Category", placeholder="Enter category")

    c3, c4 = st.columns([1,1])
    amt_usd_str = c3.text_input("Amount - USD (optional)", placeholder="e.g., 5.00")
    amt_pkr = c4.number_input("Amount - PKR (required)", min_value=0.0, step=100.0, value=0.0)

    c5, c6 = st.columns([1,2])
    start_dt = c5.date_input("Start Date", value=date.today())
    pay_method = c6.radio("Payment Method", ["Online", "IBFT", "Cash"], horizontal=True)

    bank_acc_id = None
    if pay_method in ("Online","IBFT"):
        if accounts.empty:
            st.warning("No bank accounts available. Add one on Bank Accounts page.")
        else:
            bank_label = st.selectbox("Bank Account Used", list(account_options.keys()))
            bank_acc_id = account_options[bank_label]
    else:
        bank_acc_id = None  # Cash => NULL

    c7, c8 = st.columns([1,1])
    sub_type = c7.selectbox("Subscription Type", SUB_TYPES, index=0)
    # Expiry always = start + 30 days (per requirement)
    computed_expiry = start_dt + timedelta(days=30)
    expiry_preview = c8.date_input("Expiration / Renewal Date", value=computed_expiry, disabled=True,
                                   help="Auto-set to 30 days from Start Date")

    c9, c10 = st.columns([1,1])
    alert_enabled = c9.selectbox("Alert", ["Yes", "No"], index=0) == "Yes"

    save = st.form_submit_button("Save Subscription")

if save:
    if not title.strip(): st.error("Title is required."); st.stop()
    if not category.strip(): st.error("Category is required."); st.stop()
    if amt_pkr <= 0: st.error("Amount - PKR must be greater than 0."); st.stop()

    amt_usd = None
    if amt_usd_str.strip():
        try: amt_usd = float(amt_usd_str)
        except: st.error("Amount - USD must be a number (e.g., 12.50)."); st.stop()

    err = create_subscription(
        title=title, category=category, amount_pkr=float(amt_pkr), amount_usd=amt_usd,
        start_dt=start_dt, payment_method=pay_method, bank_account_id=bank_acc_id,
        sub_type=sub_type, alert_enabled=alert_enabled
    )
    st.success("Subscription added.") if not err else st.error(f"Save failed: {err}")
    st.rerun()

st.divider()

# ------- List / Edit -------
st.subheader("Manage Subscriptions")
subs = list_subscriptions_df()

if subs.empty:
    st.info("No subscriptions yet.")
    st.stop()

# Table view
pretty = subs[[
    "id","title","category","amount_pkr","amount_usd","start_date","expiry_date",
    "sub_type","payment_method","bank_title","alert_enabled","active","pending_deactivate"
]].rename(columns={
    "amount_pkr":"PKR","amount_usd":"USD","start_date":"Start","expiry_date":"Expiry",
    "sub_type":"Type","payment_method":"Method","bank_title":"Bank","alert_enabled":"Alert",
    "pending_deactivate":"Deactivate at Next Expiry"
})
st.dataframe(pretty, use_container_width=True, hide_index=True)

# Select one to edit/delete
choices = {f"{r['title']} (#{int(r['id'])})": int(r["id"]) for _, r in subs.iterrows()}
choice = st.selectbox("Select a subscription", list(choices.keys()))
sid = choices[choice]
current = subs[subs["id"] == sid].iloc[0]

st.markdown("### Edit Subscription")
with st.form(f"edit_sub_{sid}"):
    e1, e2 = st.columns([2,2])
    title_e = e1.text_input("Title", value=current["title"])
    cat_e = e2.text_input("Category", value=current["category"])

    e3, e4 = st.columns([1,1])
    usd_e = e3.text_input("Amount - USD (optional)", value=str(current["amount_usd"] or ""))
    pkr_e = e4.number_input("Amount - PKR (required)", min_value=0.0, step=100.0, value=float(current["amount_pkr"]))

    e5, e6 = st.columns([1,2])
    start_e = e5.date_input("Start Date", value=pd.to_datetime(current["start_date"]).date())
    method_e = e6.radio("Payment Method", ["Online","IBFT","Cash"], index=["Online","IBFT","Cash"].index(current["payment_method"]), horizontal=True)

    bank_e_id = None
    if method_e in ("Online","IBFT"):
        bank_map = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in list_bank_accounts().iterrows()}
        default_label = next((k for k,v in bank_map.items() if v == (current["bank_account_id"] or -1)), None)
        bank_label_e = st.selectbox("Bank Account Used", list(bank_map.keys()), index=(list(bank_map.keys()).index(default_label) if default_label in bank_map else 0))
        bank_e_id = bank_map[bank_label_e]
    else:
        bank_e_id = None

    e7, e8 = st.columns([1,1])
    type_e = e7.selectbox("Subscription Type", ["single","monthly","yearly","lifetime"], index=["single","monthly","yearly","lifetime"].index(current["sub_type"]))
    expiry_e = e8.date_input("Expiration / Renewal Date", value=pd.to_datetime(current["expiry_date"]).date())

    e9, e10 = st.columns([1,1])
    alert_e = e9.selectbox("Alert", ["Yes","No"], index=0 if current["alert_enabled"] else 1)

    # Active logic: UI reflects "Active now? (Yes/No)"; if No, we set pending_deactivate=True (deactivate at next expiry)
    active_now = bool(current["active"])
    pending_now = bool(current["pending_deactivate"])
    # Derive checkbox default: if pending, treat as No; else reflect active flag
    default_active_ui = (not pending_now) and active_now
    active_ui = e10.selectbox("Active", ["Yes","No"], index=0 if default_active_ui else 1)

    c_btn1, c_btn2, c_btn3 = st.columns([1,1,1])
    save_btn = c_btn1.form_submit_button("Save changes")
    del_btn = c_btn2.form_submit_button("Delete", type="secondary")
    refresh_btn = c_btn3.form_submit_button("Refresh")

if save_btn:
    # validate & coerce
    usd_val = None
    if str(usd_e).strip():
        try: usd_val = float(usd_e)
        except: st.error("Amount - USD must be numeric."); st.stop()
    if float(pkr_e) <= 0: st.error("Amount - PKR must be greater than 0."); st.stop()

    # interpret active field:
    # If user chooses "No" -> mark pending_deactivate=True, keep active True until expiry passes.
    # If user chooses "Yes" -> ensure pending_deactivate=False; keep active as current active (or True).
    active_flag = True  # remain active now
    pending_flag = (active_ui == "No")

    err = update_subscription(
        sid=sid, title=title_e, category=cat_e, amount_pkr=float(pkr_e), amount_usd=usd_val,
        start_dt=start_e, expiry_dt=expiry_e, payment_method=method_e, bank_account_id=bank_e_id,
        sub_type=type_e, alert_enabled=(alert_e=="Yes"),
        active_flag=active_flag, pending_deactivate=pending_flag
    )
    st.success("Updated.") if not err else st.error(f"Update failed: {err}")
    st.rerun()

if del_btn:
    err = delete_subscription(sid)
    st.success("Deleted.") if not err else st.error(f"Delete failed: {err}")
    st.rerun()

if refresh_btn:
    st.rerun()
