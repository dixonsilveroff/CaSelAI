import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("CAROUSELAI_DATA_DIR", BASE_DIR / "data")).resolve()

# Specific data directories
BRANDS_DIR = DATA_DIR / "brands"
FONTS_DIR = DATA_DIR / "fonts"
OUTPUT_DIR = DATA_DIR / "output"
SCRIPTS_DIR = DATA_DIR / "scripts"
DB_PATH = Path(os.getenv("CAROUSELAI_DB_PATH", DATA_DIR / "carouselai.db"))

# Default settings
DEFAULT_GEMINI_MODEL = os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_SLIDE_COUNT = int(os.getenv("DEFAULT_SLIDE_COUNT", "7"))

# Ensure essential directories exist
BRANDS_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
