import os
import json
from pathlib import Path

def load_settings() -> dict:
    settings_path = Path(__file__).resolve().parents[1] / "data" / "settings.json"
    if not settings_path.exists():
        return {"ticket_poster_path": "assets/ticket_poster.png"}
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"ticket_poster_path": "assets/ticket_poster.png"}

def save_settings(settings: dict) -> None:
    settings_path = Path(__file__).resolve().parents[1] / "data" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
