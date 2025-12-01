import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ..app import render_settings

def main():
    render_settings()

if __name__ == "__main__":
    main()
