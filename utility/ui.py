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
    """Deprecated shim: prefer `apply_snow_liwa_theme()` in `snow_liwa.theme`.

    This function keeps backward compatibility for callers that directly
    depend on `inject_base_css(st)`. It will attempt to call the centralized
    theme and fall back to the old inline CSS if the theme cannot be imported.
    """
    try:
        # Prefer centralized theme
        try:
            from snow_liwa.theme import apply_snow_liwa_theme  # type: ignore
            apply_snow_liwa_theme()
            return
        except Exception:
            try:
                from theme import apply_snow_liwa_theme  # type: ignore
                apply_snow_liwa_theme()
                return
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: preserve the previous inline CSS if theme is not available
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        :root {
            --accent-blue: #8fc9ff;
            --title-blue: #9ed1ff;
            --panel-bg: rgba(255,255,255,0.95);
            --muted: #556677;
        }
        html { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
        .stApp {
            background: linear-gradient(180deg, #f6fbff 0%, #fff8f2 60%, #fff 100%);
            color: #18324a;
        }
        .page-container { max-width: 1180px; margin: 0 auto; padding: 2.4rem 1rem; }
        .site-title { text-align: center; margin-top: 0.6rem; margin-bottom: 0.6rem; }
        .site-title h1 { margin: 0; font-size: 3.2rem; letter-spacing: 0.6em; color: var(--title-blue); font-weight:800; }
        .site-sub { text-align: center; color: var(--muted); margin-bottom: 1.8rem; }
        .section-card { background: var(--panel-bg); padding: 1.25rem; border-radius: 18px; box-shadow: 0 14px 34px rgba(126,203,255,0.08); }
        .dual-column { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
        @media (max-width: 900px) { .dual-column { grid-template-columns: 1fr; } .site-title h1 { font-size: 2.4rem; letter-spacing: 0.45em; } }
        .arabic { direction: rtl; text-align: right; }
        .english { direction: ltr; text-align: left; }
        .ticket-poster-img { max-width: 100%; border-radius: 14px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
        .stButton>button { border-radius: 999px; padding: 0.6rem 1.2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_base_background():
    """Inject the shared Snow Liwa page background gradient.

    Use this on all secondary pages (not the main homepage) to ensure a
    consistent light-blue gradient background across the app.
    """
    css = """
    <style>
    .stApp {
        background: linear-gradient(180deg, var(--baby-blue, #eaf6ff) 0%, #ffffff 60%, #fbe9d0 100%);
        background-attachment: fixed;
    }
    </style>
    """
    try:
        # Prefer centralized theme application if available
        try:
            from snow_liwa.theme import apply_snow_liwa_theme  # type: ignore
            apply_snow_liwa_theme()
            return
        except Exception:
            try:
                from theme import apply_snow_liwa_theme  # type: ignore
                apply_snow_liwa_theme()
                return
            except Exception:
                pass
    except Exception:
        pass

    try:
        import streamlit as st # type: ignore
        st.markdown(css, unsafe_allow_html=True)
    except Exception:
        # Best-effort injection; if Streamlit isn't available just skip.
        pass


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


def inject_snow_only(st_obj=None, html_override: str | None = None):
    """Inject a full-page 'snow only' HTML/CSS snippet.
    If `html_override` is provided, it will be used; otherwise a default
    minimal snow-only template is injected. `st_obj` can be the Streamlit
    module or None (will import streamlit internally).
    """
    try:
        if st_obj is None:
            import streamlit as st  # type: ignore
            st_obj = st
    except Exception:
        st_obj = None

    default_html = r'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Snow LIWA - Snow Only</title>
<style>
body { margin: 0; padding: 0; min-height: 100vh; font-family: 'Poppins', Arial, sans-serif; background-color: #000; overflow: hidden; position: relative; }
.snowflake { position: fixed; top: -10px; z-index: 9999; user-select: none; pointer-events: none; animation-name: fall; animation-timing-function: linear; animation-iteration-count: infinite; opacity: 0.95; filter: drop-shadow(0 0 3px white); }
@keyframes fall { 0% { transform: translateY(-10vh) rotate(0deg); } 100% { transform: translateY(110vh) rotate(360deg); } }
.small { font-size: 14px; } .medium { font-size: 22px; } .large { font-size: 32px; }
.s1 { left: 8%; animation-duration: 7s; } .s2 { left: 22%; animation-duration: 9s; animation-delay: 1.5s; }
.s3 { left: 37%; animation-duration: 6s; animation-delay: 3s; } .s4 { left: 53%; animation-duration: 10s; animation-delay: 0.5s; }
.s5 { left: 68%; animation-duration: 8s; animation-delay: 2.2s; } .s6 { left: 84%; animation-duration: 11s; animation-delay: 4s; }
</style>
</head>
<body>
<div class="snowflake small s1">❄</div>
<div class="snowflake medium s2">❄</div>
<div class="snowflake small s3">❄</div>
<div class="snowflake large s4">❄</div>
<div class="snowflake medium s5">❄</div>
<div class="snowflake large s6">❄</div>
</body>
</html>'''

    content = html_override or default_html
    try:
        if st_obj is not None:
            st_obj.markdown(content, unsafe_allow_html=True)
    except Exception:
        # Best-effort — if we cannot import streamlit or render, silently ignore
        pass


def generate_ticket_pdf_from_template(booking_id: str, name: str, phone: str, tickets: int, total_amount: float, output_path: Path):
    """Generate a simple PDF ticket including the customer's name.
    Uses reportlab if available, otherwise writes a plain text fallback.
    """
    try:
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore
        PAGE = A4
    except Exception:
        canvas = None
        PAGE = (595.27, 841.89)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if canvas is None:
            # Fallback: write a text file with same name but .txt
            txt_path = output_path.with_suffix('.txt')
            lines = [
                f"SNOW LIWA — Booking Ticket",
                "--------------------------",
                f"Booking ID : {booking_id}",
                f"Name       : {name}",
                f"Phone      : {phone}",
                f"Tickets    : {tickets}",
                f"Total (AED): {total_amount:.2f}",
            ]
            txt_path.write_text("\n".join(lines), encoding="utf-8")
            return

        c = canvas.Canvas(str(output_path), pagesize=PAGE)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(70, 780, "Snow Liwa Ticket")
        c.setFont("Helvetica", 16)
        c.drawString(70, 740, f"الاسم: {name}")
        c.drawString(70, 710, f"رقم الحجز: {booking_id}")
        c.drawString(70, 680, f"الهاتف: {phone}")
        c.drawString(70, 650, f"عدد التذاكر: {tickets}")
        c.drawString(70, 620, f"المجموع: {total_amount:.2f} AED")
        c.showPage()
        c.save()
    except Exception:
        # ignore failures — leave fallback text or nothing
        return
