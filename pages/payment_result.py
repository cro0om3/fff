try:
import streamlit as st  # type: ignore
except ImportError:
    import sys
    import types
    st = types.ModuleType('streamlit')
    sys.modules['streamlit'] = st

# Add this import for type checking and IDE support
try:
    import streamlit as st  # type: ignore
except ImportError:
    import sys
    import types
    st = types.ModuleType('streamlit')
    sys.modules['streamlit'] = st
from ..app import render_payment_result

qp = st.experimental_get_query_params()
result = qp.get('result', [None])[0]
pi_id = qp.get('pi_id', [None])[0]

render_payment_result(result or '', pi_id or '')
