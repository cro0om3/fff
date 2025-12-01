
# PIN-based admin authentication for Streamlit

import streamlit as st
from ..utils.io import load_settings

def get_admin_pin():
    settings = load_settings()
    return settings.get("admin_pin", "1234")

def verify_pin(input_pin: str) -> bool:
    return input_pin == get_admin_pin()

def require_admin_auth():
    if not st.session_state.get("authenticated", False):
        pin = st.text_input("Enter admin PIN", type="password")
        if st.button("Login"):
            if verify_pin(pin):
                st.session_state["authenticated"] = True
                st.success("Authenticated!")
            else:
                st.error("Incorrect PIN.")
        st.stop()
