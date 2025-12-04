import streamlit as st  # type: ignore
from app import render_dashboard
try:
    from snow_liwa.theme import apply_snow_liwa_theme
except Exception:
    from theme import apply_snow_liwa_theme

# Apply the centralized theme for this page
try:
    apply_snow_liwa_theme()
except Exception:
    pass

def main():
    render_dashboard()


if __name__ == "__main__":
    main()
