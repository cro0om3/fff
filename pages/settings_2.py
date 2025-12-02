import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import render_settings
import streamlit as st  # type: ignore
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
    render_settings()

if __name__ == "__main__":
    main()
