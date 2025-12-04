import streamlit as st  # type: ignore
from app import render_payment_result
try:
    from snow_liwa.theme import apply_snow_liwa_theme
except Exception:
    from theme import apply_snow_liwa_theme

# Apply the centralized theme for this page
try:
    apply_snow_liwa_theme()
except Exception:
    pass

qp = getattr(st, "query_params", None)
if qp is not None:
    qp_dict = qp.to_dict() if hasattr(qp, "to_dict") else dict(qp)
else:
    try:
        qp_dict = st.experimental_get_query_params()
    except Exception:
        qp_dict = {}

result = qp_dict.get('result', [None])[0] if isinstance(qp_dict.get('result', None), list) else qp_dict.get('result')
pi_id = qp_dict.get('pi_id', [None])[0] if isinstance(qp_dict.get('pi_id', None), list) else qp_dict.get('pi_id')

render_payment_result(result or '', pi_id or '')
