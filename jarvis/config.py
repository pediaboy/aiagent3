"""
config.py — Centralized configuration loader
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
DATA_DIR  = BASE_DIR / "data"
DB_PATH   = DATA_DIR / "memory.db"
LOG_PATH  = DATA_DIR / "agent.log"

load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
ALLOWED_USER_IDS = [int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip().isdigit()]
AGENT_NAME       = os.getenv("AGENT_NAME", "Pedia")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

SHORT_TERM_LIMIT = int(os.getenv("SHORT_TERM_LIMIT", "20"))
MAX_LONG_TERM    = int(os.getenv("MAX_LONG_TERM", "200"))

def validate():
    errors = []
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY tidak di-set di .env")
    if not TELEGRAM_TOKEN:
        errors.append("TELEGRAM_TOKEN tidak di-set di .env")
    if errors:
        for e in errors: print(f"[CONFIG ERROR] {e}")
        return False
    return True
