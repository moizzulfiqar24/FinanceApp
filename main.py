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

# By Category
st.subheader("By Category")
by_cat = (df.groupby("category", as_index=False)["amount_pkr"].sum()
            .sort_values("amount_pkr", ascending=False))
chart_cat = alt.Chart(by_cat).mark_bar().encode(
    x=alt.X("category:N", sort="-y", title="Category"),
    y=alt.Y("amount_pkr:Q", title="Total PKR"),
    tooltip=["category", alt.Tooltip("amount_pkr:Q", format=",.0f")]
).properties(height=320)
st.altair_chart(chart_cat, use_container_width=True)

# Daily Trend
st.subheader("Daily Trend")
df["date"] = pd.to_datetime(df["date"]).dt.date
daily = df.groupby("date", as_index=False)["amount_pkr"].sum()
chart_daily = alt.Chart(daily).mark_line(point=True).encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y("amount_pkr:Q", title="PKR"),
    tooltip=[alt.Tooltip("date:T"), alt.Tooltip("amount_pkr:Q", format=",.0f")]
).properties(height=320)
st.altair_chart(chart_daily, use_container_width=True)

# Recent
st.subheader("Recent Entries")
show = df[["date","title","category","amount_pkr","payment_method","bank_title"]].rename(
    columns={"date":"Date","title":"Title","category":"Category","amount_pkr":"PKR","payment_method":"Method","bank_title":"Bank"}
)
st.dataframe(show, hide_index=True, use_container_width=True)
