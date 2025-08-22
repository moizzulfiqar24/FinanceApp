import streamlit as st
import pandas as pd
import altair as alt
from DB.database import init_db
from DB.queries import get_spendings_df
from lock_manager import lock_guard

st.set_page_config(page_title="Finance Dashboard", page_icon="📊", layout="wide")

# Enforce lock/unlock at start
lock_guard()

# Init DB + seed
init_db()

# Sidebar navigation
st.sidebar.page_link("main.py", label="📊 Dashboard")
st.sidebar.page_link("pages/1_Bank_Accounts.py", label="🏦 Bank Accounts")
st.sidebar.page_link("pages/2_Spendings.py", label="💸 Spendings")
st.sidebar.page_link("pages/3_Subscriptions.py", label="📬 Subscriptions")

st.title("📊 Dashboard")

df = get_spendings_df()
if df.empty:
    st.info("No spendings yet.")
    st.stop()

# KPIs
col1, col2, col3 = st.columns(3)
col1.metric("Total spend (PKR)", f"{df['amount_pkr'].sum():,.0f}")
col2.metric("Entries", f"{len(df)}")
col3.metric("Categories", f"{df['category'].nunique()}")

st.divider()

# ---- CHART 1: Total spendings by month (bar) ----
st.subheader("Total Spendings by Month")
df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").dt.to_timestamp()
by_month = df.groupby("month", as_index=False)["amount_pkr"].sum().sort_values("month")
chart_month = alt.Chart(by_month).mark_bar().encode(
    x=alt.X("month:T", title="Month"),
    y=alt.Y("amount_pkr:Q", title="Total PKR"),
    tooltip=[alt.Tooltip("month:T"), alt.Tooltip("amount_pkr:Q", format=",.0f")]
).properties(height=340)
st.altair_chart(chart_month, use_container_width=True)

st.divider()

# ---- CHART 2: Total spendings by categories (bar) ----
st.subheader("Total Spendings by Category")
by_cat = (df.groupby("category", as_index=False)["amount_pkr"].sum()
            .sort_values("amount_pkr", ascending=False))
chart_cat = alt.Chart(by_cat).mark_bar().encode(
    x=alt.X("category:N", sort="-y", title="Category"),
    y=alt.Y("amount_pkr:Q", title="Total PKR"),
    tooltip=["category", alt.Tooltip("amount_pkr:Q", format=",.0f")]
).properties(height=340)
st.altair_chart(chart_cat, use_container_width=True)

# NOTE: Per requirement, removed all previous charts and the "Recent Entries" table from Dashboard.
