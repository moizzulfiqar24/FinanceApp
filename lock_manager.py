import streamlit as st
import os
from dotenv import load_dotenv
import json, os

LOCK_FILE = ".lock.json"
load_dotenv()
PIN = os.getenv("APP_PIN", "1234")

def get_lock() -> bool:
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "r") as f:
            return json.load(f).get("locked", False)
    except Exception:
        return False

def set_lock(val: bool):
    with open(LOCK_FILE, "w") as f:
        json.dump({"locked": val}, f)

def lock_guard():
    """Place this at the top of every page to enforce lock/unlock logic."""
    from lock_manager import get_lock, set_lock

    if get_lock():
        st.title("🔒 Locked")
        pin_input = st.text_input("Enter PIN", type="password")
        if st.button("Unlock"):
            if pin_input == PIN:
                set_lock(False)
                st.rerun()
            else:
                st.error("Wrong PIN")
        st.stop()

    # Sidebar button to lock again
    if st.sidebar.button("🔒 Hide App"):
        set_lock(True)
        st.rerun()
