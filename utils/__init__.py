# Compatibility shim: expose `utils` API from `utility` package
from ..utility import io as io
from ..utility import bookings as bookings
from ..utility import ui as ui
from ..utility import ziina as ziina
from ..utility import helpers as helpers

# Re-export common helpers
load_settings = io.load_settings
save_settings = io.save_settings
ensure_all_required_dirs = io.ensure_all_required_dirs
ensure_all_required_files = io.ensure_all_required_files
get_image_path = io.get_image_path

# Bookings helpers
load_bookings = bookings.load_bookings
save_bookings = bookings.save_bookings
get_next_booking_id = bookings.get_next_booking_id
ensure_bookings_file_exists = bookings.ensure_bookings_file_exists

# Ziina helpers
has_ziina_configured = ziina.has_ziina_configured
create_payment_intent = ziina.create_payment_intent
get_payment_intent = ziina.get_payment_intent

# UI
encode_image_base64 = ui.encode_image_base64
inject_base_css = ui.inject_base_css
build_ticket_text = ui.build_ticket_text
