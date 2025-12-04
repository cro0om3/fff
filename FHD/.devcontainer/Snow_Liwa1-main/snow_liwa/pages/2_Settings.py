
import streamlit as st
import os
from ..settings_utils import load_settings, save_settings

st.set_page_config(page_title="Settings · SNOW LIWA", page_icon="⚙️", layout="wide")


st.markdown('<div class="qx-header">App Settings</div>', unsafe_allow_html=True)

# ...existing settings controls above...

# Contact Badges section (assume this is the last settings section)
# ...existing code for Contact Badges...

st.header("10. Ticket Poster Image")
settings = load_settings()
poster_file = st.file_uploader("Upload ticket poster (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], key="poster_upload")
if poster_file:
	poster_path = "assets/ticket_poster.png"
	os.makedirs(os.path.dirname(poster_path), exist_ok=True)
	with open(poster_path, "wb") as f:
		f.write(poster_file.read())
	settings["ticket_poster_path"] = poster_path
	save_settings(settings)
	st.success("Poster image uploaded and saved!")
if os.path.exists(settings.get("ticket_poster_path", "")):
	st.image(settings["ticket_poster_path"], use_column_width=True)
else:
	st.info("No poster image configured yet.")
