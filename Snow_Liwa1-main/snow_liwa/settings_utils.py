"""Utilities for loading and saving Snow Liwa app settings.

The Streamlit app dynamically imports this module to keep the main file
self-contained while still allowing settings persistence on disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Defaults cover every key the app accesses so missing values never break UI.
DEFAULT_SETTINGS: Dict[str, Any] = {
    "background_mode": "preset1",
    "background_image_path": None,
    "background_brightness": 1.0,
    "background_blur": 0,
    "background_opacity": 1.0,
    "custom_bg": "#eaf6ff",
    "hero_image_source": "assets/hero_main.png",
    "hero_image_path": None,
    "hero_side": "left",
    "hero_card_size": "medium",
    "accent_color": "snow_blue",
    "theme_mode": "light",
    "hero_subtitle": "تجربة شتوية في قلب الظفرة",
    "hero_intro_paragraph": "مشروع شبابي إماراتي يقدم أجواء ليوا الشتوية للعائلات والشباب، من لعب الثلج إلى الشوكولاتة الساخنة.",
    "working_days": "كل أيام الأسبوع",
    "working_hours": "4:00pm - 12:00am",
    "ticket_price": 175,
    "ticket_currency": "AED",
    "max_tickets_per_booking": 10,
    "payment_mode": "cash_on_arrival",
    "payment_base_url_or_template": "",
    "whatsapp_enabled": False,
    "whatsapp_phone": "971501234567",
    "whatsapp_message_template": "مرحبا، أود تأكيد حجز رقم {booking_id} لعدد {tickets} تذاكر في SNOW LIWA.",
    "snow_enabled": False,
    "snow_density": "medium",
    "location_label": "الموقع: منطقة الظفرة – ليوا",
    "season_label": "الموسم: شتاء 2025",
    "family_label": "مناسب للعائلات والأطفال",
    "ticket_poster_path": "assets/ticket_poster.png",
}


def _ensure_storage() -> None:
    """Make sure the data directory and settings file exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        with SETTINGS_FILE.open("w", encoding="utf-8") as outfile:
            json.dump(DEFAULT_SETTINGS, outfile, ensure_ascii=False, indent=2)


def load_settings() -> Dict[str, Any]:
    """Load settings from disk, falling back to defaults on error."""
    _ensure_storage()
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as infile:
            raw = json.load(infile)
            if not isinstance(raw, dict):  # Guard against malformed files.
                raise ValueError("Settings file must contain a JSON object")
    except Exception:
        # If anything goes wrong we restore defaults so the app keeps working.
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    merged = DEFAULT_SETTINGS.copy()
    merged.update(raw)
    return merged


def save_settings(settings: Dict[str, Any]) -> None:
    """Persist settings to disk."""
    _ensure_storage()
    with SETTINGS_FILE.open("w", encoding="utf-8") as outfile:
        json.dump(settings, outfile, ensure_ascii=False, indent=2)
