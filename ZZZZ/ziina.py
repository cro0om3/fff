import logging
import requests
from typing import Optional
from .io import load_settings
import os


def _secrets_ziina():
    try:
        import streamlit as st
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
    test_mode = s.get('test_mode') or ziina.get("test", False)
    return access_token, app_base_url, test_mode


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
