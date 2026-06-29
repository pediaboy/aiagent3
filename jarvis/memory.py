"""
memory.py — SQLite-based short-term + long-term memory
"""
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from jarvis.config import DB_PATH, SHORT_TERM_LIMIT, MAX_LONG_TERM

logger = logging.getLogger(__name__)


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if not exist."""
    conn = _connect()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS short_term (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT NOT NULL,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            ts        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS long_term (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT NOT NULL,
            fact      TEXT NOT NULL,
            category  TEXT DEFAULT 'general',
            ts        TEXT NOT NULL,
            UNIQUE(user_id, fact)
        );

        CREATE TABLE IF NOT EXISTS tool_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT NOT NULL,
            tool      TEXT NOT NULL,
            args      TEXT,
            result    TEXT,
            ts        TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    logger.info("DB initialized at %s", DB_PATH)


# ─── Short-term (conversation history) ───────────────────────────────────────

def add_message(user_id: str, role: str, content: str):
    """Append a message to short-term history."""
    conn = _connect()
    c = conn.cursor()
    ts = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO short_term (user_id, role, content, ts) VALUES (?,?,?,?)",
        (str(user_id), role, content, ts)
    )
    conn.commit()
    # Prune: keep only last SHORT_TERM_LIMIT per user
    c.execute("""
        DELETE FROM short_term WHERE user_id=? AND id NOT IN (
            SELECT id FROM short_term WHERE user_id=? ORDER BY id DESC LIMIT ?
        )
    """, (str(user_id), str(user_id), SHORT_TERM_LIMIT))
    conn.commit()
    conn.close()


def get_history(user_id: str) -> list:
    """Return conversation history as list of dicts {role, content}."""
    conn = _connect()
    c = conn.cursor()
    rows = c.execute(
        "SELECT role, content FROM short_term WHERE user_id=? ORDER BY id ASC",
        (str(user_id),)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "parts": [{"text": r["content"]}]} for r in rows]


def clear_history(user_id: str):
    conn = _connect()
    conn.execute("DELETE FROM short_term WHERE user_id=?", (str(user_id),))
    conn.commit()
    conn.close()


# ─── Long-term (persistent facts) ────────────────────────────────────────────

def save_fact(user_id: str, fact: str, category: str = "general"):
    """Save a permanent fact about the user."""
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO long_term (user_id, fact, category, ts) VALUES (?,?,?,?)",
            (str(user_id), fact, category, ts)
        )
        conn.commit()
        # Prune oldest if over limit
        conn.execute("""
            DELETE FROM long_term WHERE user_id=? AND id NOT IN (
                SELECT id FROM long_term WHERE user_id=? ORDER BY id DESC LIMIT ?
            )
        """, (str(user_id), str(user_id), MAX_LONG_TERM))
        conn.commit()
    except Exception as e:
        logger.error("save_fact: %s", e)
    finally:
        conn.close()


def get_facts(user_id: str, category: str = None) -> list:
    """Return list of long-term facts."""
    conn = _connect()
    if category:
        rows = conn.execute(
            "SELECT fact FROM long_term WHERE user_id=? AND category=? ORDER BY id DESC",
            (str(user_id), category)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT fact FROM long_term WHERE user_id=? ORDER BY id DESC",
            (str(user_id),)
        ).fetchall()
    conn.close()
    return [r["fact"] for r in rows]


def delete_fact(user_id: str, fact: str):
    conn = _connect()
    conn.execute("DELETE FROM long_term WHERE user_id=? AND fact=?", (str(user_id), fact))
    conn.commit()
    conn.close()


def get_all_facts_text(user_id: str) -> str:
    facts = get_facts(user_id)
    if not facts:
        return ""
    return "Fakta tentang user:\n" + "\n".join(f"- {f}" for f in facts)


# ─── Tool log ─────────────────────────────────────────────────────────────────

def log_tool(user_id: str, tool: str, args: dict, result: str):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO tool_log (user_id, tool, args, result, ts) VALUES (?,?,?,?,?)",
        (str(user_id), tool, json.dumps(args, ensure_ascii=False), str(result)[:500], ts)
    )
    conn.commit()
    conn.close()
