from pathlib import Path
import pandas as pd
from datetime import datetime
from .io import find_settings_file


def bookings_file_path() -> Path:
    repo_root = Path(__file__).parent.parent.parent.resolve()
    candidates = [
        repo_root / "data" / "bookings.xlsx",
        repo_root / "Snow_Liwa1-main" / "data" / "bookings.xlsx",
        repo_root / "Snow_Liwa1-main" / "snow_liwa" / "data" / "bookings.xlsx",
    ]
    for c in candidates:
        if c.exists():
            return c
    # default
    default = repo_root / "data" / "bookings.xlsx"
    return default


def ensure_bookings_file_exists():
    p = bookings_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        df = pd.DataFrame(columns=[
            "booking_id",
            "created_at",
            "name",
            "phone",
            "tickets",
            "ticket_price",
            "total_amount",
            "status",
            "payment_intent_id",
            "payment_status",
            "redirect_url",
            "notes",
        ])
        df.to_excel(p, index=False)


def load_bookings() -> pd.DataFrame:
    p = bookings_file_path()
    ensure_bookings_file_exists()
    return pd.read_excel(p)


def save_bookings(df: pd.DataFrame) -> None:
    p = bookings_file_path()
    df.to_excel(p, index=False)


def get_next_booking_id(df: pd.DataFrame) -> str:
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"SL-{today}-"
    todays = df[df["booking_id"].astype(str).str.startswith(prefix)]
    if todays.empty:
        seq = 1
    else:
        last = todays["booking_id"].iloc[-1]
        try:
            seq = int(str(last).split("-")[-1]) + 1
        except Exception:
            seq = len(todays) + 1
    return prefix + f"{seq:03d}"
