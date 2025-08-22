import streamlit as st
from datetime import date
import pandas as pd

from DB.queries import (
    add_spending, list_bank_accounts, get_spendings_month,
    update_spending, delete_spending
)
from DB.database import init_db
from lock_manager import lock_guard

# ---------- Page & lock ----------
st.set_page_config(page_title="Spendings", page_icon="💸", layout="wide")
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
      /* Page spacing tweaks */
      .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

      /* Subsection titles */
      .subhead { font-size: 1.05rem; color: #6b6f76; margin: 0.25rem 0 0.5rem; }

      /* Toolbar (month nav) */
      .toolbar {
          display:flex; align-items:center; justify-content:center;
          gap:.5rem; margin:.2rem auto 1rem; padding:.3rem .6rem;
          border:1px solid rgba(0,0,0,.08); border-radius:999px; width: fit-content;
          background: linear-gradient(180deg, rgba(255,255,255,.9), rgba(249,249,249,.9));
          box-shadow: 0 1px 2px rgba(0,0,0,.03);
      }
      .pill {
          border:1px solid rgba(0,0,0,.1); border-radius:999px; padding:.35rem .75rem;
          background:#fff; cursor:pointer; user-select:none;
      }
      .pill:hover { background:#fafafa; }
      .month-label { font-weight:600; letter-spacing:.2px; padding:0 .4rem; }

      /* Card */
      .card {
          border:1px solid rgba(0,0,0,.08);
          border-radius:12px; padding:1rem; background:#fff;
          box-shadow: 0 1px 2px rgba(0,0,0,.03);
      }
      .card h3 { margin-top:0; margin-bottom:.4rem; }
      .card .desc { color:#6b6f76; margin-bottom: .8rem; }

      /* Subtle caption above tables */
      .caption { color:#6b6f76; font-size:.92rem; margin: .15rem 0 .5rem; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- Title ----------
st.title("💸 Spendings")
st.markdown('<div class="subhead">Add, browse, and edit your spendings with a cleaner flow.</div>', unsafe_allow_html=True)

# ---------- State ----------
today = date.today()
if "sp_month" not in st.session_state:
    st.session_state.sp_month = today.month
if "sp_year" not in st.session_state:
    st.session_state.sp_year = today.year
if "edit_target_id" not in st.session_state:
    st.session_state.edit_target_id = None

def move_month(delta: int):
    y, m = st.session_state.sp_year, st.session_state.sp_month
    dt = pd.Timestamp(year=y, month=m, day=15)
    new = (dt + pd.DateOffset(months=delta)).to_pydatetime().date().replace(day=1)
    st.session_state.sp_year, st.session_state.sp_month = new.year, new.month
    st.session_state.edit_target_id = None  # close editor when month changes

# ---------- Add Spending (compact card) ----------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Add Spending")
    st.markdown('<div class="desc">Quickly capture a new expense. Fields arranged for speed.</div>', unsafe_allow_html=True)

    accounts = list_bank_accounts()
    account_options = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in accounts.iterrows()}

    with st.form("spending_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2.2, 1.5, 1.1])
        title = c1.text_input("Title", placeholder="Groceries / AWS / Uber etc.")
        category_choice = c2.selectbox("Category", [
            "Bills & Utilities","Food & Dining","Fuel & Travel","Productivity",
            "Shopping & Leisure","Entertainment","Health & Self Care","Other",
        ], index=0)
        in_office_radio = c3.radio("In-Office?", ["Yes", "No"], index=1, horizontal=True)
        in_office = (in_office_radio == "Yes")

        category = category_choice if category_choice != "Other" else st.text_input("Custom Category", placeholder="Enter category")

        c4, c5, c6 = st.columns([1,1,1])
        amt_usd_str = c4.text_input("Amount - USD (optional)", placeholder="5.00")
        amt_pkr = c5.number_input("Amount - PKR", min_value=0.0, step=100.0, value=0.0)
        dt_val = c6.date_input("Date", value=today)

        c7, c8 = st.columns([1.4, 2.6])
        pay_method = c7.radio("Payment Method", ["Online", "IBFT", "Cash"], horizontal=True)
        if pay_method in ("Online", "IBFT"):
            if accounts.empty:
                st.warning("No bank accounts available. Add one on the Bank Accounts page.")
                bank_acc_id = None
            else:
                bank_label = c8.selectbox("Bank Account Used", list(account_options.keys()))
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
            dt=dt_val,
            payment_method=pay_method,
            bank_account_id=bank_acc_id,
            in_office=in_office,
        )
        st.success("Spending saved.") if not err else st.error(f"Save failed: {err}")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.write("")  # spacer

# ---------- Month Selector Toolbar ----------
col_toolbar = st.container()
with col_toolbar:
    st.markdown(
        f"""
        <div class="toolbar">
            <form action="#" method="get">
              <button class="pill" name="prev" type="submit">◀</button>
            </form>
            <span class="month-label">{date(st.session_state.sp_year, st.session_state.sp_month, 1):%B %Y}</span>
            <form action="#" method="get">
              <button class="pill" name="next" type="submit">▶</button>
            </form>
        </div>
        """,
        unsafe_allow_html=True
    )
    # Wire the buttons to Streamlit actions (the HTML is just for looks).
    cL, _, cR = st.columns([1,8,1])
    with cL:
        if st.button("◀ Previous", key="prev_btn", use_container_width=True):
            move_month(-1); st.rerun()
    with cR:
        if st.button("Next ▶", key="next_btn", use_container_width=True):
            move_month(+1); st.rerun()

# ---------- Entries (table + edit panel) ----------
month_df = get_spendings_month(st.session_state.sp_year, st.session_state.sp_month)

st.markdown("### Entries")
st.markdown('<div class="caption">Showing this month’s spendings in descending date order.</div>', unsafe_allow_html=True)

if month_df.empty:
    st.info("No entries for this month.")
else:
    # Prepare pretty table
    show = month_df.assign(
        InOffice=month_df["in_office"].map({True:"Yes", False:"No"})
    )[["id","date","title","category","amount_pkr","amount_usd","payment_method","bank_title","InOffice"]].copy()
    show.rename(columns={
        "id": "ID", "date":"Date","title":"Title","category":"Category","amount_pkr":"PKR","amount_usd":"USD",
        "payment_method":"Method","bank_title":"Bank"
    }, inplace=True)

    # A small filter/search row
    f1, f2, f3, f4 = st.columns([1.5,1.5,1.2,1.2])
    cat_filter = f1.selectbox("Filter by category", ["All"] + sorted(show["Category"].unique().tolist()))
    method_filter = f2.selectbox("Filter by method", ["All"] + sorted(show["Method"].unique().tolist()))
    office_filter = f3.selectbox("In-Office", ["All", "Yes", "No"])
    sort_opt = f4.selectbox("Sort by", ["Date (newest)", "Amount (high→low)", "Amount (low→high)"], index=0)

    filtered = show.copy()
    if cat_filter != "All":
        filtered = filtered[filtered["Category"] == cat_filter]
    if method_filter != "All":
        filtered = filtered[filtered["Method"] == method_filter]
    if office_filter != "All":
        filtered = filtered[filtered["InOffice"] == office_filter]

    if sort_opt == "Amount (high→low)":
        filtered = filtered.sort_values("PKR", ascending=False)
    elif sort_opt == "Amount (low→high)":
        filtered = filtered.sort_values("PKR", ascending=True)
    else:
        filtered = filtered.sort_values(["Date","ID"], ascending=[False, False])

    # Show table (polished with column_config)
    st.dataframe(
        filtered.drop(columns=["ID"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date"),
            "Title": st.column_config.TextColumn("Title", width="medium"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "PKR": st.column_config.NumberColumn("PKR", format="%,.0f"),
            "USD": st.column_config.NumberColumn("USD", format="%.2f"),
            "Method": st.column_config.TextColumn("Method", width="small"),
            "Bank": st.column_config.TextColumn("Bank", width="small"),
            "InOffice": st.column_config.TextColumn("In‑Office", width="small"),
        }
    )

    # --- Edit panel trigger (clean, no per-row buttons) ---
    # user picks an entry to edit from a compact selector
    nice_labels = {
        int(r["ID"]): f"{pd.to_datetime(r['Date']).date():%d %b} • {r['Title']} • PKR {r['PKR']:,.0f}"
        for _, r in filtered.iterrows()
    }
    options = [None] + list(nice_labels.keys())
    default_idx = 0
    if st.session_state.edit_target_id in nice_labels:
        default_idx = options.index(st.session_state.edit_target_id)
    choose = st.selectbox("Edit entry", options=options, index=default_idx, format_func=lambda v: "Select an entry…" if v is None else nice_labels[v])

    if choose is not None:
        st.session_state.edit_target_id = choose

    # --- Edit Card ---
    if st.session_state.edit_target_id is not None:
        sid = int(st.session_state.edit_target_id)
        cur = month_df[month_df["id"] == sid]
        if cur.empty:
            st.session_state.edit_target_id = None
            st.rerun()
        row = cur.iloc[0]

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"### Edit Entry #{sid}")
        st.markdown('<div class="desc">Update any field. Use Delete to remove permanently.</div>', unsafe_allow_html=True)

        with st.form(f"edit_sp_{sid}"):
            e1, e2, e3 = st.columns([2.1, 1.6, 1.0])
            title_e = e1.text_input("Title", value=row["title"])
            category_e = e2.text_input("Category", value=row["category"])
            in_office_e_radio = e3.radio("In-Office?", ["Yes","No"], index=(0 if bool(row["in_office"]) else 1), horizontal=True)

            e4, e5, e6 = st.columns([1,1,1])
            usd_e = e4.text_input("Amount - USD (optional)", value="" if pd.isna(row["amount_usd"]) else str(row["amount_usd"]))
            pkr_e = e5.number_input("Amount - PKR", min_value=0.0, step=100.0, value=float(row["amount_pkr"]))
            date_e = e6.date_input("Date", value=pd.to_datetime(row["date"]).date())

            e7, e8 = st.columns([1.4, 2.6])
            method_e = e7.radio("Payment Method", ["Online","IBFT","Cash"], index=["Online","IBFT","Cash"].index(row["payment_method"]), horizontal=True)

            banks_df = list_bank_accounts()
            if method_e in ("Online","IBFT") and not banks_df.empty:
                bank_map = {f"{r['title']} (#{r['id']})": int(r["id"]) for _, r in banks_df.iterrows()}
                default_label = next((k for k,v in bank_map.items() if v == (row["bank_account_id"] or -1)), None)
                bank_label_e = e8.selectbox("Bank Account Used", list(bank_map.keys()),
                                            index=(list(bank_map.keys()).index(default_label) if default_label in bank_map else 0))
                bank_e_id = bank_map[bank_label_e]
            else:
                bank_e_id = None
                if method_e in ("Online","IBFT"):
                    e8.warning("No bank accounts available.")

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

            err = update_spending(
                sid=sid,
                title=title_e,
                category=category_e,
                amount_pkr=float(pkr_e),
                amount_usd=usd_val,
                dt=date_e,
                payment_method=method_e,
                bank_account_id=bank_e_id,
                in_office=(in_office_e_radio == "Yes"),
            )
            if err:
                st.error(f"Update failed: {err}")
            else:
                st.success("Updated.")
                st.session_state.edit_target_id = None
            st.rerun()

        if del_btn:
            err = delete_spending(sid)
            if err:
                st.error(f"Delete failed: {err}")
            else:
                st.success("Deleted.")
                st.session_state.edit_target_id = None
            st.rerun()

        if cancel_btn:
            st.session_state.edit_target_id = None
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
