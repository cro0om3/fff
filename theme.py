import streamlit as st

def apply_snow_liwa_theme():
    """Apply Snow Liwa page config and global CSS theme.

    This function centralizes the visual styling used across the app.
    It intentionally does not touch any business logic or data handling.
    """
    try:
        st.set_page_config(
            page_title="SNOW LIWA",
            page_icon="❄️",
            layout="wide",
            initial_sidebar_state="collapsed",
        )
    except Exception:
        # set_page_config can only be called once; ignore if already set
        pass

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
        .page-container { max-width: 1180px; margin: 0 auto; padding: 0.8rem 0.75rem 1.6rem; }
        .page-card { max-width: 1180px; width: 100%; background: var(--glass-bg); box-shadow: 0 18px 48px rgba(126,203,255,0.10); border: 1.5px solid var(--glass-border); border-radius: 24px; padding: 0; backdrop-filter: blur(10px); }
        .section-card { padding: 2rem; margin-bottom: 1.6rem; border-radius: 18px; }
        .ticket-card { display: flex; flex-direction: column; gap: 1rem; }
        .ticket-card input, .ticket-card textarea, .ticket-card .stNumberInput, .ticket-card .stTextInput { margin-bottom: 0 !important; }
        .hero-title { font-size: 3.6rem; line-height: 1.05; letter-spacing: 0.18em; font-weight: 800; color: var(--accent-blue); }
        .snow-title { text-align: center; font-size: 3rem; font-weight: 700; letter-spacing: 0.30em; margin-bottom: 0.4rem; color: var(--accent-blue); }
        .subheading { text-align: center; font-size: 0.95rem; opacity: 0.8; margin-bottom: 2rem; }
        .arabic { direction: rtl; text-align: right; font-size: 1rem; line-height: 1.8; }
        .english { direction: ltr; text-align: left; font-size: 0.98rem; line-height: 1.7; }
        .dual-column { display: grid; grid-template-columns: 1fr 1fr; gap: 2.25rem; }
        @media (max-width: 800px) { .dual-column { grid-template-columns: 1fr; } .hero-title { font-size: 2.6rem; } }
        .center-btn { display: flex; justify-content: center; margin-top: 0.5rem; margin-bottom: 0.5rem; }
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
        .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 16px 32px rgba(126,203,255,0.22); }
        .stButton>button:focus { outline: 2px solid var(--accent-blue); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_snow_liwa_header(title: str, subtitle: str = ""):
    st.markdown(f"<div class='hero-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='subheading'>{subtitle}</div>", unsafe_allow_html=True)
