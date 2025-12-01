"""Archived copy of admin_settings page wrapper."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_settings import main

if __name__ == "__main__":
    main()

# Archived: original file moved to _archive to avoid duplicate Streamlit pages
