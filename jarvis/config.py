"""
config.py — Centralized configuration loader v3.0
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
DATA_DIR  = BASE_DIR / "data"
DB_PATH   = DATA_DIR / "memory.db"
LOG_PATH  = DATA_DIR / "agent.log"

load_dotenv(BASE_DIR / ".env")

# ── AI Providers ──────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")

GEMINI_MODEL   = os.getenv("GEMINI_MODEL",   "gemini-1.5-flash")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
GROQ_MODEL     = os.getenv("GROQ_MODEL",     "llama-3.1-8b-instant")

# ── Agent Settings ────────────────────────────────────────────
AGENT_NAME = os.getenv("AGENT_NAME", "Pedia")

# ── Memory ────────────────────────────────────────────────────
SHORT_TERM_LIMIT = int(os.getenv("SHORT_TERM_LIMIT", "30"))
MAX_LONG_TERM    = int(os.getenv("MAX_LONG_TERM", "200"))

# ── Conversation timing ───────────────────────────────────────
TYPING_WPM        = int(os.getenv("TYPING_WPM", "250"))
MIN_TYPING_MS     = int(os.getenv("MIN_TYPING_MS", "1000"))   # 1s minimum
MAX_TYPING_MS     = int(os.getenv("MAX_TYPING_MS", "15000"))  # 15s maximum
READ_RECEIPT_DELAY = float(os.getenv("READ_RECEIPT_DELAY", "0.5"))  # detik

# ── AI Timeout ────────────────────────────────────────────────
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "25"))

# ── Dashboard ─────────────────────────────────────────────────
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "changeme123")

# ── Multi-Session ─────────────────────────────────────────────
DEFAULT_SESSION_ID = os.getenv("DEFAULT_SESSION_ID", "default")

def validate():
    has_any = bool(GEMINI_API_KEY or CEREBRAS_API_KEY or GROQ_API_KEY)
    if not has_any:
        print("[CONFIG ERROR] Isi minimal satu: GEMINI_API_KEY / CEREBRAS_API_KEY / GROQ_API_KEY")
        return False
    return True
