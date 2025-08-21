import streamlit as st
import os
from dotenv import load_dotenv
import json

LOCK_FILE = ".lock.json"
load_dotenv()

def get_app_pin():
    """Get APP_PIN from Streamlit secrets (cloud) or environment variables (local)"""
    try:
        return st.secrets["APP_PIN"]
    except:
        return os.getenv("APP_PIN")

PIN = get_app_pin()

def get_lock() -> bool:
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "r") as f:
            return json.load(f).get("locked", False)
    except Exception:
        return False

def set_lock(val: bool):
    try:
        with open(LOCK_FILE, "w") as f:
            json.dump({"locked": val}, f)
    except Exception:
        # If we can't write to file system (some cloud environments), 
        # fall back to session state
        st.session_state["app_locked"] = val

def lock_guard():
    """Place this at the top of every page to enforce lock/unlock logic."""
    
    # Try to get lock status from file, fallback to session state
    try:
        locked = get_lock()
    except:
        locked = st.session_state.get("app_locked", False)
    
    if locked:
        st.title("🔒 Locked")
        pin_input = st.text_input("Enter PIN", type="password")
        if st.button("Unlock"):
            if pin_input == PIN:
                set_lock(False)
                if "app_locked" in st.session_state:
                    st.session_state["app_locked"] = False
                st.rerun()
            else:
                st.error("Wrong PIN")
        st.stop()

    # Sidebar button to lock again
    if st.sidebar.button("🔒 Hide App"):
        set_lock(True)
        if "app_locked" not in st.session_state:
            st.session_state["app_locked"] = True
        st.rerun()