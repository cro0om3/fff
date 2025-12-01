"""Utilities to call Ziina Payment Intent API.

Configuration order of precedence:
- Streamlit `st.secrets['ziina']` if available
- `data/settings.json` under `apis.ziina`
- Environment variables `ZIINA_ACCESS_TOKEN` and `ZIINA_APP_BASE_URL`

Create `.streamlit/secrets.toml` with a `[ziina]` table to provide
`access_token`, `app_base_url`, and `test_mode` for local runs.
"""

import logging
import requests
from typing import Optional
from .io import load_settings
import os


def _secrets_ziina():
    try:
        import streamlit as st # type: ignore
        s = st.secrets.get('ziina', {}) if hasattr(st, 'secrets') else {}
        return s
    except Exception:
        return {}

ZIINA_API_BASE = "https://api-v2.ziina.com/api"


def _get_ziina_config():
    settings = load_settings()
    ziina = settings.get("apis", {}).get("ziina", {})
    # Prefer Streamlit secrets when available
    s = _secrets_ziina()
    access_token = s.get('access_token') or ziina.get('access_token') or os.environ.get('ZIINA_ACCESS_TOKEN')
    app_base_url = s.get('app_base_url') or ziina.get("app_base_url") or settings.get("payment_base_url_or_template") or os.environ.get('ZIINA_APP_BASE_URL', '')
    # Accept either `test_mode` (preferred) or older `test` flag in settings
    test_mode = s.get('test_mode') if 'test_mode' in s else (ziina.get('test_mode') if 'test_mode' in ziina else ziina.get('test', False))
    return access_token, app_base_url, bool(test_mode)


def get_ziina_access_token() -> Optional[str]:
    """Return configured Ziina access token or None."""
    token, _, _ = _get_ziina_config()
    return token


def get_ziina_app_base_url() -> str:
    """Return configured app base URL (may be empty string)."""
    _, base, _ = _get_ziina_config()
    return base or ""


def get_ziina_test_mode() -> bool:
    """Return whether Ziina test mode is enabled."""
    _, _, tm = _get_ziina_config()
    return bool(tm)


def get_ziina_config_summary() -> dict:
    """Return a small summary dict with masked token and config source info."""
    token, base, tm = _get_ziina_config()
    masked = None
    source = "unknown"
    if token:
        if token.startswith("REPLACE_") or token.startswith("PUT_"):
            masked = "(placeholder)"
        else:
            masked = token[:4] + "..." + token[-4:]
    else:
        masked = None
    # Determine source by checking st.secrets first, then settings, then env
    try:
        import streamlit as st # type: ignore
        if hasattr(st, 'secrets') and st.secrets.get('ziina'):
            source = 'st.secrets'
        else:
            source = 'settings_or_env'
    except Exception:
        source = 'settings_or_env'
    return {"access_token_masked": masked, "app_base_url": base, "test_mode": bool(tm), "source": source}


def show_ziina_debug_panel():
    """Show a small Streamlit panel with current Ziina config and a test button.

    This function imports `streamlit` lazily and is safe to call only from Streamlit UI code.
    It will not print or expose the full access token.
    """
    try:
        import streamlit as st # type: ignore
    except Exception:
        logging.error("Streamlit not available for debug panel")
        return

    st.header("Ziina configuration")
    summary = get_ziina_config_summary()
    st.write("**Access token (masked):**", summary.get("access_token_masked"))
    st.write("**App base URL:**", summary.get("app_base_url"))
    st.write("**Test mode:**", summary.get("test_mode"))
    st.write("**Config source:**", summary.get("source"))

    if st.button("Run Ziina credentials test (create test intent)"):
        access_token = get_ziina_access_token()
        if not access_token:
            st.error("Ziina access token not configured. Add it to .streamlit/secrets.toml or env vars.")
            return
        st.info("Running test payment intent (test mode)...")
        # perform a small test intent creation (1 AED)
        res = create_payment_intent(1.00, "TEST-DEBUG", "Debug User", api_debug=True)
        if not res:
            st.error("Test call failed — check logs or token validity.")
        else:
            st.success("Test call succeeded — response below")
            st.json(res)


def has_ziina_configured() -> bool:
    token, _, _ = _get_ziina_config()
    return bool(token)


def create_payment_intent(amount_aed: float, booking_id: str, customer_name: str, api_debug: bool = False) -> Optional[dict]:
    access_token, app_base_url, test_mode = _get_ziina_config()
    if not access_token:
        logging.error("Ziina access token not configured")
        return None

    amount_fils = int(round(amount_aed * 100))
    url = f"{ZIINA_API_BASE}/payment_intent"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    base_return = app_base_url.rstrip("/") if app_base_url else ""
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
    if api_debug:
        logging.info(f"[ZIINA] POST {url}")
        logging.info(f"[ZIINA] Payload (safe): {payload}")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.RequestException as e:
        logging.error(f"Error calling Ziina: {e}")
        return None
    if api_debug:
        logging.info(f"[ZIINA] Response status: {resp.status_code}")
        logging.info(f"[ZIINA] Response body: {resp.text}")
    if resp.status_code not in (200, 201):
        return None
    try:
        return resp.json()
    except Exception:
        return None


def get_payment_intent(pi_id: str, api_debug: bool = False) -> Optional[dict]:
    access_token, _, _ = _get_ziina_config()
    if not access_token:
        logging.error("Ziina access token not configured")
        return None
    url = f"{ZIINA_API_BASE}/payment_intent/{pi_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    if api_debug:
        logging.info(f"[ZIINA] GET {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as e:
        logging.error(f"Error calling Ziina: {e}")
        return None
    if api_debug:
        logging.info(f"[ZIINA] Response status: {resp.status_code}")
        logging.info(f"[ZIINA] Response body: {resp.text}")
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except Exception:
        return None
