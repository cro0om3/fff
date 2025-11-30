import base64
from datetime import datetime
from pathlib import Path
import urllib.parse
import os
from settings_utils import load_settings

import pandas as pd
import requests
import streamlit as st

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
import logging

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

PAGES = {
    "Welcome": "welcome",
    "Who we are": "who",
    "Experience": "experience",
    "Contact": "contact",
    "Dashboard (Admin)": "dashboard",
}

ADMIN_PASSWORD = "snowadmin123"  # Legacy; login removed

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
                "payment_status",  # requires_payment_instrument / completed / failed...
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
        st.error("Ziina API key is missing from st.secrets. Please add access_token under [ziina].")
        return None

    amount_fils = int(round(amount_aed * 100))  # Ziina expects amount in fils (cents equivalent)
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
    logging.info(f"[ZIINA] Headers: {{'Authorization': 'Bearer ***', 'Content-Type': 'application/json'}}")
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
        st.error("Ziina API key is missing from st.secrets. Please add access_token under [ziina].")
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
        st.error("Ziina API key is missing from st.secrets. Please add access_token under [ziina].")
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
    logging.info(f"[ZIINA-TEST] Headers: {{'Authorization': 'Bearer ***', 'Content-Type': 'application/json'}}")
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
            df.at[idx, "status"] = "paid"
            updated = True
        elif status in ("failed", "canceled"):
            df.at[idx, "status"] = "cancelled"
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
        background: linear-gradient(180deg, {bg_color} 0%, #ffffff 60%, #fbe9d0 100%);
        color: #18324a;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def inject_base_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        :root {
            --baby-blue: #eaf6ff;
            --snow-white: #ffffff;
            --desert-sand: #fbe9d0;
            --accent-blue: #7ecbff;
            --accent-gold: #e0b455;
            --text-main: #18324a;
            --glass-bg: rgba(255,255,255,0.55);
            --glass-border: rgba(126,203,255,0.22);
        }
        html { font-size: 70%; }
        * { font-family: 'Inter', 'SF Pro Display', system-ui, -apple-system, sans-serif; }
        body { color: var(--text-main); }
        .stApp {
            background: linear-gradient(180deg, var(--baby-blue) 0%, var(--snow-white) 60%, var(--desert-sand) 100%);
            color: var(--text-main);
        }
        .page-container {
            max-width: 1180px;
            margin: 0 auto;
            padding: 0.8rem 0.75rem 1.6rem;
        }
        .page-card {
            max-width: 1180px;
            width: 100%;
            background: var(--glass-bg);
            box-shadow: 0 18px 48px rgba(126,203,255,0.10);
            border: 1.5px solid var(--glass-border);
            border-radius: 24px;
            padding: 0;
            backdrop-filter: blur(10px);
        }
        @media (max-width: 800px) {
            .page-card { padding: 0; }
        }
        .hero-card {
            position: relative;
            border-radius: 30px;
            overflow: hidden;
            min-height: 480px;
            background-size: cover;
            background-position: center;
            box-shadow: 0 18px 48px rgba(126,203,255,0.18);
            isolation: isolate;
            background: var(--glass-bg);
            border: 1.5px solid var(--glass-border);
        }
        .sticker {
            position: absolute;
            z-index: 3;
            font-size: 2.8rem;
            opacity: 0.9;
            filter: drop-shadow(0 6px 12px rgba(0,0,0,0.18));
            pointer-events: none;
        }
        .sticker.kid { top: 62%; left: 12%; font-size: 3.1rem; }
        .sticker.snowman { top: 24%; right: 14%; }
        .sticker.deer { bottom: 12%; right: 30%; }
        .sticker.mitten { top: 12%; left: 8%; }
        .hero-layer {
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.0) 0%, var(--baby-blue) 100%);
            z-index: 1;
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
            color: var(--text-main);
            text-align: center;
        }
        .hero-nav {
            display: flex;
            gap: 1.8rem;
            letter-spacing: 0.18em;
            font-size: 0.9rem;
            text-transform: uppercase;
            color: var(--accent-blue);
        }
        .hero-title {
            font-size: 3.6rem;
            line-height: 1.05;
            letter-spacing: 0.18em;
            font-weight: 800;
            color: var(--accent-blue);
            text-shadow: 0 10px 24px rgba(126,203,255,0.14);
        }
        .hero-tags {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            justify-content: center;
        }
        .hero-pill {
            background: rgba(255,255,255,0.92);
            color: var(--accent-blue);
            padding: 0.6rem 1.4rem;
            border-radius: 999px;
            font-weight: 700;
            box-shadow: 0 10px 30px rgba(126,203,255,0.16);
            letter-spacing: 0.08em;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin: 1.1rem 0 1.0rem 0;
        }
        .info-card {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 18px;
            padding: 1.1rem 1.25rem;
            box-shadow: 0 12px 30px rgba(126,203,255,0.08);
        }
        .info-card h3 {
            margin: 0 0 0.4rem 0;
            font-size: 1.1rem;
            letter-spacing: 0.08em;
            color: var(--accent-blue);
        }
        .info-card p {
            margin: 0;
            color: #4f6077;
            line-height: 1.5;
        }
        .section-card {
            background: var(--snow-white);
            border: 1px solid var(--glass-border);
            border-radius: 18px;
            padding: 1.4rem 1.4rem 1.2rem 1.4rem;
            box-shadow: 0 14px 34px rgba(126,203,255,0.10);
            margin-top: 1rem;
        }
        .snow-title {
            text-align: center;
            font-size: 3rem;
            font-weight: 700;
            letter-spacing: 0.30em;
            margin-bottom: 0.4rem;
            color: var(--accent-blue);
        }
        .subheading {
            text-align: center;
            font-size: 0.95rem;
            opacity: 0.8;
            margin-bottom: 2rem;
        }
        .arabic {
            direction: rtl;
            text-align: right;
            font-size: 1rem;
            line-height: 1.8;
        }
        .english {
            direction: ltr;
            text-align: left;
            font-size: 0.98rem;
            line-height: 1.7;
        }
        .dual-column {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2.25rem;
        }
        @media (max-width: 800px) {
            .dual-column { grid-template-columns: 1fr; }
            .hero-card { min-height: 360px; }
            .hero-title { font-size: 2.6rem; }
            .hero-nav { gap: 0.7rem; font-size: 0.78rem; }
            .hero-content { padding: 2rem 1.2rem; gap: 1rem; }
        }
        .ticket-price {
            font-size: 1.2rem;
            font-weight: 700;
            margin-top: 1rem;
            color: var(--accent-gold);
        }
        .stButton>button {
            border-radius: 999px;
            padding: 0.7rem 1.6rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            background: linear-gradient(120deg, var(--accent-gold), #ffe9b0);
            color: #18324a;
            border: none;
            box-shadow: 0 10px 30px rgba(224,180,85,0.18);
            transition: transform 0.15s ease, box-shadow 0.2s ease;
        }
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 16px 32px rgba(126,203,255,0.22);
        }
        .stButton>button:focus {
            outline: 2px solid var(--accent-blue);
        }
        .center-btn {
            display: flex;
            justify-content: center;
            margin-top: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .footer-note {
            text-align: center;
            font-size: 0.8rem;
            opacity: 0.75;
            margin-top: 1.5rem;
        }
        .snow-experience-card {
            width: 100%;
            background: radial-gradient(circle at top, #FFFFFF 0%, #F6FBFF 55%, #EDF6FF 100%);
            border-radius: 32px;
            padding: 2.4rem 2.2rem 2.6rem;
            box-shadow: 0 20px 45px rgba(0, 72, 140, 0.10);
            box-sizing: border-box;
            direction: rtl;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .snow-experience-small-title {
            position: absolute;
            top: 1.6rem;
            left: 2.2rem;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            color: #76B4FF;
            direction: ltr;
        }

        .snow-experience-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.55rem 1.3rem;
            border-radius: 999px;
            border: 1px solid #BEE4FF;
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 10px 25px rgba(0, 80, 156, 0.09);
            font-size: 18px;
            font-weight: 700;
            color: #27A4FF;
            margin-bottom: 1.4rem;
            margin-top: 0.4rem;
        }

        .snow-experience-pill-icon {
            font-size: 20px;
        }

        .snow-experience-text {
            max-width: 520px;
            margin: 0 auto;
            font-size: 16px;
            line-height: 1.9;
            color: #234266;
            font-weight: 500;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "Welcome"


def page_nav():
    with st.sidebar:
        st.title("SNOW LIWA")
        nav = st.radio(
            "Navigation",
            ["Welcome", "Who we are", "Experience", "Contact", "Dashboard", "Settings"],
            index=["Welcome", "Who we are", "Experience", "Contact", "Dashboard", "Settings"].index(st.session_state.page) if st.session_state.page in ["Welcome", "Who we are", "Experience", "Contact", "Dashboard", "Settings"] else 0,
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
    # Customer info panel with tabs, styled as a card
    st.markdown('<div class="section-card" style="margin-top:1.5rem;">', unsafe_allow_html=True)
    tabs = st.tabs(["من نحن؟", "موقعنا", "سياسة الحجز", "الأسئلة الشائعة"])
    with tabs[0]:
        st.markdown(
            '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
            'مشروع شبابي إماراتي من قلب منطقة الظفرة.<br>'
            'يقدم تجربة شتوية فريدة تجمع بين أجواء ليوا الساحرة ولمسات من البساطة والجمال.'
            '<br><br>'
            '# TODO: insert FHD\'s final about-us text here'
            '</div>',
            unsafe_allow_html=True,
        )
    with tabs[1]:
        st.markdown(
            '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
            'سيتم مشاركة موقع Snow Liwa بالتفصيل بعد تأكيد الحجز عبر واتساب. 🗺️📍'
            '</div>',
            unsafe_allow_html=True,
        )
    with tabs[2]:
        st.markdown(
            (
                '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
                '<ul style="padding-right:1.2em;">'
                '<li>التذكرة صالحة للاستخدام في اليوم المحدد فقط.</li>'
                '<li>بعد تأكيد الحجز لا يمكن استرجاع المبلغ.</li>'
                '<li>يمكنكم تعديل وقت الزيارة بالتواصل معنا قبل 24 ساعة.</li>'
                '</ul>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )
    with tabs[3]:
        st.markdown(
            '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
            '<b>هل يمكنني استرجاع المبلغ بعد الحجز؟</b><br>لا، بعد تأكيد الحجز لا يمكن استرجاع المبلغ.<br><br>'
            '<b>كيف أحصل على موقع Snow Liwa؟</b><br>سيتم إرسال الموقع عبر واتساب بعد تأكيد الحجز.<br><br>'
            '<b>هل يمكن تعديل وقت الزيارة؟</b><br>نعم، بالتواصل معنا قبل 24 ساعة من الموعد المحدد.<br><br>'
            '<b>هل التذكرة تشمل جميع الأنشطة؟</b><br>نعم، التذكرة تشمل جميع الأنشطة المتوفرة في اليوم المحدد.'
            '</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

def render_welcome():
    settings = st.session_state.get("settings", {})
    bg_img_path = settings.get("background_image_path")
    bg_brightness = settings.get("background_brightness", 1.0)
    bg_blur = settings.get("background_blur", 0)
    bg_opacity = settings.get("background_opacity", 1.0)
    hero_img_path = settings.get("hero_image_path")
    hero_side = settings.get("hero_side", "left")
    hero_card_size = settings.get("hero_card_size", "medium")
    accent_color = settings.get("accent_color", "snow_blue")
    theme_mode = settings.get("theme_mode", "light")
    hero_subtitle = settings.get("hero_subtitle", "تجربة شتوية في قلب الظفرة")
    hero_intro_paragraph = settings.get("hero_intro_paragraph", "مشروع شبابي إماراتي يقدم أجواء ليوا الشتوية للعائلات والشباب، من لعب الثلج إلى الشوكولاتة الساخنة.")

    # --- Section anchors for scroll/jump ---
    booking_anchor = st.empty()
    about_anchor = st.empty()

    # --- HERO LAYOUT ---
    col1, col2 = st.columns([1.15, 1], gap="large")
    with col1:
        st.markdown(f"""
        <div class='hero-content' style='align-items: flex-start; text-align: right;'>
            <div style='margin-bottom: 0.5rem;'></div>
            <div class='hero-title' style='font-size:3.2rem; letter-spacing:0.18em; color:var(--accent-blue); font-weight:800;'>SNOW LIWA</div>
            <div style='font-size:1.6rem; color:#18324a; font-weight:600; margin-bottom:0.2rem;'>تجربة شتوية في قلب الظفرة</div>
            <div class='arabic' style='margin-bottom:1.2rem; font-size:1.1rem; max-width:420px;'>
                مشروع شبابي إماراتي يقدم أجواء ليوا الشتوية للعائلات والشباب، من لعب الثلج إلى الشوكولاتة الساخنة.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- CTAs ---
        cta1, cta2 = st.columns([1.2, 1.1], gap="small")
        with cta1:
            if st.button("احجز تذكرتك الآن", key="cta_book", use_container_width=True):
                st.session_state["scroll_to_booking"] = True
                st.rerun()
        with cta2:
            if st.button("تعرف علينا أكثر", key="cta_about", use_container_width=True):
                st.session_state["scroll_to_about"] = True
                st.rerun()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # --- ICE SKATING / SLADDING pills ---
        pill1, pill2 = st.columns([1,1], gap="small")
        with pill1:
            if st.button("ICE SKATING", key="ice_skating_pill", use_container_width=True):
                st.session_state["selected_activity"] = "ice_skating"
        with pill2:
            if st.button("SLADDING", key="sladding_pill", use_container_width=True):
                st.session_state["selected_activity"] = "sladding"

        with col2:
                # Custom snow experience cards: Arabic and English
                st.markdown("""
                <style>
                .snow-experience-card {
                        width: 100%;
                        background: radial-gradient(circle at top, #FFFFFF 0%, #F6FBFF 55%, #EDF6FF 100%);
                        border-radius: 32px;
                        padding: 2.4rem 2.2rem 2.6rem;
                        box-shadow: 0 20px 45px rgba(0, 72, 140, 0.10);
                        box-sizing: border-box;
                        text-align: center;
                        position: relative;
                        overflow: hidden;
                        margin-bottom: 1.2rem;
                }
                .snow-experience-card.arabic { direction: rtl; }
                .snow-experience-card.english { direction: ltr; }
                .snow-experience-small-title {
                        position: absolute;
                        top: 1.6rem;
                        left: 2.2rem;
                        font-size: 14px;
                        font-weight: 700;
                        letter-spacing: 0.25em;
                        text-transform: uppercase;
                        color: #76B4FF;
                        direction: ltr;
                }
                .snow-experience-pill {
                        display: inline-flex;
                        align-items: center;
                        gap: 0.5rem;
                        padding: 0.55rem 1.3rem;
                        border-radius: 999px;
                        border: 1px solid #BEE4FF;
                        background: rgba(255, 255, 255, 0.95);
                        box-shadow: 0 10px 25px rgba(0, 80, 156, 0.09);
                        font-size: 18px;
                        font-weight: 700;
                        color: #27A4FF;
                        margin-bottom: 1.4rem;
                        margin-top: 0.4rem;
                }
                .snow-experience-pill-icon {
                        font-size: 20px;
                }
                .snow-experience-text {
                        max-width: 520px;
                        margin: 0 auto;
                        font-size: 16px;
                        line-height: 1.9;
                        color: #234266;
                        font-weight: 500;
                }
                </style>
                <div class="snow-experience-card arabic">
                    <div class="snow-experience-small-title">
                        SNOW LIWA
                    </div>
                    <div style="margin-top: 1.2rem;"></div>
                    <div class="snow-experience-pill">
                        <span class="snow-experience-pill-icon">❄️</span>
                        <span>تجربة الثلج</span>
                    </div>
                    <p class="snow-experience-text">
                        في مبادرةٍ فريدةٍ تمنح الزوّار أجواءً ثلجيةً ممتعة وتجربةً استثنائية لا تُنسى،
                        يمكنكم الاستمتاع بمشاهدة تساقُط الثلج، وتجربة مشروب الشوكولاتة الساخنة،
                        مع ضيافةٍ راقية تشمل الفراولة ونافورة الشوكولاتة.
                        تذكرة الدخول فقط بـ ١٧٥ درهمًا.
                    </p>
                </div>
                <div class="snow-experience-card english">
                    <div class="snow-experience-small-title">
                        SNOW LIWA
                    </div>
                    <div style="margin-top: 1.2rem;"></div>
                    <div class="snow-experience-pill">
                        <span class="snow-experience-pill-icon">❄️</span>
                        <span>Snow Experience</span>
                    </div>
                    <p class="snow-experience-text">
                        In a unique initiative that gives visitors a pleasant snowy atmosphere and an exceptional and unforgettable experience, you can enjoy watching the snowfall, and try a hot chocolate drink, with high-end hospitality including strawberries and a chocolate fountain. The entrance ticket is only AED 175.
                    </p>
                </div>
                """, unsafe_allow_html=True)

    # --- SCROLL/JUMP LOGIC ---
    if st.session_state.get("scroll_to_booking"):
        st.session_state.pop("scroll_to_booking")
        booking_anchor.empty()
        st.markdown("<div id='booking_section'></div>", unsafe_allow_html=True)
        st.write("")  # force scroll
    if st.session_state.get("scroll_to_about"):
        st.session_state.pop("scroll_to_about")
        about_anchor.empty()
        st.markdown("<div id='about_section'></div>", unsafe_allow_html=True)
        st.write("")

    # --- BOOKING SECTION (anchor for scroll) ---
    booking_anchor.markdown('<div id="booking_section"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### 🎟️ Book your ticket")
    st.write(f"Entrance ticket: **{TICKET_PRICE} AED** per person.")

    # Pre-select activity if chosen in hero
    selected_activity = st.session_state.get("selected_activity")
    activity_options = ["ice_skating", "sladding"]
    activity_labels = {"ice_skating": "Ice Skating", "sladding": "Sladding"}
    if selected_activity in activity_options:
        st.info(f"تم اختيار النشاط: {activity_labels[selected_activity]}")

    # Load poster path from settings
    settings = load_settings()
    poster_path = settings.get("ticket_poster_path", "assets/ticket_poster.png")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<div class="ticket-card">', unsafe_allow_html=True)
        with st.form("booking_form"):
            name = st.text_input("Name / الاسم الكامل")
            phone = st.text_input("Phone / رقم الهاتف (واتساب)")
            tickets = st.number_input("Number of tickets / عدد التذاكر", 1, 20, 1)
            notes = st.text_area("Notes (optional) / ملاحظات اختيارية", height=70)
            # Optionally show activity selection if needed in future
            submitted = st.form_submit_button("Confirm booking / إصدار التذكرة")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="ticket-card ticket-card-poster">', unsafe_allow_html=True)
        if poster_path and os.path.exists(poster_path):
            with open(poster_path, "rb") as f:
                img_bytes = f.read()
            import base64
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            st.markdown(
                f'''
                <div class="ticket-poster-wrapper">
                    <img src="data:image/png;base64,{img_b64}" class="ticket-poster-img" />
                </div>
                ''',
                unsafe_allow_html=True,
            )
        else:
            st.write("No poster image configured yet. Please upload one from the Settings page.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Add CSS for card and image fit
    st.markdown(
        '''<style>
        .ticket-card {
            background: #FFFFFF;
            border-radius: 24px;
            padding: 1.8rem 1.6rem 2rem;
            box-shadow: 0 20px 40px rgba(15, 72, 122, 0.08);
            height: 100%;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }
        .ticket-card-poster {
            justify-content: center;
        }
        .ticket-poster-wrapper {
            width: 100%;
            height: 307px; /* fixed height requested */
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.5rem;
            overflow: hidden;
        }
        .ticket-poster-img {
            max-width: 100%;
            max-height: 307px; /* ensure image never exceeds container */
            width: auto;
            height: auto;
            object-fit: contain;
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
            display: block;
            margin: 0 auto;
        }
        </style>''',
        unsafe_allow_html=True
    )

    if "submitted" in locals() and submitted:
        if not name.strip() or not phone.strip():
            st.error("الرجاء إدخال الاسم ورقم الهاتف.")
        else:
            df = load_bookings()
            booking_id = get_next_booking_id(df)
            total_amount = float(tickets) * TICKET_PRICE

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
                "ticket_price": TICKET_PRICE,
                "total_amount": total_amount,
                "status": "paid" if payment_status == "completed" else "pending",
                "payment_intent_id": payment_intent_id,
                "payment_status": payment_status or "pending",
                "redirect_url": redirect_url,
                "notes": notes,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_bookings(df)

            ticket_text = build_ticket_text(booking_id, name, phone, int(tickets), total_amount)
            ticket_bytes = ticket_text.encode("utf-8")

            st.success(
                f"تم إنشاء الحجز! رقم الحجز: **{booking_id}** والمبلغ **{total_amount:.2f} AED**. "
                "يمكنك تنزيل التذكرة أو إرسالها مباشرة."
            )
            cta_ticket, cta_wa = st.columns(2, gap="small")
            with cta_ticket:
                st.download_button(
                    "⬇️ تنزيل التذكرة باسم العميل",
                    data=ticket_bytes,
                    file_name=f"{booking_id}_ticket.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with cta_wa:
                share_url = f"https://wa.me/?text={urllib.parse.quote(ticket_text)}"
                st.link_button(
                    "📲 إرسال التذكرة على واتساب",
                    share_url,
                    use_container_width=True,
                )

            if redirect_url:
                st.link_button("💳 إكمال الدفع (Ziina)", redirect_url, use_container_width=True)
            else:
                st.info("الدفع عند الوصول أو سيتم مشاركة رابط الدفع لاحقاً.")

    st.markdown("</div>", unsafe_allow_html=True)

    # --- INFO/ABOUT SECTION (anchor for scroll) ---
    about_anchor.markdown('<div id="about_section"></div>', unsafe_allow_html=True)
    render_customer_info_panel()

    # --- Debug/Admin Tools (below info panel, admin only) ---
    is_admin = st.session_state.get("is_admin", False)
    if is_admin:
        with st.expander("Debug / Admin Tools", expanded=False):
            if st.button("🔍 Test Ziina API"):
                test_ziina_credentials()


def render_who_we_are():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">من نحن ؟ · Who are we</div>',
        unsafe_allow_html=True,
    )

    ar_text = """
مشروع شبابي إماراتي من قلب منطقة الظفرة ، 

يقدم تجربة شتوية فريدة تجمع بين أجواء ليوا الساحرة ولمسات من البساطة والجمال . 

يهدف المشروع إلى خلق مساحة ترفيهية ودية للعائلات والشباب تجمع بين الديكور الشتوي الفخم والضيافة الراقية من مشروب الشوكولاتة الساخنة الي نافورة الشوكولاتة والفراولة الطازجة نحن نعمل على تطوير باستمرار بدعم من الجهات المحلية وروح الشباب الإماراتي الطموح .
"""

    en_title = "? Who are we"
    en_text = """
Emirati youth project from the heart of Al Dhafra region,

It offers a unique winter experience that combines the charming atmosphere of Liwa
with touches of simplicity and beauty.

The project aims to create a friendly entertainment space for families and young people
that combines luxurious winter decoration and high-end hospitality from hot chocolate
drink to the fresh chocolate and strawberry fountain. We are constantly developing
with the support of local authorities and the spirit of ambitious Emirati youth.
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
    st.markdown("</div>", unsafe_allow_html=True)


def render_experience():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">Snow Experience · تجربة الثلج</div>',
        unsafe_allow_html=True,
    )

    ar_block_1 = """
تجربة الثلج ❄️ 

في مبادرةٍ فريدةٍ تمنح الزوّار أجواءً ثلجية ممتعة وتجربةً استثنائية لا تُنسى، يمكنكم الاستمتاع بمشاهدة تساقط الثلج، وتجربة مشروب الشوكولاتة الساخنة، مع ضيافةٍ راقية تشمل الفراولة ونافورة الشوكولاتة.

تذكرة الدخول فقط بـ 175 درهمًا 
"""

    en_block_1 = """
In a unique initiative that gives visitors a pleasant snowy
atmosphere and an exceptional and unforgettable experience,
you can enjoy watching the snowfall, and try a hot chocolate
drink, with high-end hospitality including strawberries and a
chocolate fountain.

The entrance ticket is only AED 175
"""

    ar_block_2 = """
SNOW Liwa

بعد الدفع عن طريق تصوير الباركود تواصلو معانا واستلمو تذكرتكم ولوكيشن موقعنا السري 🫣
"""

    en_block_2 = """
SNOW Liwa

After paying by photographing the barcode, contact us and receive
your ticket and the location of our secret website 🫣
"""

    st.markdown('<div class="dual-column">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="arabic">{ar_block_1}<br><br>{ar_block_2}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="english">{en_block_1}<br><br>{en_block_2}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f'<div class="ticket-price">🎟️ Entrance Ticket: <strong>{TICKET_PRICE} AED</strong> per person</div>',
        unsafe_allow_html=True,
    )


def render_contact():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">Contact · تواصل معنا</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### 📞 Contact Us / تواصل معنا")

    ar_contact = """
**رقم الهاتف**

050 113 8781

للتواصل عبر الواتساب فقط أو من خلال حسابنا في الإنستغرام:
**snowliwa**
"""

    en_contact = """
**Phone**

050 113 8781

To contact WhatsApp only or on our Instagram account:

**snowliwa**
"""

    st.markdown('<div class="dual-column">', unsafe_allow_html=True)
    st.markdown(f'<div class="arabic">{ar_contact}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="english">{en_contact}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.write("You can later add direct WhatsApp links or Instagram buttons here.")


def render_dashboard():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
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
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subheading">Payment result · نتيجة الدفع</div>',
        unsafe_allow_html=True,
    )

    st.write(f"**Payment Intent ID:** `{pi_id}`")

    df = load_bookings()
    row = df[df["payment_intent_id"].astype(str) == str(pi_id)]
    booking_id = row["booking_id"].iloc[0] if not row.empty else None
    if booking_id:
        st.write(f"**Booking ID:** `{booking_id}`")

    pi_status = None
    if pi_id:
        pi = get_payment_intent(pi_id)
        if pi:
            pi_status = pi.get("status")
            if not row.empty:
                idx = row.index[0]
                df.at[idx, "payment_status"] = pi_status
                if pi_status == "completed":
                    df.at[idx, "status"] = "paid"
                elif pi_status in ("failed", "canceled"):
                    df.at[idx, "status"] = "cancelled"
                save_bookings(df)

    final_status = pi_status or result

    if final_status == "completed":
        st.success(
            "✅ تم الدفع بنجاح!\n\n"
            "شكرًا لاختياركم **SNOW LIWA** ❄️\n\n"
            "تواصلوا معنا عبر الواتساب مع رقم الحجز لاستلام التذكرة ولوكيشن الموقع."
        )
    elif final_status in ("pending", "requires_payment_instrument", "requires_user_action"):
        st.info(
            "ℹ️ عملية الدفع قيد المعالجة أو لم تكتمل بعد.\n\n"
            "لو تأكدت أن المبلغ تم خصمه، أرسل لنا رقم الحجز لنراجع الحالة."
        )
    elif final_status in ("failed", "canceled"):
        st.error(
            "❌ لم تتم عملية الدفع أو تم إلغاؤها.\n\n"
            "يمكنك إعادة المحاولة من صفحة الحجز أو التواصل معنا للمساعدة."
        )
    else:
        st.warning(
            "تعذر التأكد من حالة الدفع.\n\n"
            "يرجى التواصل معنا على الواتساب مع رقم الحجز للتحقق من العملية."
        )

    st.markdown("---")
    st.markdown(
        "📱 للتواصل: واتساب أو إنستغرام **snowliwa** مع ذكر رقم الحجز.",
    )

    st.markdown('<div class="center-btn">', unsafe_allow_html=True)
    st.link_button("Back to SNOW LIWA home", get_ziina_app_base_url(), use_container_width=False)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# MAIN APP
# =========================



def render_settings():
    st.markdown('<div class="snow-title">Settings</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheading">App Settings · إعدادات التطبيق</div>', unsafe_allow_html=True)

    # --- Initialize settings dict in session_state ---
    if "settings" not in st.session_state:
        st.session_state["settings"] = {}
    settings = st.session_state["settings"]

    # Use temp variables for all controls
    temp = {}
    st.header("1. Background")
    bg_modes = ["preset1", "preset2", "preset3", "uploaded"]
    temp["background_mode"] = st.selectbox("Background mode", bg_modes, index=bg_modes.index(settings.get("background_mode", "preset1")), key="bg_mode")
    if temp["background_mode"] == "uploaded":
        uploaded_bg = st.file_uploader("Upload background image", type=["png", "jpg", "jpeg"], key="bg_upload")
        if uploaded_bg:
            bg_path = "assets/bg_uploaded.png"
            with open(bg_path, "wb") as f:
                f.write(uploaded_bg.read())
            temp["background_image_path"] = bg_path
            st.success("Background image uploaded!")
        else:
            temp["background_image_path"] = settings.get("background_image_path")
    else:
        temp["background_image_path"] = None

    st.header("1A. Background Appearance")
    temp["background_brightness"] = st.slider("Background brightness", min_value=0.2, max_value=1.5, value=float(settings.get("background_brightness", 1.0)), step=0.05, key="bg_brightness")
    temp["background_blur"] = st.slider("Background blur (px)", min_value=0, max_value=20, value=int(settings.get("background_blur", 0)), step=1, key="bg_blur")

    st.header("2. Hero Image")
    hero_sources = ["assets/hero_main.png", "uploaded", "none"]
    temp["hero_image_source"] = st.selectbox("Hero image source", hero_sources, index=hero_sources.index(settings.get("hero_image_source", "assets/hero_main.png")), key="hero_img_src")
    if temp["hero_image_source"] == "uploaded":
        uploaded_hero = st.file_uploader("Upload hero image", type=["png", "jpg", "jpeg"], key="hero_upload")
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
    temp["hero_side"] = st.selectbox("Hero image side", ["left", "right"], index=["left", "right"].index(settings.get("hero_side", "left")), key="hero_side")
    temp["hero_card_size"] = st.selectbox("Hero card size", ["small", "medium", "large"], index=["small", "medium", "large"].index(settings.get("hero_card_size", "medium")), key="hero_card_size")

    st.header("3. Theme")
    accent_options = {"snow_blue": "#7ecbff", "purple": "#a259ff", "pink": "#ff6fae", "warm_yellow": "#e0b455"}
    temp["accent_color"] = st.selectbox("Accent color", list(accent_options.keys()), index=list(accent_options.keys()).index(settings.get("accent_color", "snow_blue")), key="accent_color")
    temp["theme_mode"] = st.selectbox("Theme mode", ["light", "snow_night"], index=["light", "snow_night"].index(settings.get("theme_mode", "light")), key="theme_mode")

    st.header("4. Text Content")
    temp["hero_subtitle"] = st.text_input("Hero subtitle", value=settings.get("hero_subtitle", "تجربة شتوية في قلب الظفرة"), key="hero_subtitle")
    temp["hero_intro_paragraph"] = st.text_area("Hero intro paragraph", value=settings.get("hero_intro_paragraph", "مشروع شبابي إماراتي يقدم أجواء ليوا الشتوية للعائلات والشباب، من لعب الثلج إلى الشوكولاتة الساخنة."), key="hero_intro_paragraph")
    temp["working_days"] = st.text_input("Working days (badge)", value=settings.get("working_days", "كل أيام الأسبوع"), key="working_days")
    temp["working_hours"] = st.text_input("Working hours (badge)", value=settings.get("working_hours", "4:00pm - 12:00am"), key="working_hours")

    st.header("5. Tickets")
    temp["ticket_price"] = st.number_input("Ticket price", min_value=0, value=int(settings.get("ticket_price", 175)), key="ticket_price")
    temp["ticket_currency"] = st.text_input("Ticket currency", value=settings.get("ticket_currency", "AED"), key="ticket_currency")
    temp["max_tickets_per_booking"] = st.number_input("Max tickets per booking", min_value=1, value=int(settings.get("max_tickets_per_booking", 10)), key="max_tickets_per_booking")

    st.header("6. Payment / API")
    temp["payment_mode"] = st.selectbox("Payment mode", ["cash_on_arrival", "payment_link"], index=["cash_on_arrival", "payment_link"].index(settings.get("payment_mode", "cash_on_arrival")), key="payment_mode")
    temp["payment_base_url_or_template"] = st.text_input("Payment base URL or template", value=settings.get("payment_base_url_or_template", ""), key="payment_base_url_or_template")
    st.caption("API key/token must be set in st.secrets, not here.")

    st.header("7. WhatsApp")
    temp["whatsapp_enabled"] = st.checkbox("Enable WhatsApp confirmation", value=settings.get("whatsapp_enabled", False), key="whatsapp_enabled")
    temp["whatsapp_phone"] = st.text_input("WhatsApp phone (no +)", value=settings.get("whatsapp_phone", "971501234567"), key="whatsapp_phone")
    temp["whatsapp_message_template"] = st.text_area("WhatsApp message template", value=settings.get("whatsapp_message_template", "مرحبا، أود تأكيد حجز رقم {booking_id} لعدد {tickets} تذاكر في SNOW LIWA."), key="whatsapp_message_template")

    st.header("8. Snow Effect")
    temp["snow_enabled"] = st.checkbox("Enable snow effect", value=settings.get("snow_enabled", False), key="snow_enabled")
    temp["snow_density"] = st.selectbox("Snow density", ["light", "medium", "heavy"], index=["light", "medium", "heavy"].index(settings.get("snow_density", "medium")), key="snow_density")


    st.header("9. Contact Badges")
    temp["location_label"] = st.text_input("Location label", value=settings.get("location_label", "الموقع: منطقة الظفرة – ليوا"), key="location_label")
    temp["season_label"] = st.text_input("Season label", value=settings.get("season_label", "الموسم: شتاء 2025"), key="season_label")
    temp["family_label"] = st.text_input("Family label", value=settings.get("family_label", "مناسب للعائلات والأطفال"), key="family_label")

    # --- Ticket Poster Upload Section ---
    st.header("10. Ticket Poster Image")
    poster_file = st.file_uploader("Upload ticket poster (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], key="poster_upload")
    if poster_file:
        poster_path = "assets/ticket_poster.png"
        os.makedirs(os.path.dirname(poster_path), exist_ok=True)
        with open(poster_path, "wb") as f:
            f.write(poster_file.read())
        settings["ticket_poster_path"] = poster_path
        from settings_utils import save_settings
        save_settings(settings)
        st.success("Poster image uploaded and saved!")
    if os.path.exists(settings.get("ticket_poster_path", "")):
        st.image(settings["ticket_poster_path"], use_column_width=True)
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
    result_param = _normalize_query_value(query.get("result")) if query else None
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

    st.markdown('<div class="page-container"><div class="page-card">', unsafe_allow_html=True)
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
