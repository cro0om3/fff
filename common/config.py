# Project-wide config paths and flags
import pathlib

ROOT_PATH = pathlib.Path(__file__).parent.parent.resolve()
DATA_PATH = ROOT_PATH / 'data'
ASSETS_PATH = ROOT_PATH / 'assets'

SETTINGS_FILE = DATA_PATH / 'settings.json'
BOOKINGS_FILE = DATA_PATH / 'bookings.xlsx'
PRODUCTS_FILE = DATA_PATH / 'products.xlsx'

DEFAULT_API_DEBUG = False
