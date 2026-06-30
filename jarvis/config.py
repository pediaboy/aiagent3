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

# ── AI Providers ──────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")

# Models
GEMINI_MODEL   = os.getenv("GEMINI_MODEL",   "gemini-1.5-flash")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
GROQ_MODEL     = os.getenv("GROQ_MODEL",     "llama-3.1-8b-instant")

# ── Agent Settings ────────────────────────────────────────────────────────────
AGENT_NAME       = os.getenv("AGENT_NAME", "Pedia")
AGENT_PHONE      = os.getenv("AGENT_PHONE", "")  # diisi otomatis saat login

# ── Memory ────────────────────────────────────────────────────────────────────
SHORT_TERM_LIMIT = int(os.getenv("SHORT_TERM_LIMIT", "30"))
MAX_LONG_TERM    = int(os.getenv("MAX_LONG_TERM", "200"))

# ── Typing simulation ─────────────────────────────────────────────────────────
TYPING_WPM = int(os.getenv("TYPING_WPM", "300"))

# ── AI Router timeout ─────────────────────────────────────────────────────────
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "20"))

# ── Group settings defaults ───────────────────────────────────────────────────
GROUP_AI_ENABLED_DEFAULT = os.getenv("GROUP_AI_ENABLED_DEFAULT", "true").lower() == "true"

def validate():
    has_any_ai = bool(GEMINI_API_KEY or CEREBRAS_API_KEY or GROQ_API_KEY)
    if not has_any_ai:
        print("[CONFIG ERROR] Minimal satu AI provider harus di-set:")
        print("  GEMINI_API_KEY / CEREBRAS_API_KEY / GROQ_API_KEY")
        return False
    return True
