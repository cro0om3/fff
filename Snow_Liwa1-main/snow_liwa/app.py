import logging
import base64
from datetime import datetime
from pathlib import Path
import urllib.parse
import os
import json
import html
from settings_utils import load_settings

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# =========================
# BASIC CONFIG
# =========================

st.set_page_config(
    page_title="SNOW LIWA",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================
# SETTINGS
# =========================

BASE_DIR = Path(__file__).resolve().parent
BACKGROUND_IMAGE_PATH = BASE_DIR / "assets" / "snow_liwa_bg.jpg"
HERO_IMAGE_PATH = BACKGROUND_IMAGE_PATH
DATA_DIR = BASE_DIR / "data"
BOOKINGS_FILE = DATA_DIR / "bookings.xlsx"

TICKET_PRICE = 175  # AED per ticket


# =========================
# ZIINA CONFIG FROM SECRETS
# =========================


def get_ziina_config():
    # Prefer st.secrets, fallback to legacy variables for compatibility
    try:
        access_token = st.secrets["ziina"]["access_token"]
    except Exception:
        access_token = None
    try:
        app_base_url = st.secrets["ziina"]["app_base_url"]
    except Exception:
        app_base_url = "https://snow-liwa.streamlit.app"
    try:
        test_mode = st.secrets["ziina"].get("test_mode", False)
    except Exception:
        test_mode = False
    return access_token, app_base_url, test_mode


ZIINA_API_BASE = "https://api-v2.ziina.com/api"


def get_ziina_access_token():
    access_token, _, _ = get_ziina_config()
    return access_token


def get_ziina_app_base_url():
    _, app_base_url, _ = get_ziina_config()
    return app_base_url


def get_ziina_test_mode():
    _, _, test_mode = get_ziina_config()
    return test_mode


def ensure_ziina_secrets():
    """Validate Ziina secrets and show Streamlit warnings if misconfigured."""
    access_token, app_base_url, test_mode = get_ziina_config()
    if not access_token:
        st.warning("Ziina access token not found in `st.secrets['ziina']['access_token']`. Please add it to `.streamlit/secrets.toml`.")
        return False
    if access_token.startswith("REPLACE_WITH") or access_token.strip() == "":
        st.warning("Ziina access token looks like a placeholder. Replace it in `.streamlit/secrets.toml` with your real token.")
        return False
    # Informational display in test mode
    if test_mode:
        st.info("Ziina is running in test mode (secrets: `ziina.test_mode = true`).")
    return True


PAGES = {
    "Welcome": "welcome",
    "Who we are": "who",
    "Experience": "experience",
    "Contact": "contact",
    "Dashboard (Admin)": "dashboard",
}

ADMIN_PASSWORD = "0502992"  # Hidden admin unlock passcode

# =========================
# DATA HELPERS
# =========================


def ensure_data_file():
    DATA_DIR.mkdir(exist_ok=True)
    if not BOOKINGS_FILE.is_file():
        df = pd.DataFrame(
            columns=[
                "booking_id",
                "created_at",
                "name",
                "phone",
                "tickets",
                "ticket_price",
                "total_amount",
                "status",  # pending / paid / cancelled
                "payment_intent_id",  # from Ziina
                # requires_payment_instrument / completed / failed...
                "payment_status",
                "redirect_url",  # Ziina hosted page
                "notes",
            ]
        )
        df.to_excel(BOOKINGS_FILE, index=False)


def load_bookings():
    ensure_data_file()
    return pd.read_excel(BOOKINGS_FILE)


def save_bookings(df: pd.DataFrame):
    df.to_excel(BOOKINGS_FILE, index=False)


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


# =========================
# TICKET HELPERS
# =========================

def build_ticket_text(booking_id: str, name: str, phone: str, tickets: int, total_amount: float) -> str:
    """Return a small text ticket so it can be shared/downloaded with the customer's name."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "SNOW LIWA — Booking Ticket",
        "--------------------------",
        f"Booking ID : {booking_id}",
        f"Name       : {name}",
        f"Phone      : {phone}",
        f"Tickets    : {tickets}",
        f"Total (AED): {total_amount:.2f}",
        f"Issued at  : {timestamp}",
        "",
        "Show this ticket on arrival. For help: Instagram/WhatsApp snowliwa",
    ]
    return "\n".join(lines)


# =========================
# ZIINA API HELPERS
# =========================


def has_ziina_configured() -> bool:
    token = get_ziina_access_token()
    return bool(token) and token != "PUT_YOUR_ZIINA_ACCESS_TOKEN_IN_SECRETS"


def create_payment_intent(amount_aed: float, booking_id: str, customer_name: str) -> dict | None:
    """Create Payment Intent via Ziina API and return JSON."""
    access_token = get_ziina_access_token()
    app_base_url = get_ziina_app_base_url()
    test_mode = get_ziina_test_mode()
    if not access_token:
        st.error(
            "Ziina API key is missing from st.secrets. Please add access_token under [ziina].")
        return None

    # Ziina expects amount in fils (cents equivalent)
    amount_fils = int(round(amount_aed * 100))
    url = f"{ZIINA_API_BASE}/payment_intent"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    base_return = app_base_url.rstrip("/")
    success_url = f"{base_return}/?result=success&pi_id={{PAYMENT_INTENT_ID}}"
    cancel_url = f"{base_return}/?result=cancel&pi_id={{PAYMENT_INTENT_ID}}"
    failure_url = f"{base_return}/?result=failure&pi_id={{PAYMENT_INTENT_ID}}"
    payload = {
        "amount": amount_fils,
        "currency_code": "AED",
        "message": f"Snow Liwa booking {booking_id} - {customer_name}",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "failure_url": failure_url,
        "test": test_mode,
    }
    # Debug logging (mask token)
    logging.info(f"[ZIINA] POST {url}")
    logging.info(
        f"[ZIINA] Headers: {{'Authorization': 'Bearer ***', 'Content-Type': 'application/json'}}")
    logging.info(f"[ZIINA] Payload: {payload}")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.RequestException as e:
        st.error(f"Error talking to Ziina API: {e}")
        return None
    logging.info(f"[ZIINA] Response status: {resp.status_code}")
    logging.info(f"[ZIINA] Response text: {resp.text}")
    # Accept 200 or 201 as success (Ziina may return 201 Created)
    if resp.status_code not in (200, 201):
        try:
            msg = resp.json().get("message", resp.text)
        except Exception:
            msg = resp.text
        st.error(f"Ziina API error ({resp.status_code}): {msg}")
        return None
    return resp.json()


def get_payment_intent(pi_id: str) -> dict | None:
    """Fetch payment intent from Ziina."""
    access_token = get_ziina_access_token()
    if not access_token:
        st.error(
            "Ziina API key is missing from st.secrets. Please add access_token under [ziina].")
        return None
    url = f"{ZIINA_API_BASE}/payment_intent/{pi_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    logging.info(f"[ZIINA] GET {url}")
    logging.info(f"[ZIINA] Headers: {{'Authorization': 'Bearer ***'}}")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as e:
        st.error(f"Error talking to Ziina API: {e}")
        return None
    logging.info(f"[ZIINA] Response status: {resp.status_code}")
    logging.info(f"[ZIINA] Response text: {resp.text}")
    if resp.status_code != 200:
        try:
            msg = resp.json().get("message", resp.text)
        except Exception:
            msg = resp.text
        st.error(f"Ziina API error ({resp.status_code}): {msg}")
        return None
    return resp.json()
# =========================
# DEBUG/ADMIN: TEST ZIINA API
# =========================


def test_ziina_credentials():
    """Test Ziina API credentials by creating a dummy payment intent (does not create booking)."""
    access_token = get_ziina_access_token()
    app_base_url = get_ziina_app_base_url()
    test_mode = True  # Always test mode for this
    if not access_token:
        st.error(
            "Ziina API key is missing from st.secrets. Please add access_token under [ziina].")
        return
    url = f"{ZIINA_API_BASE}/payment_intent"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    base_return = app_base_url.rstrip("/")
    payload = {
        "amount": 100,  # 1 AED in fils
        "currency_code": "AED",
        "message": "Test payment intent (debug)",
        "success_url": f"{base_return}/?result=success&pi_id={{PAYMENT_INTENT_ID}}",
        "cancel_url": f"{base_return}/?result=cancel&pi_id={{PAYMENT_INTENT_ID}}",
        "failure_url": f"{base_return}/?result=failure&pi_id={{PAYMENT_INTENT_ID}}",
        "test": test_mode,
    }
    logging.info(f"[ZIINA-TEST] POST {url}")
    logging.info(
        f"[ZIINA-TEST] Headers: {{'Authorization': 'Bearer ***', 'Content-Type': 'application/json'}}")
    logging.info(f"[ZIINA-TEST] Payload: {payload}")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.RequestException as e:
        st.error(f"Error talking to Ziina API: {e}")
        return
    logging.info(f"[ZIINA-TEST] Response status: {resp.status_code}")
    logging.info(f"[ZIINA-TEST] Response text: {resp.text}")
    st.write(f"**Status code:** {resp.status_code}")
    st.write(f"**Response:** {resp.text}")


def sync_payments_from_ziina(df: pd.DataFrame) -> pd.DataFrame:
    """Loop pending bookings and update payment status from Ziina."""
    if not has_ziina_configured():
        st.error("Ziina API not configured.")
        return df

    updated = False
    for idx, row in df.iterrows():
        pi_id = str(row.get("payment_intent_id") or "").strip()
        if not pi_id:
            continue

        pi = get_payment_intent(pi_id)
        if not pi:
            continue

        status = pi.get("status")
        if not status:
            continue

            # removed unused/incomplete line

        if status == "completed":
            df.loc[df.index == idx, "status"] = "paid"
            updated = True
        elif status in ("failed", "canceled"):
            df.loc[df.index == idx, "status"] = "cancelled"
            updated = True

    if updated:
        save_bookings(df)
    return df


# =========================
# UI HELPERS
# =========================


def encode_image_base64(image_path: Path) -> str | None:
    if not image_path.is_file():
        return None
    try:
        return base64.b64encode(image_path.read_bytes()).decode()
    except Exception:
        return None


def set_background(image_path: Path):
    # Allow background color override from session_state (set via dashboard settings)
    bg_color = st.session_state.get("custom_bg", "#eaf6ff")
    css = f"""
    <style>
    .stApp {{
        background: linear-gradient(180deg, {bg_color} 0%, #e7f5ff 45%, #fff1d6 75%, #f4c37a 100%);
        color: #18324a;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def redirect_client_to_payment(url: str) -> None:
    """Inject JavaScript that moves the browser to the hosted payment page."""
    safe_url = json.dumps(url)
    components.html(
        f"""
        <script>
        (function() {{
            const target = {safe_url};
            try {{
                window.top.location.href = target;
            }} catch (err) {{
                window.location.href = target;
            }}
        }})();
        </script>
        """,
        height=0,
    )


def resolve_media_path(path_value):
    if not path_value:
        return None
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate if candidate.exists() else None
def inject_base_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&family=Nunito:wght@300;400;600;700&family=Noto+Kufi+Arabic:wght@400;600;700&display=swap');
        :root {
            --sl-bg: #f5fbff;
            --sl-bg-soft: #ffffff;
            --sl-accent: #4dafff;
            --sl-accent-soft: #ffcf70;
            --sl-text-main: #163046;
            --sl-text-muted: #6b7b8c;
            --sl-danger: #ff4b6b;
            --sl-success: #10b981;
            --sl-warning: #f59e0b;
            --sl-radius-pill: 999px;
            --sl-radius-lg: 26px;
            --sl-shadow-soft: 0 14px 40px rgba(7, 36, 63, 0.10);
        }
        html { font-size: 15px; }
        *, ::before, ::after { box-sizing: border-box; }
        body, .stApp {
            font-family: 'Inter', 'Noto Kufi Arabic', 'SF Pro Display', system-ui, -apple-system, sans-serif;
            background: radial-gradient(circle at top right, #ffffff 0%, #e4f3ff 45%, #fff1d6 85%, #f2bc6d 125%);
            color: var(--sl-text-main);
        }
        a, a:visited {
            color: inherit;
            text-decoration: none;
        }
        a:hover, a:focus {
            text-decoration: none;
        }
        * {
            font-family: 'Inter', 'Noto Kufi Arabic', 'SF Pro Display', system-ui, -apple-system, sans-serif;
        }
        .arabic-text {
            direction: rtl;
            text-align: right;
        }
        .english-text {
            direction: ltr;
            text-align: left;
            font-family: 'Nunito', system-ui, sans-serif;
        }
        @supports (scrollbar-color: transparent transparent) {
            * {
                scrollbar-width: thin;
                scrollbar-color: transparent transparent;
            }
        }
        .stApp { padding: 0; }
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }
        .page-container {
            max-width: 1150px;
            margin: 0 auto;
            padding: 0 1.1rem 2.8rem;
        }
        .page-card {
            background: transparent;
            border-radius: 0;
            padding: 0;
            border: none;
            box-shadow: none;
        }
        .section-spacer { height: 2.4rem; }
        .landing-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.9rem 1.4rem;
            border-radius: var(--sl-radius-lg);
            background: rgba(255, 255, 255, 0.88);
            box-shadow: var(--sl-shadow-soft);
            border: 1px solid rgba(77, 175, 255, 0.18);
        }
        .landing-logo {
            display: flex;
            align-items: center;
            gap: 0.9rem;
        }
        .landing-logo-mark {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--sl-accent), var(--sl-accent-soft));
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: 700;
            font-size: 1.1rem;
            box-shadow: 0 10px 26px rgba(77, 175, 255, 0.35);
        }
        .landing-logo-text-main {
            font-weight: 700;
            letter-spacing: 0.08em;
            font-size: 1.45rem;
        }
        .landing-logo-text-sub {
            font-size: 0.78rem;
            color: var(--sl-text-muted);
        }
        .landing-header-cta {
            display: flex;
            align-items: center;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            padding: 0.65rem 1.45rem;
            border-radius: var(--sl-radius-pill);
            text-decoration: none;
            font-weight: 700;
            letter-spacing: 0.05em;
            background: linear-gradient(135deg, #ffe8b2, #f7b343);
            color: #2b1b05 !important;
            border: none;
            box-shadow: 0 10px 26px rgba(211, 151, 49, 0.45);
            transition: transform 0.15s ease, box-shadow 0.2s ease;
        }
        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 14px 32px rgba(211, 151, 49, 0.55);
        }
        .btn.btn-outline {
            background: linear-gradient(135deg, #fff4dc, #ffcf70);
            color: #3d2a0b !important;
            border: 1.5px solid rgba(247, 179, 67, 0.65);
            box-shadow: 0 8px 22px rgba(211, 151, 49, 0.32);
        }
        .btn.btn-outline:hover {
            background: linear-gradient(135deg, #ffe8b2, #f7b343);
            color: #2b1b05 !important;
            box-shadow: 0 14px 32px rgba(211, 151, 49, 0.55);
        }
        .hero-section {
            margin-top: 1.2rem;
            padding: 2.1rem 2rem;
            border-radius: 32px;
            background:
                radial-gradient(circle at top left, rgba(255, 255, 255, 0.7), transparent 60%),
                linear-gradient(145deg, #f5fbff 0%, rgba(255, 255, 255, 0.92) 40%, rgba(255, 233, 195, 0.95) 100%);
            box-shadow: var(--sl-shadow-soft);
        }
        .hero-content {
            position: relative;
            z-index: 2;
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 1.5rem;
            padding: 2.8rem 2rem;
            color: var(--sl-text-main);
            text-align: center;
        }
        .hero-content p {
            margin-bottom: 1.2rem;
            font-size: 1.1rem;
            max-width: 420px;
        }
        .hero-title-main {
            font-size: 3.2rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: var(--sl-accent);
            font-weight: 800;
            margin-bottom: 0.6rem;
        }
        .hero-subtitle-main {
            font-size: 1.6rem;
            color: #18324a;
            font-weight: 600;
            margin-bottom: 0.3rem;
            direction: rtl;
        }
        .snow-experience-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.5rem 1.05rem;
            border-radius: var(--sl-radius-pill);
            background: rgba(255, 207, 112, 0.3);
            color: #b76b00;
            font-weight: 600;
            font-size: 0.95rem;
            margin-bottom: 1rem;
        }
        .snow-experience-pill-icon {
            font-size: 1.25rem;
        }
        .hero-subtext {
            font-size: 0.98rem;
            color: var(--sl-text-muted);
            line-height: 1.8;
            margin-bottom: 0.6rem;
            direction: rtl;
            text-align: right;
            width: 100%;
        }
        .hero-subtext.en {
            direction: ltr;
            text-align: left;
            font-family: 'Nunito', system-ui, sans-serif;
        }
        .hero-cta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin-top: 1.2rem;
        }
        .hero-cta-row .btn {
            font-size: 0.95rem;
        }
        .hero-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin-top: 1.4rem;
            font-size: 0.82rem;
            color: var(--sl-text-muted);
        }
        .badge-soft {
            padding: 0.45rem 0.9rem;
            border-radius: var(--sl-radius-pill);
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid #e0e9f5;
        }
        .poster-box {
            border-radius: 24px;
            border: 1px dashed #cfdfee;
            min-height: 220px;
            background: radial-gradient(circle at top, #f3f9ff, #ffffff);
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 0.85rem;
            color: var(--sl-text-muted);
            font-size: 0.9rem;
        }
        .poster-box img, .ticket-poster-img {
            max-width: 100%;
            border-radius: 22px;
            box-shadow: 0 14px 34px rgba(0, 0, 0, 0.12);
            display: block;
        }
        .landing-section {
            background: var(--sl-bg-soft);
            border-radius: var(--sl-radius-lg);
            padding: 1.8rem 1.6rem;
            box-shadow: var(--sl-shadow-soft);
            border: 1px solid rgba(77, 175, 255, 0.08);
        }
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.6rem;
            margin-bottom: 1rem;
        }
        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
        }
        .section-tag {
            font-size: 0.78rem;
            letter-spacing: 0.12em;
            color: var(--sl-text-muted);
        }
        .section-body p {
            margin: 0.45rem 0;
            font-size: 1rem;
            line-height: 1.9;
            direction: rtl;
            text-align: right;
        }
        .section-body p.en {
            direction: ltr;
            text-align: left;
            font-family: 'Nunito', system-ui, sans-serif;
            color: var(--sl-text-muted);
        }
        .pill-highlight {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.45rem 0.95rem;
            border-radius: var(--sl-radius-pill);
            background: rgba(255, 207, 112, 0.16);
            color: var(--sl-danger);
            font-weight: 600;
            font-size: 0.92rem;
            margin-bottom: 0.8rem;
            direction: rtl;
            text-align: right;
        }
        .ticket-card {
            background: linear-gradient(135deg, #fdf8ee, #fff4dc);
            border-radius: 24px;
            padding: 1.4rem 1.6rem;
            margin-top: 1.1rem;
            box-shadow: 0 18px 38px rgba(243, 188, 96, 0.32);
        }
        .ticket-price {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
            color: #b76b00;
        }
        .steps-list {
            list-style: none;
            padding: 0;
            margin: 0.8rem 0 0;
            font-size: 0.95rem;
            color: var(--sl-text-main);
        }
        .steps-list li {
            margin-bottom: 0.35rem;
            direction: rtl;
            text-align: right;
        }
        .landing-booking {
            background: rgba(255, 255, 255, 0.94);
        }
        .booking-form-wrapper {
            background: rgba(255, 255, 255, 0.96);
            border-radius: 22px;
            padding: 1.4rem 1.2rem 1.6rem;
            box-shadow: inset 0 0 0 1px rgba(77, 175, 255, 0.1);
        }
        .booking-form-wrapper h4 {
            margin-bottom: 1.1rem;
            font-size: 1.05rem;
        }
        .poster-card {
            background: rgba(255, 255, 255, 0.92);
            border-radius: 22px;
            padding: 1.2rem;
            box-shadow: inset 0 0 0 1px rgba(77, 175, 255, 0.08);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .poster-card .ticket-poster-wrapper {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .poster-card .ticket-poster-img {
            max-height: 320px;
            object-fit: contain;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea {
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 0.65rem 0.9rem;
            font-size: 0.95rem;
            background: #f8fbff;
            transition: border 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
        }
        div[data-testid="stTextArea"] textarea { min-height: 90px; }
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stNumberInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {
            border-color: var(--sl-accent);
            box-shadow: 0 0 0 1.5px rgba(77, 175, 255, 0.28);
            background: #ffffff;
        }
        div[data-testid="stNumberInput"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label {
            font-size: 0.88rem;
            color: var(--sl-text-muted);
        }
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button,
        div[data-testid="stLinkButton"] > button {
            border-radius: var(--sl-radius-pill);
            padding: 0.7rem 1.6rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            border: none;
            background: linear-gradient(135deg, var(--sl-accent-soft), #f7b343);
            color: #2b1b05;
            box-shadow: 0 10px 26px rgba(211, 151, 49, 0.45);
            transition: transform 0.15s ease, box-shadow 0.2s ease;
        }
        div[data-testid="stButton"] > button[kind="secondary"] {
            background: rgba(255, 255, 255, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.9);
            color: var(--sl-text-main);
            box-shadow: 0 8px 20px rgba(7, 36, 63, 0.14);
        }
        div[data-testid="stButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover,
        div[data-testid="stLinkButton"] > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 16px 32px rgba(211, 151, 49, 0.55);
        }
        div[data-testid="stButton"] > button:focus {
            outline: 2px solid rgba(130, 190, 255, 0.55);
        }
        .activity-buttons > div[data-testid="stButton"] > button {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(190, 228, 255, 0.7);
            color: #27a4ff;
            box-shadow: 0 8px 20px rgba(0, 80, 156, 0.12);
        }
        .activity-buttons > div[data-testid="stButton"] > button:hover {
            box-shadow: 0 12px 28px rgba(0, 80, 156, 0.16);
        }
        .faq-list {
            list-style: none;
            padding: 0;
            margin: 0;
            font-size: 0.98rem;
            color: var(--sl-text-main);
            direction: rtl;
            text-align: right;
        }
        .faq-list li {
            margin-bottom: 0.7rem;
            line-height: 1.8;
        }
        .dual-column {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.8rem;
        }
        .dual-column .arabic,
        .arabic {
            direction: rtl;
            text-align: right;
            font-size: 1rem;
            line-height: 1.8;
        }
        .dual-column .english {
            direction: ltr;
            text-align: left;
            font-family: 'Nunito', system-ui, sans-serif;
            color: var(--sl-text-muted);
            line-height: 1.9;
        }
        .snow-title {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 700;
            letter-spacing: 0.24em;
            margin-bottom: 0.6rem;
            color: var(--sl-accent);
        }
        .subheading {
            text-align: center;
            font-size: 1rem;
            color: var(--sl-text-muted);
            margin-bottom: 2rem;
        }
        .center-btn {
            display: flex;
            justify-content: center;
            margin-top: 0.6rem;
        }
        .footer-note {
            text-align: center;
            font-size: 0.82rem;
            color: var(--sl-text-muted);
            margin-top: 1.5rem;
        }
        .payment-container {
            max-width: 620px;
            margin: 0 auto;
            background: var(--sl-bg-soft);
            border-radius: var(--sl-radius-lg);
            padding: 2.2rem 1.8rem;
            box-shadow: var(--sl-shadow-soft);
            border: 1px solid rgba(77, 175, 255, 0.12);
            text-align: center;
        }
        .payment-logo-title {
            font-size: 1.8rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            color: var(--sl-accent);
            margin-bottom: 0.4rem;
        }
        .payment-subtitle {
            font-size: 0.95rem;
            color: var(--sl-text-muted);
            margin-bottom: 1.2rem;
        }
        .status-box {
            padding: 1.6rem;
            border-radius: 18px;
            margin-bottom: 1.4rem;
            border: 1px solid rgba(77, 175, 255, 0.16);
        }
        .status-box.success { background: #d1fae5; border-color: var(--sl-success); }
        .status-box.error { background: #fee2e2; border-color: var(--sl-danger); }
        .status-box.warning { background: #fef3c7; border-color: var(--sl-warning); }
        .status-box.info { background: #dbeafe; border-color: var(--sl-accent); }
        .status-icon { font-size: 2.8rem; margin-bottom: 0.6rem; }
        .status-message { font-size: 1.15rem; font-weight: 700; margin-bottom: 0.5rem; }
        .status-details { font-size: 0.95rem; color: var(--sl-text-muted); line-height: 1.7; }
        .payment-info-row { font-size: 0.9rem; margin: 0.35rem 0; color: var(--sl-text-muted); }
        .payment-footer { font-size: 0.85rem; color: var(--sl-text-muted); margin-top: 1.2rem; }
        .payment-actions { margin-top: 1.2rem; display: flex; flex-direction: column; gap: 0.75rem; }
        .payment-actions a {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.85rem 1.8rem;
            border-radius: var(--sl-radius-pill);
            text-decoration: none;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(135deg, #10b981, #059669);
            box-shadow: 0 12px 30px rgba(16, 185, 129, 0.36);
        }
        .payment-actions a.secondary {
            background: linear-gradient(135deg, var(--sl-accent-soft), #f7b343);
            color: #2b1b05;
            box-shadow: 0 10px 26px rgba(211, 151, 49, 0.45);
        }
        .payment-cta-wrapper {
            margin-top: 1.2rem;
            display: flex;
            justify-content: center;
        }
        .payment-cta-wrapper .btn {
            min-width: 280px;
        }
        @media (max-width: 900px) {
            .landing-header { flex-direction: column; align-items: flex-start; }
            .hero-section { padding: 1.6rem 1.4rem; }
            .hero-title-main { text-align: center; font-size: 2.4rem; letter-spacing: 0.12em; }
            .hero-subtitle-main { text-align: center; font-size: 1.3rem; }
            .hero-subtext, .hero-subtext.en { text-align: center; }
            .landing-header-cta { width: 100%; }
            .landing-header-cta .btn { width: 100%; justify-content: center; }
            .hero-cta-row { justify-content: center; }
            .hero-badges { justify-content: center; }
            .snow-experience-pill { justify-content: center; }
            .dual-column { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "Welcome"
    if "admin_taps" not in st.session_state:
        st.session_state.admin_taps = 0
    if "show_admin_password" not in st.session_state:
        st.session_state.show_admin_password = False
    if "admin_unlock_error" not in st.session_state:
        st.session_state.admin_unlock_error = ""


def page_nav():
    # Hide the full sidebar on the landing (Welcome) page to give a cleaner look.
    # Still provide small top-level buttons so users can navigate to Dashboard/Settings.
    pages = ["Welcome", "Who we are", "Experience", "Contact", "Dashboard", "Settings"]
    if st.session_state.get("page", "Welcome") == "Welcome":
        # Landing page should not expose admin links (Dashboard/Settings) to clients.
        # Do not render the sidebar or any admin navigation here.
        return

    with st.sidebar:
        st.title("SNOW LIWA")
        nav = st.radio(
            "Navigation",
            pages,
            index=pages.index(st.session_state.page) if st.session_state.page in pages else 0,
            key="sidebar_nav_radio",
        )
        st.session_state.page = nav


def get_query_params() -> dict:
    """Handle query params in both new and old Streamlit."""
    try:
        qp = st.query_params
        if hasattr(qp, "to_dict"):
            return qp.to_dict()
        return dict(qp)
    except Exception:
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}


def _normalize_query_value(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


# =========================
# PAGE CONTENT
# =========================


def render_customer_info_panel():
    st.markdown(
        """
        <div class="landing-section">
            <div class="section-header">
                <div class="section-title">أسئلة شائعة</div>
                <div class="section-tag">FAQ</div>
            </div>
            <ul class="faq-list">
                <li><strong>هل المكان مناسب للعائلات؟</strong> نعم، SNOW LIWA مخصص للعائلات والشباب مع أجواء آمنة وممتعة.</li>
                <li><strong>هل يجب الحجز مسبقًا؟</strong> نعم، احجز وادفع أونلاين عبر موقعنا لتضمن مكانك وتحصل على تذكرتك فوراً.</li>
                <li><strong>أين موقعكم؟</strong> الموقع سري 🫣 – سيتم إرسال اللوكيشن بالتفصيل بعد تأكيد الدفع عبر الواتساب.</li>
                <li><strong>هل يمكن تعديل وقت الزيارة؟</strong> نعم، بالتواصل معنا قبل 24 ساعة من الموعد المحدد.</li>
                <li><strong>هل التذكرة قابلة للاسترجاع؟</strong> بعد تأكيد الحجز لا يمكن استرجاع المبلغ، ويمكن إعادة جدولة الموعد عند الحاجة.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_welcome():
    session_settings = st.session_state.get("settings", {}) or {}
    stored_settings = load_settings() or {}
    settings = {**stored_settings, **session_settings}

    hero_subtitle = settings.get("hero_subtitle", "تجربة شتوية في قلب الظفرة")
    hero_intro_ar = settings.get(
        "hero_intro_paragraph",
        "مشروع شبابي إماراتي يقدم أجواء شتوية للعائلات والشباب، من لعب الثلج إلى الشوكولاتة الساخنة."
    )
    hero_intro_en = settings.get(
        "hero_intro_paragraph_en",
        "Emirati youth project offering a cozy winter experience in the heart of Al Dhafra, mixing the charm of Liwa desert with snow, hot chocolate and warm hospitality."
    )

    ticket_price_value = float(settings.get("ticket_price", TICKET_PRICE))
    ticket_currency = settings.get("ticket_currency", "AED")
    max_tickets = int(settings.get("max_tickets_per_booking", 20))

    working_days = settings.get("working_days", "كل أيام الأسبوع")
    working_hours = settings.get("working_hours", "4:00pm - 12:00am")
    location_label = settings.get(
        "location_label", "الموقع: منطقة الظفرة – ليوا")
    family_label = settings.get("family_label", "مناسب للعائلات والأطفال")

    hero_image_path = settings.get("hero_image_path")
    poster_path = settings.get(
        "ticket_poster_path", "assets/ticket_poster.png")

    # Anchors for navigation
    booking_anchor = st.empty()
    about_anchor = st.empty()

    # Header
    st.markdown(
        """
        <div class="landing-header">
            <div class="landing-logo">
                <div class="landing-logo-mark">SL</div>
                <div>
                    <div class="landing-logo-text-main">SNOW LIWA</div>
                    <div class="landing-logo-text-sub arabic-text">تجربة الثلج في قلب ليوا</div>
                </div>
            </div>
            <div class="landing-header-cta">
                <a class="btn btn-primary" href="#booking_section">🎟️ احجز تذكرتك الآن</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-spacer' style='height:1.6rem'></div>",
                unsafe_allow_html=True)

    # Hero
    st.markdown("<div class='hero-section'>", unsafe_allow_html=True)
    col1, col2 = st.columns([1.2, 1], gap="large")
    with col1:
        badges = [
            "❄️ Snow Experience",
            f"🕒 {working_hours}",
            f"📍 {location_label}",
            f"👨‍👩‍👧‍👦 {family_label}",
        ]
        badge_html = "".join(
            f"<span class='badge-soft'>{badge}</span>" for badge in badges if badge)
        st.markdown(
            f"""
            <div class="hero-content">
                <div class="hero-title-main">SNOW LIWA</div>
                <div class="hero-subtitle-main arabic-text">{hero_subtitle}</div>
                <div class="snow-experience-pill">
                    <span class="snow-experience-pill-icon">❄️</span>
                    <span>تجربة الثلج</span>
                </div>
                <p class="hero-subtext arabic-text">{hero_intro_ar}</p>
                <p class="hero-subtext en english-text">{hero_intro_en}</p>
                <div class="hero-cta-row">
                    <a class="btn btn-primary" href="#booking_section">احجز تذكرتك الآن</a>
                    <a class="btn btn-outline" href="#about_section">تعرف علينا أكثر</a>
                </div>
                <div class="hero-badges">{badge_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='section-spacer' style='height:1.2rem'></div>", unsafe_allow_html=True)
        st.markdown("<div class='activity-buttons'>", unsafe_allow_html=True)
        pill1, pill2 = st.columns(2, gap="small")
        with pill1:
            if st.button("ICE SKATING", key="ice_skating_pill", use_container_width=True):
                st.session_state["selected_activity"] = "ice_skating"
        with pill2:
            if st.button("SLADDING", key="sladding_pill", use_container_width=True):
                st.session_state["selected_activity"] = "sladding"
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        hero_image = resolve_media_path(hero_image_path)
        poster_image = resolve_media_path(poster_path)
        image_path = hero_image or poster_image
        if image_path:
            try:
                img_bytes = image_path.read_bytes()
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                mime = "image/png"
                suffix = image_path.suffix.lower()
                if suffix in {".jpg", ".jpeg"}:
                    mime = "image/jpeg"
                elif suffix == ".webp":
                    mime = "image/webp"
                st.markdown(
                    f"""
                    <div class="poster-box">
                        <img src="data:{mime};base64,{img_b64}" alt="SNOW LIWA" />
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown(
                    "<div class='poster-box'>Poster image placeholder – ضع صورة SNOW LIWA هنا</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div class='poster-box'>Poster image placeholder – ضع صورة SNOW LIWA هنا</div>",
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)

    # Scroll anchors using session flags if set
    if st.session_state.get("scroll_to_booking"):
        st.session_state.pop("scroll_to_booking")
        booking_anchor.empty()
        st.markdown("<div id='booking_section'></div>", unsafe_allow_html=True)
        st.write("")
    if st.session_state.get("scroll_to_about"):
        st.session_state.pop("scroll_to_about")
        about_anchor.empty()
        st.markdown("<div id='about_section'></div>", unsafe_allow_html=True)
        st.write("")

    st.markdown("<div class='section-spacer'></div>", unsafe_allow_html=True)

    # Experience section
    total_price_text = f"{ticket_price_value:,.0f} {ticket_currency}"
    st.markdown(
        f"""
        <div class="landing-section" id="experience_section">
            <div class="section-header">
                <div class="section-title">تجربة الثلج ❄️</div>
                <div class="section-tag">SNOW EXPERIENCE</div>
            </div>
            <div class="section-body">
                <p class="arabic-text">
                    في مبادرةٍ فريدةٍ تمنح الزوّار أجواءً ثلجية ممتعة وتجربةً استثنائية لا تُنسى،
                    يمكنكم الاستمتاع بمشاهدة تساقط الثلج، وتجربة مشروب الشوكولاتة الساخنة، مع ضيافةٍ
                    راقية تشمل الفراولة ونافورة الشوكولاتة.
                </p>
                <p class="en english-text">
                    In a unique initiative that gives visitors a pleasant snowy atmosphere and an exceptional
                    and unforgettable experience, you can enjoy watching the snowfall, and try a hot chocolate
                    drink, with high-end hospitality including strawberries and a chocolate fountain.
                </p>
                <div class="ticket-card">
                    <div class="ticket-price">🎟️ Entrance ticket: {total_price_text} per person</div>
                    <span class="pill-highlight">تذكرة الدخول فقط بـ {int(ticket_price_value)} درهمًا</span>
                    <ul class="steps-list">
                        <li>① املأ نموذج الحجز بالمعلومات المطلوبة.</li>
                        <li>② ادفع أونلاين عبر Ziina ({int(ticket_price_value)} {ticket_currency} لكل شخص).</li>
                        <li>③ استلم تذكرتك الإلكترونية مباشرة بعد الدفع.</li>
                        <li>④ تواصل معنا على الواتساب لاستلام لوكيشن الموقع السري 🫣</li>
                    </ul>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-spacer'></div>", unsafe_allow_html=True)

    # Booking section
    booking_anchor.markdown(
        '<div id="booking_section"></div>', unsafe_allow_html=True)
    st.markdown('<div class="landing-section landing-booking">',
                unsafe_allow_html=True)
    st.markdown(
        """
        <div class="section-header">
            <div class="section-title">إحجز تذكرتك الآن</div>
            <div class="section-tag">Book your ticket</div>
        </div>
        <div class="pill-highlight">احجز الآن وادفع أونلاين – احصل على تذكرتك فوراً</div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1.1, 0.9], gap="large")

    with col_left:
        st.markdown('<div class="booking-form-wrapper">',
                    unsafe_allow_html=True)
        with st.form("booking_form"):
            name = st.text_input("Name / الاسم الكامل")
            phone = st.text_input("Phone / رقم الهاتف (واتساب)")
            tickets = st.number_input(
                "Number of tickets / عدد التذاكر",
                min_value=1,
                max_value=max_tickets,
                value=1,
            )
            notes = st.text_area(
                "Notes (optional) / ملاحظات اختيارية", height=80)
            submitted = st.form_submit_button(
                "Confirm booking / إصدار التذكرة")
        st.markdown('</div>', unsafe_allow_html=True)

        selected_activity = st.session_state.get("selected_activity")
        activity_labels = {
            "ice_skating": "Ice Skating", "sladding": "Sladding"}
        if selected_activity in activity_labels:
            st.info(f"تم اختيار النشاط: {activity_labels[selected_activity]}")

    with col_right:
        st.markdown('<div class="poster-card">', unsafe_allow_html=True)
        if poster_path and os.path.exists(poster_path):
            try:
                img_bytes = Path(poster_path).read_bytes()
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                st.markdown(
                    f"""
                    <div class="ticket-poster-wrapper">
                        <img src="data:image/png;base64,{img_b64}" class="ticket-poster-img" alt="SNOW LIWA Poster" />
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown(
                    "<div class='poster-box'>Poster image placeholder – ضع صورة SNOW LIWA هنا</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div class='poster-box'>No poster image configured yet. Please upload one from Settings.</div>",
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        if not name.strip() or not phone.strip():
            st.error("الرجاء إدخال الاسم ورقم الهاتف.")
        else:
            df = load_bookings()
            booking_id = get_next_booking_id(df)
            total_amount = float(tickets) * ticket_price_value

            payment_intent_id = None
            payment_status = None
            redirect_url = None
            if has_ziina_configured():
                with st.spinner("جاري إنشاء رابط الدفع عبر Ziina..."):
                    pi = create_payment_intent(total_amount, booking_id, name)
                if pi:
                    payment_intent_id = str(
                        pi.get("id")
                        or pi.get("payment_intent_id")
                        or pi.get("paymentIntent", {}).get("id")
                        or ""
                    )
                    payment_status = pi.get("status")
                    redirect_url = (
                        pi.get("redirect_url")
                        or pi.get("hosted_page_url")
                        or pi.get("next_action", {}).get("redirect_url")
                    )

            new_row = {
                "booking_id": booking_id,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": name,
                "phone": phone,
                "tickets": int(tickets),
                "ticket_price": ticket_price_value,
                "total_amount": total_amount,
                "status": "paid" if payment_status == "completed" else "pending",
                "payment_intent_id": payment_intent_id,
                "payment_status": payment_status or "pending",
                "redirect_url": redirect_url,
                "notes": notes,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_bookings(df)

            ticket_text = build_ticket_text(
                booking_id, name, phone, int(tickets), total_amount)
            ticket_bytes = ticket_text.encode("utf-8")

            st.success(
                f"تم إنشاء الحجز! رقم الحجز: **{booking_id}** والمبلغ **{total_amount:.2f} {ticket_currency}**. "
                "يمكنك تنزيل التذكرة أو إرسالها مباشرة."
            )
            # Show a manual payment CTA button so the customer proceeds when ready.
            if redirect_url:
                safe_redirect = html.escape(redirect_url, quote=True)
                st.markdown(
                    f"""
                    <div class="payment-cta-wrapper">
                        <a class="btn btn-primary" href="{safe_redirect}" target="_blank" rel="noopener noreferrer">
                            💳 إكمال الدفع (Ziina)
                        </a>
                    </div>
                    <div class="footer-note">اضغط الزر لإكمال الدفع عبر Ziina في نافذة جديدة.</div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("الدفع عند الوصول أو سيتم مشاركة رابط الدفع لاحقاً.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-spacer'></div>", unsafe_allow_html=True)

    about_anchor.markdown('<div id="about_section"></div>',
                          unsafe_allow_html=True)
    render_who_we_are()

    st.markdown("<div class='section-spacer'></div>", unsafe_allow_html=True)
    render_customer_info_panel()

    # Hidden admin unlock: tap the subtle button five times, then enter passcode to access dashboard.
    trigger_cols = st.columns([0.96, 0.04])
    with trigger_cols[1]:
        if st.button("···", key="admin_secret_tap", help="", width="stretch"):
            st.session_state.admin_taps = st.session_state.get("admin_taps", 0) + 1
            if st.session_state.admin_taps >= 5:
                st.session_state.show_admin_password = True
                st.session_state.admin_unlock_error = ""
                st.session_state.admin_taps = 0

    if st.session_state.get("show_admin_password"):
        st.info("إدخال رمز الإدارة للانتقال إلى لوحة التحكم.")
        if st.session_state.get("admin_unlock_error"):
            st.error(st.session_state.admin_unlock_error)
        with st.form("admin_unlock_form", clear_on_submit=True):
            admin_code = st.text_input("Admin passcode", type="password")
            unlock = st.form_submit_button("دخول لوحة التحكم")
        if unlock:
            if admin_code.strip() == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.session_state.page = "Dashboard"
                st.session_state.show_admin_password = False
                st.session_state.admin_taps = 0
                st.session_state.admin_unlock_error = ""
                st.rerun()
            else:
                st.session_state.admin_unlock_error = "رمز غير صحيح. حاول مرة أخرى."
                st.session_state.show_admin_password = True

    is_admin = st.session_state.get("is_admin", False)
    if is_admin:
        with st.expander("Debug / Admin Tools", expanded=False):
            if st.button("🔍 Test Ziina API"):
                test_ziina_credentials()


def render_who_we_are():
    st.markdown('<div class="landing-section">', unsafe_allow_html=True)
    st.markdown('<div class="snow-title">SNOW LIWA</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">من نحن ؟ · Who are we</div>',
        unsafe_allow_html=True,
    )

    ar_text = """
مشروع شبابي إماراتي من قلب منطقة الظفرة، يقدم تجربة شتوية فريدة تجمع بين أجواء ليوا الساحرة ولمسات من البساطة والجمال.

يهدف المشروع إلى خلق مساحة ترفيهية ودّية للعائلات والشباب تجمع بين ديكورات شتوية فاخرة وضيافة راقية من مشروب الشوكولاتة الساخنة إلى نافورة الشوكولاتة والفراولة الطازجة.
نحن في تطوّر مستمر بدعم الجهات المحلية وروح الشباب الإماراتي الطموح.
"""

    en_title = "Who are we?"
    en_text = """
Emirati youth project from the heart of Al Dhafra region. It offers a unique winter experience that combines the charming atmosphere of Liwa with touches of simplicity and beauty.

The project aims to create a friendly entertainment space for families and young people that combines luxurious winter decoration and high-end hospitality, from hot chocolate drinks to fresh strawberries and a chocolate fountain. We are constantly developing with the support of local authorities and the spirit of ambitious Emirati youth.
"""

    st.markdown('<div class="dual-column">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="arabic"><strong>من نحن ؟</strong><br><br>{ar_text}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="english"><strong>{en_title}</strong><br><br>{en_text}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_experience():
    st.markdown('<div class="landing-section">', unsafe_allow_html=True)
    st.markdown('<div class="snow-title">SNOW LIWA</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">Snow Experience · تجربة الثلج</div>',
        unsafe_allow_html=True,
    )

    ar_block = """
تجربة الثلج ❄️

في مبادرةٍ فريدةٍ تمنح الزوّار أجواءً ثلجية ممتعة وتجربةً استثنائية لا تُنسى، يمكنكم الاستمتاع بمشاهدة تساقط الثلج، وتجربة مشروب الشوكولاتة الساخنة، مع ضيافةٍ راقية تشمل الفراولة ونافورة الشوكولاتة.

بعد الدفع عن طريق تصوير الباركود تواصلوا معنا واستلموا تذكرتكم ولوكيشن موقعنا السري 🫣
"""

    en_block = """
In a unique initiative that gives visitors a pleasant snowy atmosphere and an exceptional and unforgettable experience,
you can enjoy watching the snowfall, and try a hot chocolate drink, with high-end hospitality including strawberries
and a chocolate fountain.

After paying by photographing the barcode, contact us and receive your ticket and the location of our secret spot 🫣
"""

    st.markdown('<div class="dual-column">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="arabic">{ar_block}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="english">{en_block}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        f"<div class='ticket-price'>🎟️ Entrance Ticket: <strong>{TICKET_PRICE} AED</strong> per person</div>",
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)


def render_contact():
    st.markdown('<div class="landing-section">', unsafe_allow_html=True)
    st.markdown('<div class="snow-title">SNOW LIWA</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">Contact · تواصل معنا</div>',
        unsafe_allow_html=True,
    )

    ar_contact = """
📞 **رقم الهاتف**<br>
050 113 8781<br><br>
للتواصل عبر الواتساب فقط أو من خلال حسابنا في الإنستغرام:<br>
**snowliwa**
"""

    en_contact = """
📞 **Phone**<br>
050 113 8781<br><br>
WhatsApp only or through Instagram:<br>
**snowliwa**
"""

    st.markdown('<div class="dual-column">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="arabic">{ar_contact}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="english">{en_contact}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        "<div class='center-btn'><a class='btn btn-primary' href='https://wa.me/971501138781' target='_blank'>تواصل عبر واتساب</a></div>",
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)


def render_dashboard():
    st.markdown('<div class="snow-title">SNOW LIWA</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">Dashboard · لوحة التحكم</div>',
        unsafe_allow_html=True,
    )

    df = load_bookings()
    if df.empty:
        st.info("No bookings yet.")
        return

    # Sync from Ziina
    if st.button("🔄 Sync payment status from Ziina"):
        with st.spinner("Syncing with Ziina..."):
            df = sync_payments_from_ziina(df)
        st.success("Sync completed.")

    # KPIs
    total_bookings = len(df)
    total_tickets = df["tickets"].sum()
    total_amount = df["total_amount"].sum()
    total_paid = df[df["status"] == "paid"]["total_amount"].sum()
    total_pending = df[df["status"] == "pending"]["total_amount"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total bookings", int(total_bookings))
    c2.metric("Total tickets", int(total_tickets))
    c3.metric("Total amount (AED)", f"{total_amount:,.0f}")
    c4.metric("Paid (AED)", f"{total_paid:,.0f}")
    c5.metric("Pending (AED)", f"{total_pending:,.0f}")

    st.markdown("### Update booking status manually")
    booking_ids = df["booking_id"].tolist()
    selected_id = st.selectbox("Select booking", booking_ids)
    new_status = st.selectbox("New status", ["pending", "paid", "cancelled"])
    if st.button("Save status"):
        df.loc[df["booking_id"] == selected_id, "status"] = new_status
        save_bookings(df)
        st.success(f"Updated {selected_id} to status: {new_status}")

    st.markdown("### Last 25 bookings")
    st.dataframe(
        df.sort_values("created_at", ascending=False).head(25),
        use_container_width=True,
    )


def render_payment_result(result: str, pi_id: str):
    """Page shown when user returns from Ziina with pi_id in URL."""
    df = load_bookings()
    row = df[df["payment_intent_id"].astype(str) == str(pi_id)]
    booking_id = row["booking_id"].iloc[0] if not row.empty else None

    pi_status = None
    if pi_id:
        pi = get_payment_intent(pi_id)
        if pi:
            pi_status = pi.get("status")
            if not row.empty:
                idx = row.index[0]
                df.loc[df.index == idx, "payment_status"] = pi_status
                if pi_status == "completed":
                    df.loc[df.index == idx, "status"] = "paid"
                elif pi_status in ("failed", "canceled"):
                    df.loc[df.index == idx, "status"] = "cancelled"
                save_bookings(df)

    final_status = (pi_status or result or "").lower()

    status_map = {
        "completed": {
            "cls": "success",
            "icon": "✅",
            "title": "تم الدفع بنجاح!",
            "details": (
                "شكرًا لاختياركم <strong>SNOW LIWA</strong> ❄️<br>"
                "تذكرتك الإلكترونية جاهزة! تواصل معنا عبر الواتساب مع رقم الحجز لاستلام اللوكيشن السري."
            ),
        },
        "pending": {
            "cls": "info",
            "icon": "ℹ️",
            "title": "عملية الدفع قيد المعالجة",
            "details": (
                "عملية الدفع قيد المعالجة أو لم تكتمل بعد.<br>"
                "لو تأكدت أن المبلغ تم خصمه، أرسل لنا رقم الحجز لنراجع الحالة."
            ),
        },
        "failed": {
            "cls": "error",
            "icon": "❌",
            "title": "لم تتم عملية الدفع",
            "details": (
                "لم تتم عملية الدفع أو تم إلغاؤها.<br>"
                "يمكنك إعادة المحاولة من صفحة الحجز أو التواصل معنا للمساعدة."
            ),
        },
        "unknown": {
            "cls": "warning",
            "icon": "⚠️",
            "title": "تعذر التأكد من حالة الدفع",
            "details": "يرجى التواصل معنا على الواتساب مع رقم الحجز للتحقق من العملية.",
        },
    }

    if final_status in ("completed", "success"):
        status_key = "completed"
    elif final_status in ("pending", "requires_payment_instrument", "requires_user_action"):
        status_key = "pending"
    elif final_status in ("failed", "canceled", "cancel", "failure"):
        status_key = "failed"
    else:
        status_key = "unknown"

    meta = status_map[status_key]
    booking_html = (
        f"<div class='payment-info-row'><strong>Booking ID:</strong> {html.escape(str(booking_id))}</div>"
        if booking_id
        else ""
    )
    pi_html = (
        f"<div class='payment-info-row'><strong>Payment Intent ID:</strong> {html.escape(str(pi_id))}</div>"
        if pi_id
        else ""
    )

    home_url = get_ziina_app_base_url()

    st.markdown('<div class="payment-container">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="payment-logo-title">SNOW LIWA</div>
        <div class="payment-subtitle">نتيجة الدفع · Payment Result</div>
        <div class="status-box {meta['cls']}">
            <div class="status-icon">{meta['icon']}</div>
            <div class="status-message">{meta['title']}</div>
            <div class="status-details">{meta['details']}</div>
        </div>
        {booking_html}
        {pi_html}
        <div class="payment-footer">📱 للتواصل: واتساب أو إنستغرام <strong>snowliwa</strong> مع ذكر رقم الحجز.</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="payment-actions">', unsafe_allow_html=True)

    ticket_bytes = None
    if status_key == "completed" and not row.empty:
        try:
            row_data = row.iloc[0]
            ticket_text = build_ticket_text(
                row_data["booking_id"],
                row_data["name"],
                row_data["phone"],
                int(row_data["tickets"]),
                float(row_data["total_amount"]),
            )
            ticket_bytes = ticket_text.encode("utf-8")
        except Exception:
            ticket_bytes = None

    if ticket_bytes:
        st.download_button(
            "🎟️ تنزيل التذكرة",
            data=ticket_bytes,
            file_name=f"{booking_id}_ticket.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.markdown(
        f"<a class='secondary' href='{home_url}' target='_self'>العودة إلى صفحة SNOW LIWA الرئيسية</a>",
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# MAIN APP
# =========================


def render_settings():
    st.markdown('<div class="snow-title">Settings</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="subheading">App Settings · إعدادات التطبيق</div>',
                unsafe_allow_html=True)

    # --- Initialize settings dict in session_state ---
    if "settings" not in st.session_state:
        st.session_state["settings"] = {}
    settings = st.session_state["settings"]

    # Use temp variables for all controls
    temp = {}
    st.header("1. Background")
    bg_modes = ["preset1", "preset2", "preset3", "uploaded"]
    temp["background_mode"] = st.selectbox("Background mode", bg_modes, index=bg_modes.index(
        settings.get("background_mode", "preset1")), key="bg_mode")
    if temp["background_mode"] == "uploaded":
        uploaded_bg = st.file_uploader("Upload background image", type=[
                                       "png", "jpg", "jpeg"], key="bg_upload")
        if uploaded_bg:
            bg_path = "assets/bg_uploaded.png"
            with open(bg_path, "wb") as f:
                f.write(uploaded_bg.read())
            temp["background_image_path"] = bg_path
            st.success("Background image uploaded!")
        else:
            temp["background_image_path"] = settings.get(
                "background_image_path")
    else:
        temp["background_image_path"] = None

    st.header("1A. Background Appearance")
    temp["background_brightness"] = st.slider("Background brightness", min_value=0.2, max_value=1.5, value=float(
        settings.get("background_brightness", 1.0)), step=0.05, key="bg_brightness")
    temp["background_blur"] = st.slider("Background blur (px)", min_value=0, max_value=20, value=int(
        settings.get("background_blur", 0)), step=1, key="bg_blur")

    st.header("2. Hero Image")
    hero_sources = ["assets/hero_main.png", "uploaded", "none"]
    temp["hero_image_source"] = st.selectbox("Hero image source", hero_sources, index=hero_sources.index(
        settings.get("hero_image_source", "assets/hero_main.png")), key="hero_img_src")
    if temp["hero_image_source"] == "uploaded":
        uploaded_hero = st.file_uploader("Upload hero image", type=[
                                         "png", "jpg", "jpeg"], key="hero_upload")
        if uploaded_hero:
            hero_path = "assets/hero_uploaded.png"
            with open(hero_path, "wb") as f:
                f.write(uploaded_hero.read())
            temp["hero_image_path"] = hero_path
            st.success("Hero image uploaded!")
        else:
            temp["hero_image_path"] = settings.get("hero_image_path")
    else:
        temp["hero_image_path"] = temp["hero_image_source"] if temp["hero_image_source"] != "none" else None
    temp["hero_side"] = st.selectbox("Hero image side", ["left", "right"], index=[
                                     "left", "right"].index(settings.get("hero_side", "left")), key="hero_side")
    temp["hero_card_size"] = st.selectbox("Hero card size", ["small", "medium", "large"], index=[
                                          "small", "medium", "large"].index(settings.get("hero_card_size", "medium")), key="hero_card_size")

    st.header("3. Theme")
    accent_options = {"snow_blue": "#7ecbff", "purple": "#a259ff",
                      "pink": "#ff6fae", "warm_yellow": "#e0b455"}
    temp["accent_color"] = st.selectbox("Accent color", list(accent_options.keys()), index=list(
        accent_options.keys()).index(settings.get("accent_color", "snow_blue")), key="accent_color")
    temp["theme_mode"] = st.selectbox("Theme mode", ["light", "snow_night"], index=[
                                      "light", "snow_night"].index(settings.get("theme_mode", "light")), key="theme_mode")

    st.header("4. Text Content")
    temp["hero_subtitle"] = st.text_input("Hero subtitle", value=settings.get(
        "hero_subtitle", "تجربة شتوية في قلب الظفرة"), key="hero_subtitle")
    temp["hero_intro_paragraph"] = st.text_area("Hero intro paragraph", value=settings.get(
        "hero_intro_paragraph", "مشروع شبابي إماراتي يقدم أجواء ليوا الشتوية للعائلات والشباب، من لعب الثلج إلى الشوكولاتة الساخنة."), key="hero_intro_paragraph")
    temp["working_days"] = st.text_input("Working days (badge)", value=settings.get(
        "working_days", "كل أيام الأسبوع"), key="working_days")
    temp["working_hours"] = st.text_input("Working hours (badge)", value=settings.get(
        "working_hours", "4:00pm - 12:00am"), key="working_hours")

    st.header("5. Tickets")
    temp["ticket_price"] = st.number_input("Ticket price", min_value=0, value=int(
        settings.get("ticket_price", 175)), key="ticket_price")
    temp["ticket_currency"] = st.text_input("Ticket currency", value=settings.get(
        "ticket_currency", "AED"), key="ticket_currency")
    temp["max_tickets_per_booking"] = st.number_input("Max tickets per booking", min_value=1, value=int(
        settings.get("max_tickets_per_booking", 10)), key="max_tickets_per_booking")

    st.header("6. Payment / API")
    temp["payment_mode"] = st.selectbox("Payment mode", ["cash_on_arrival", "payment_link"], index=[
                                        "cash_on_arrival", "payment_link"].index(settings.get("payment_mode", "cash_on_arrival")), key="payment_mode")
    temp["payment_base_url_or_template"] = st.text_input("Payment base URL or template", value=settings.get(
        "payment_base_url_or_template", ""), key="payment_base_url_or_template")
    st.caption("API key/token must be set in st.secrets, not here.")

    st.header("7. WhatsApp")
    temp["whatsapp_enabled"] = st.checkbox("Enable WhatsApp confirmation", value=settings.get(
        "whatsapp_enabled", False), key="whatsapp_enabled")
    temp["whatsapp_phone"] = st.text_input(
        "WhatsApp phone (no +)", value=settings.get("whatsapp_phone", "971501234567"), key="whatsapp_phone")
    temp["whatsapp_message_template"] = st.text_area("WhatsApp message template", value=settings.get(
        "whatsapp_message_template", "مرحبا، أود تأكيد حجز رقم {booking_id} لعدد {tickets} تذاكر في SNOW LIWA."), key="whatsapp_message_template")

    st.header("8. Snow Effect")
    temp["snow_enabled"] = st.checkbox("Enable snow effect", value=settings.get(
        "snow_enabled", False), key="snow_enabled")
    temp["snow_density"] = st.selectbox("Snow density", ["light", "medium", "heavy"], index=[
                                        "light", "medium", "heavy"].index(settings.get("snow_density", "medium")), key="snow_density")

    st.header("9. Contact Badges")
    temp["location_label"] = st.text_input("Location label", value=settings.get(
        "location_label", "الموقع: منطقة الظفرة – ليوا"), key="location_label")
    temp["season_label"] = st.text_input("Season label", value=settings.get(
        "season_label", "الموسم: شتاء 2025"), key="season_label")
    temp["family_label"] = st.text_input("Family label", value=settings.get(
        "family_label", "مناسب للعائلات والأطفال"), key="family_label")

    # --- Ticket Poster Upload Section ---
    st.header("10. Ticket Poster Image")
    poster_file = st.file_uploader("Upload ticket poster (PNG, JPG, JPEG)", type=[
                                   "png", "jpg", "jpeg"], key="poster_upload")
    if poster_file:
        poster_rel_path = Path("assets") / "ticket_poster.png"
        poster_path = BASE_DIR / poster_rel_path
        poster_path.parent.mkdir(parents=True, exist_ok=True)
        with open(poster_path, "wb") as f:
            f.write(poster_file.read())
        settings["ticket_poster_path"] = str(poster_rel_path)
        from settings_utils import save_settings
        save_settings(settings)
        st.success("Poster image uploaded and saved!")
    resolved_poster = resolve_media_path(settings.get("ticket_poster_path", ""))
    if resolved_poster:
        st.image(str(resolved_poster), use_column_width=True)
    else:
        st.info("No poster image configured yet.")

    if st.button("💾 حفظ الإعدادات / Save Settings", type="primary"):
        st.session_state["settings"].update(temp)
        st.success("تم حفظ جميع الإعدادات بنجاح! / All settings saved.")


def main():
    init_state()
    ensure_data_file()
    set_background(BACKGROUND_IMAGE_PATH)
    inject_base_css()
    page_nav()

    query = get_query_params()
    result_param = _normalize_query_value(
        query.get("result")) if query else None
    pi_id_param = _normalize_query_value(query.get("pi_id")) if query else None

    # If coming back from Ziina with pi_id -> show payment result
    if result_param and pi_id_param:
        st.markdown(
            '<div class="page-container"><div class="page-card">',
            unsafe_allow_html=True,
        )
        render_payment_result(result_param, pi_id_param)
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    st.markdown('<div class="page-container"><div class="page-card">',
                unsafe_allow_html=True)
    if st.session_state.page == "Welcome":
        render_welcome()
    elif st.session_state.page == "Who we are":
        render_who_we_are()
    elif st.session_state.page == "Experience":
        render_experience()
    elif st.session_state.page == "Contact":
        render_contact()
    elif st.session_state.page == "Dashboard":
        render_dashboard()
    elif st.session_state.page == "Settings":
        render_settings()
    st.markdown("</div></div>", unsafe_allow_html=True)

    # Debug/diagnostics area
    with st.expander("Debug / Admin Tools"):
        if st.button("🔍 Test Ziina API"):
            test_ziina_credentials()


if __name__ == "__main__":
    main()
