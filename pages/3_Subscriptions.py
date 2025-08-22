import streamlit as st
from datetime import date, timedelta
import pandas as pd

from lock_manager import lock_guard
from DB.database import init_db
from DB.queries import (
    list_bank_accounts, create_subscription, list_subscriptions_df,
    update_subscription, delete_subscription, run_due_alerts
)

# ---------- Page & lock ----------
st.set_page_config(page_title="Subscriptions", page_icon="📬", layout="wide")
lock_guard()
init_db()

# ---------- Sidebar ----------
st.sidebar.page_link("main.py", label="📊 Dashboard")
st.sidebar.page_link("pages/1_Bank_Accounts.py", label="🏦 Bank Accounts")
st.sidebar.page_link("pages/2_Spendings.py", label="💸 Spendings")
st.sidebar.page_link("pages/3_Subscriptions.py", label="📬 Subscriptions")

# ---------- Minimal theming ----------
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
      .subhead { font-size: 1.05rem; color: #6b6f76; margin: 0.25rem 0 0.5rem; }
      .card {
          border:1px solid rgba(0,0,0,.08);
          border-radius:12px; padding:1rem; background:#fff;
          box-shadow: 0 1px 2px rgba(0,0,0,.03);
      }
      .card h3 { margin-top:0; margin-bottom:.4rem; }
      .card .desc { color:#6b6f76; margin-bottom: .8rem; }
      .caption { color:#6b6f76; font-size:.92rem; margin: .15rem 0 .5rem; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- Title ----------
st.title("📬 Subscriptions")
st.markdown('<div class="subhead">Track recurring and one‑time subscriptions, with quick edits.</div>', unsafe_allow_html=True)

# Run auto-maintenance & due alerts
run_due_alerts()

# ---------- Helpers ----------
TYPE_LABELS = {
    "single": "Single",
    "monthly": "Monthly",
    "yearly": "Yearly",
    "lifetime": "Lifetime",
}
LABEL_TO_ENUM = {v: k for k, v in TYPE_LABELS.items()}

def yn(val: bool) -> str:
    return "Yes" if bool(val) else "No"

# ---------- Add Subscription (compact card) ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Add Subscription")
    st.markdown('<div class="desc">Capture a new subscription. Expiry previews + alert toggle included.</div>', unsafe_allow_html=True)

    accounts = list_bank_accounts()
    account_options = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in accounts.iterrows()}

    with st.form("sub_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2.2, 1.7, 1.1])
        title = c1.text_input("Title", placeholder="Netflix / One‑time Course / Prime etc.")
        cat_choice = c2.selectbox(
            "Category",
            ["Bills & Utilities","Food & Dining","Fuel & Travel","Productivity",
             "Shopping & Leisure","Entertainment","Health & Self Care","Other"],
            index=0
        )
        sub_type_label = c3.selectbox("Type", ["Single", "Monthly", "Yearly", "Lifetime"], index=0)

        category = cat_choice if cat_choice != "Other" else st.text_input("Custom Category", placeholder="Enter category")

        c4, c5, c6 = st.columns([1,1,1])
        amt_usd_str = c4.text_input("Amount - USD (optional)", placeholder="5.00")
        amt_pkr = c5.number_input("Amount - PKR", min_value=0.0, step=100.0, value=0.0)
        start_dt = c6.date_input("Start Date", value=date.today())

        # computed expiry (preview only)
        computed_expiry = start_dt + timedelta(days=30)
        st.date_input("Expiration / Renewal Date", value=computed_expiry, disabled=True,
                      help="Auto-set to 30 days from Start Date")

        c7, c8 = st.columns([1.4, 2.6])
        pay_method = c7.radio("Payment Method", ["Online", "IBFT", "Cash"], horizontal=True)
        if pay_method in ("Online","IBFT"):
            if accounts.empty:
                st.warning("No bank accounts available. Add one on Bank Accounts page.")
                bank_acc_id = None
            else:
                bank_label = c8.selectbox("Bank Account Used", list(account_options.keys()))
                bank_acc_id = account_options[bank_label]
        else:
            bank_acc_id = None

        c9, _ = st.columns([1,3])
        alert_enabled = c9.selectbox("Alert", ["Yes", "No"], index=0) == "Yes"

        save = st.form_submit_button("Save Subscription", use_container_width=True)

    if save:
        if not title.strip(): st.error("Title is required."); st.stop()
        if not (category or "").strip(): st.error("Category is required."); st.stop()
        if amt_pkr <= 0: st.error("Amount - PKR must be greater than 0."); st.stop()

        amt_usd = None
        if amt_usd_str.strip():
            try: amt_usd = float(amt_usd_str)
            except: st.error("Amount - USD must be a number (e.g., 12.50)."); st.stop()

        err = create_subscription(
            title=title,
            category=category,
            amount_pkr=float(amt_pkr),
            amount_usd=amt_usd,
            start_dt=start_dt,
            payment_method=pay_method,
            bank_account_id=bank_acc_id,
            sub_type=LABEL_TO_ENUM[sub_type_label],   # map back to enum ("single",...)
            alert_enabled=alert_enabled
        )
        st.success("Subscription added.") if not err else st.error(f"Save failed: {err}")
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

st.write("")  # spacer

# ---------- Manage / Table ----------
st.markdown("### Manage Subscriptions")
subs = list_subscriptions_df()

if subs.empty:
    st.info("No subscriptions yet.")
    st.stop()

# Pretty table data
pretty = subs.copy()
pretty["Type"] = pretty["sub_type"].map(TYPE_LABELS).fillna(pretty["sub_type"])
pretty["PKR"] = pretty["amount_pkr"]
pretty["USD"] = pretty["amount_usd"]
pretty["Start"] = pd.to_datetime(pretty["start_date"]).dt.date
pretty["Expiry"] = pd.to_datetime(pretty["expiry_date"]).dt.date
pretty["Method"] = pretty["payment_method"]
pretty["Bank"] = pretty["bank_title"]
pretty["Alert"] = pretty["alert_enabled"].map(yn)
pretty["ActiveNow"] = pretty["active"].map(yn)
pretty["Deactivate at Next Expiry"] = pretty["pending_deactivate"].map(yn)

show_cols = [
    "id","title","category","PKR","USD","Start","Expiry",
    "Type","Method","Bank","Alert","ActiveNow","Deactivate at Next Expiry"
]
pretty = pretty[show_cols].rename(columns={
    "id":"ID", "title":"Title", "category":"Category"
})

# Filters + sort
f1, f2, f3, f4 = st.columns([1.4,1.2,1.2,1.4])
type_filter = f1.selectbox("Type", ["All","Single","Monthly","Yearly","Lifetime"])
alert_filter = f2.selectbox("Alert", ["All","Yes","No"])
active_filter = f3.selectbox("Active", ["All","Yes","No"])
sort_opt = f4.selectbox("Sort by", ["Expiry (nearest)","Amount (high→low)","Amount (low→high)","Start (newest)"], index=0)

filtered = pretty.copy()
if type_filter != "All":
    filtered = filtered[filtered["Type"] == type_filter]
if alert_filter != "All":
    filtered = filtered[filtered["Alert"] == alert_filter]
if active_filter != "All":
    filtered = filtered[filtered["ActiveNow"] == active_filter]

if sort_opt == "Amount (high→low)":
    filtered = filtered.sort_values("PKR", ascending=False)
elif sort_opt == "Amount (low→high)":
    filtered = filtered.sort_values("PKR", ascending=True)
elif sort_opt == "Start (newest)":
    filtered = filtered.sort_values("Start", ascending=False)
else:
    filtered = filtered.sort_values("Expiry", ascending=True)

st.markdown('<div class="caption">Tip: filter by Type/Alert/Active and sort the view the way you like.</div>', unsafe_allow_html=True)
st.dataframe(
    filtered.drop(columns=["ID"]),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Title": st.column_config.TextColumn("Title", width="medium"),
        "Category": st.column_config.TextColumn("Category", width="small"),
        "PKR": st.column_config.NumberColumn("PKR", format="%,.0f"),
        "USD": st.column_config.NumberColumn("USD", format="%.2f"),
        "Start": st.column_config.DateColumn("Start"),
        "Expiry": st.column_config.DateColumn("Expiry"),
        "Type": st.column_config.TextColumn("Type", width="small"),
        "Method": st.column_config.TextColumn("Method", width="small"),
        "Bank": st.column_config.TextColumn("Bank", width="small"),
        "Alert": st.column_config.TextColumn("Alert", width="small"),
        "ActiveNow": st.column_config.TextColumn("Active", width="small"),
        "Deactivate at Next Expiry": st.column_config.TextColumn("Deactivate @ Expiry", width="small"),
    }
)

# ---------- Edit selector ----------
nice_labels = {
    int(r["ID"]): f"{pd.to_datetime(r['Title']).strftime('') if False else ''}{r['Title']} • {r['Type']} • PKR {r['PKR']:,.0f} • Exp {r['Expiry']}"
    for _, r in filtered.iterrows()
}
options = [None] + list(nice_labels.keys())
choose = st.selectbox("Edit subscription", options=options, index=0,
                      format_func=lambda v: "Select a subscription…" if v is None else nice_labels[v])

# ---------- Edit Card ----------
if choose is not None:
    sid = int(choose)
    current = subs[subs["id"] == sid].iloc[0]

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### Edit Subscription #{sid}")
    st.markdown('<div class="desc">Adjust details; deactivate schedules at the next expiry by toggling Active to “No”.</div>', unsafe_allow_html=True)

    with st.form(f"edit_sub_{sid}"):
        e1, e2, e3 = st.columns([2.1, 1.6, 1.0])
        title_e = e1.text_input("Title", value=current["title"])
        cat_e = e2.text_input("Category", value=current["category"])
        type_label_e = e3.selectbox("Type", ["Single","Monthly","Yearly","Lifetime"],
                                    index=["Single","Monthly","Yearly","Lifetime"].index(TYPE_LABELS.get(current["sub_type"], "Single")))

        e4, e5, e6 = st.columns([1,1,1])
        usd_e = e4.text_input("Amount - USD (optional)", value=str(current["amount_usd"] or ""))
        pkr_e = e5.number_input("Amount - PKR", min_value=0.0, step=100.0, value=float(current["amount_pkr"]))
        start_e = e6.date_input("Start Date", value=pd.to_datetime(current["start_date"]).date())

        e7, e8 = st.columns([1,1])
        expiry_e = e7.date_input("Expiration / Renewal Date", value=pd.to_datetime(current["expiry_date"]).date())
        method_e = e8.radio("Payment Method", ["Online","IBFT","Cash"],
                            index=["Online","IBFT","Cash"].index(current["payment_method"]), horizontal=True)

        banks_df = list_bank_accounts()
        if method_e in ("Online","IBFT") and not banks_df.empty:
            bank_map = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in banks_df.iterrows()}
            default_label = next((k for k,v in bank_map.items() if v == (current["bank_account_id"] or -1)), None)
            bank_label_e = st.selectbox("Bank Account Used", list(bank_map.keys()),
                                        index=(list(bank_map.keys()).index(default_label) if default_label in bank_map else 0))
            bank_e_id = bank_map[bank_label_e]
        else:
            bank_e_id = None
            if method_e in ("Online","IBFT"):
                st.warning("No bank accounts available.")

        e9, e10 = st.columns([1,1])
        alert_e = e9.selectbox("Alert", ["Yes","No"], index=0 if current["alert_enabled"] else 1)
        # Active UX: if No -> set pending_deactivate True (deactivates at next expiry)
        active_now = bool(current["active"])
        pending_now = bool(current["pending_deactivate"])
        default_active_ui = (not pending_now) and active_now
        active_ui = e10.selectbox("Active", ["Yes","No"], index=0 if default_active_ui else 1)

        b1, b2, b3 = st.columns([1,1,6])
        save_btn = b1.form_submit_button("Save changes")
        del_btn = b2.form_submit_button("Delete", type="secondary")
        cancel_btn = b3.form_submit_button("Cancel")

    if save_btn:
        usd_val = None
        if str(usd_e).strip():
            try:
                usd_val = float(usd_e)
            except:
                st.error("Amount - USD must be numeric."); st.stop()
        if float(pkr_e) <= 0:
            st.error("Amount - PKR must be greater than 0."); st.stop()

        active_flag = True
        pending_flag = (active_ui == "No")

        err = update_subscription(
            sid=sid, title=title_e, category=cat_e, amount_pkr=float(pkr_e), amount_usd=usd_val,
            start_dt=start_e, expiry_dt=expiry_e, payment_method=method_e, bank_account_id=bank_e_id,
            sub_type=LABEL_TO_ENUM[type_label_e],     # map label -> enum for DB
            alert_enabled=(alert_e=="Yes"),
            active_flag=active_flag, pending_deactivate=pending_flag
        )
        st.success("Updated.") if not err else st.error(f"Update failed: {err}")
        st.rerun()

    if del_btn:
        err = delete_subscription(sid)
        st.success("Deleted.") if not err else st.error(f"Delete failed: {err}")
        st.rerun()

    if cancel_btn:
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
