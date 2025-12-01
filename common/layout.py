# Shared layout components for Streamlit
import streamlit as st

def render_public_header():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)

def render_admin_header():
    st.markdown('<div class="snow-title">SNOW LIWA Admin</div>', unsafe_allow_html=True)

def render_footer():
    st.markdown('<div class="footer-note">© 2025 SNOW LIWA</div>', unsafe_allow_html=True)

def render_sidebar_menu(menu_items):
    st.sidebar.title("Menu")
    for item in menu_items:
        st.sidebar.write(item)
