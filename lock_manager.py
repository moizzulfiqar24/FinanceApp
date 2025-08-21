# Temporary LOCKED

# import streamlit as st
# import os
# from dotenv import load_dotenv
# import json, os

# LOCK_FILE = ".lock.json"
# load_dotenv()
# PIN = os.getenv("APP_PIN")

# def get_lock() -> bool:
#     if not os.path.exists(LOCK_FILE):
#         return False
#     try:
#         with open(LOCK_FILE, "r") as f:
#             return json.load(f).get("locked", False)
#     except Exception:
#         return False

# def set_lock(val: bool):
#     with open(LOCK_FILE, "w") as f:
#         json.dump({"locked": val}, f)

# def lock_guard():
#     """Place this at the top of every page to enforce lock/unlock logic."""
#     from lock_manager import get_lock, set_lock

#     if get_lock():
#         st.title("🔒 Locked")
#         pin_input = st.text_input("Enter PIN", type="password")
#         if st.button("Unlock"):
#             if pin_input == PIN:
#                 set_lock(False)
#                 st.rerun()
#             else:
#                 st.error("Wrong PIN")
#         st.stop()

#     # Sidebar button to lock again
#     if st.sidebar.button("🔒 Hide App"):
#         set_lock(True)
#         st.rerun()

# ALWAYS LOCKED

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
PIN = os.getenv("APP_PIN") or (st.secrets.get("APP_PIN") if hasattr(st, "secrets") else None)

def _current_page_key() -> str:
    # Streamlit 1.27+: st.query_params; fallback to experimental_get_query_params
    try:
        val = st.query_params.get("page", "main")
        return (val[0] if isinstance(val, list) else val) or "main"
    except Exception:
        return st.experimental_get_query_params().get("page", ["main"])[0]

def lock_guard():
    """Call at the top of EVERY page. Always-locked by default.
    Unlock applies only to the current page; page change or refresh re-locks.
    """
    page = _current_page_key()

    # If page changed since last run, clear any previous unlocks
    last = st.session_state.get("_last_page")
    if last != page:
        for k in list(st.session_state.keys()):
            if k.startswith(("unlocked_", "pin_")):
                del st.session_state[k]
        st.session_state["_last_page"] = page

    flag_key = f"unlocked_{page}"
    pin_key = f"pin_{page}"

    if not st.session_state.get(flag_key, False):
        st.title("🔒 Locked")
        pin = st.text_input("Enter PIN", type="password", key=pin_key)
        if st.button("Unlock", key=f"unlock_{page}"):
            if str(pin) == str(PIN):
                st.session_state[flag_key] = True
                st.rerun()
            else:
                st.error("Wrong PIN")
        st.stop()  # stop rendering until unlocked

    # Manual re-lock
    if st.sidebar.button("🔒 Hide App"):
        st.session_state[flag_key] = False
        st.rerun()
