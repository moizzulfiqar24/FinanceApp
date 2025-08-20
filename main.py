import streamlit as st
import os
from dotenv import load_dotenv
from DB.database import init_db
from app_pages import page1_bank_accounts, page2_spendings, page3_dashboard

load_dotenv()
PIN = os.getenv("APP_PIN", "1234")  # fallback default

st.set_page_config(page_title="Personal Finance – Simple App", page_icon="💼", layout="wide")

# Ensure DB & seed
init_db()

# --- PIN lock ---
if "unlocked" not in st.session_state:
    st.session_state.unlocked = False

if not st.session_state.unlocked:
    st.title("🔒 Enter PIN to Unlock")
    pin_input = st.text_input("PIN", type="password")
    if st.button("Unlock"):
        if pin_input == PIN:
            st.session_state.unlocked = True
            st.success("Unlocked! 🎉")
            st.rerun()
        else:
            st.error("Incorrect PIN")
    st.stop()

# --- If unlocked, show full app ---
PAGES = {
    "Bank Accounts": page1_bank_accounts,
    "Spendings": page2_spendings,
    "Dashboard": page3_dashboard,
}

choice = st.sidebar.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")
PAGES[choice].render()
