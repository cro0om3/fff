import os
import json
import pandas as pd
from pathlib import Path

# Robust import: allow both package-relative and top-level imports depending on execution context
try:
    from ..common.config import DATA_PATH, SETTINGS_FILE, BOOKINGS_FILE
except Exception:
    try:
        # When running as a script or inside some tooling, package-relative imports may fail
        from common.config import DATA_PATH, SETTINGS_FILE, BOOKINGS_FILE
    except Exception:
        # Final fallback: compute paths relative to this file
        ROOT = Path(__file__).parent.parent.resolve()
        DATA_PATH = ROOT / 'data'
        SETTINGS_FILE = DATA_PATH / 'settings.json'
        BOOKINGS_FILE = DATA_PATH / 'bookings.xlsx'


def find_settings_file() -> Path:
    """Search for an existing settings.json in known locations and return the Path.

    Search order:
    - repo_root/data/settings.json
    - Snow_Liwa1-main/data/settings.json (legacy)
    - snow_liwa/data/settings.json (legacy inside package)
    If none found, return default SETTINGS_FILE (repo_root/data/settings.json).
    """
    repo_root = Path(__file__).parent.parent.parent.resolve()
    candidates = [
        repo_root / "data" / "settings.json",
        repo_root / "Snow_Liwa1-main" / "data" / "settings.json",
        repo_root / "Snow_Liwa1-main" / "snow_liwa" / "data" / "settings.json",
        SETTINGS_FILE,
    ]
    for c in candidates:
        if c.exists():
            return c
    return SETTINGS_FILE

def ensure_all_required_dirs():
    (DATA_PATH).mkdir(exist_ok=True)
    (Path('assets')).mkdir(exist_ok=True)
    (Path('assets/images')).mkdir(exist_ok=True)

def ensure_settings_file_exists():
    settings_path = find_settings_file()
    if not settings_path.exists():
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump({
                "admin_pin": "1234",
                "api_debug": False,
                "apis": {"ziina": {"enabled": True, "base_url": "https://api-v2.ziina.com/api", "timeout_sec": 15}},
            }, f, ensure_ascii=False, indent=2)

def load_settings():
    settings_path = find_settings_file()
    ensure_settings_file_exists()
    with open(settings_path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_settings(settings: dict) -> None:
    settings_path = find_settings_file()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def ensure_bookings_file_exists():
    if not BOOKINGS_FILE.exists():
        df = pd.DataFrame(columns=[
            "booking_id", "created_at", "name", "phone", "tickets", "ticket_price", "total_amount", "status", "payment_intent_id", "payment_status", "redirect_url", "notes"
        ])
        df.to_excel(BOOKINGS_FILE, index=False)

def ensure_all_required_files():
    ensure_settings_file_exists()
    ensure_bookings_file_exists()

def get_image_path(name: str) -> str:
    path = Path('assets/images') / name
    if path.exists():
        return str(path)
    return 'assets/images/placeholder.png'
