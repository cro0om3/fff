import base64
from pathlib import Path
from datetime import datetime


def encode_image_base64(image_path: Path) -> str | None:
    if not image_path or not Path(image_path).is_file():
        return None
    try:
        return base64.b64encode(Path(image_path).read_bytes()).decode()
    except Exception:
        return None


def build_ticket_text(booking_id: str, name: str, phone: str, tickets: int, total_amount: float) -> str:
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


def inject_base_css(st):
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        .snow-title { font-size: 2.6rem; color: #1B76FF; font-weight:800; }
        .section-card { background: #fff; padding: 1rem; border-radius: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def set_background(st, bg_color="#eaf6ff"):
    css = f"""
    <style>
    .stApp {{
        background: linear-gradient(180deg, {bg_color} 0%, #ffffff 60%, #fbe9d0 100%);
        color: #18324a;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
