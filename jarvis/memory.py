"""
memory.py — SQLite memory: short-term, long-term, user profile, group memory, logs
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
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = _connect()
    c = conn.cursor()
    c.executescript("""
        -- Short-term: conversation history per user/group
        CREATE TABLE IF NOT EXISTS short_term (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            context_id TEXT NOT NULL,   -- user_id atau group_id
            role       TEXT NOT NULL,   -- user | assistant
            sender     TEXT,            -- nama pengirim (untuk grup)
            content    TEXT NOT NULL,
            ts         TEXT NOT NULL
        );

        -- Long-term: fakta permanen per user
        CREATE TABLE IF NOT EXISTS long_term (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            context_id TEXT NOT NULL,
            fact       TEXT NOT NULL,
            category   TEXT DEFAULT 'general',
            ts         TEXT NOT NULL,
            UNIQUE(context_id, fact)
        );

        -- User profiles
        CREATE TABLE IF NOT EXISTS user_profile (
            phone      TEXT PRIMARY KEY,
            name       TEXT,
            last_seen  TEXT,
            msg_count  INTEGER DEFAULT 0,
            notes      TEXT DEFAULT ''
        );

        -- Group settings
        CREATE TABLE IF NOT EXISTS group_settings (
            group_id   TEXT PRIMARY KEY,
            group_name TEXT,
            ai_enabled INTEGER DEFAULT 1,
            ai_paused  INTEGER DEFAULT 0,
            provider   TEXT DEFAULT 'auto',
            created_at TEXT,
            updated_at TEXT
        );

        -- AI logs
        CREATE TABLE IF NOT EXISTS ai_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            context_id    TEXT,
            is_group      INTEGER DEFAULT 0,
            sender_phone  TEXT,
            sender_name   TEXT,
            prompt        TEXT,
            response      TEXT,
            provider      TEXT,
            model         TEXT,
            response_ms   INTEGER,
            retry_count   INTEGER DEFAULT 0,
            fallback_used INTEGER DEFAULT 0,
            error         TEXT,
            ts            TEXT
        );

        -- Tool log
        CREATE TABLE IF NOT EXISTS tool_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            context_id TEXT,
            tool       TEXT,
            args       TEXT,
            result     TEXT,
            ts         TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_short_context ON short_term(context_id);
        CREATE INDEX IF NOT EXISTS idx_long_context  ON long_term(context_id);
        CREATE INDEX IF NOT EXISTS idx_log_context   ON ai_log(context_id);
        CREATE INDEX IF NOT EXISTS idx_log_ts        ON ai_log(ts);
    """)
    conn.commit()
    conn.close()
    logger.info("DB initialized at %s", DB_PATH)


# ─── Short-term ───────────────────────────────────────────────────────────────

def add_message(context_id: str, role: str, content: str, sender: str = None):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO short_term (context_id, role, sender, content, ts) VALUES (?,?,?,?,?)",
        (context_id, role, sender, content, ts)
    )
    conn.commit()
    # Prune
    conn.execute("""
        DELETE FROM short_term WHERE context_id=? AND id NOT IN (
            SELECT id FROM short_term WHERE context_id=? ORDER BY id DESC LIMIT ?
        )
    """, (context_id, context_id, SHORT_TERM_LIMIT))
    conn.commit()
    conn.close()


def get_history(context_id: str, limit: int = None) -> list:
    conn = _connect()
    lim = limit or SHORT_TERM_LIMIT
    rows = conn.execute(
        "SELECT role, sender, content FROM short_term WHERE context_id=? ORDER BY id ASC",
        (context_id,)
    ).fetchall()
    conn.close()
    
    result = []
    for r in rows[-lim:]:
        if r["role"] == "user" and r["sender"]:
            content = r["sender"] + ": " + r["content"]
        else:
            content = r["content"]
        result.append({"role": r["role"], "content": content})
    return result


def clear_history(context_id: str):
    conn = _connect()
    conn.execute("DELETE FROM short_term WHERE context_id=?", (context_id,))
    conn.commit()
    conn.close()


def get_history_count(context_id: str) -> int:
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM short_term WHERE context_id=?", (context_id,)
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


# ─── Long-term ────────────────────────────────────────────────────────────────

def save_fact(context_id: str, fact: str, category: str = "general"):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO long_term (context_id, fact, category, ts) VALUES (?,?,?,?)",
            (context_id, fact, category, ts)
        )
        conn.commit()
        conn.execute("""
            DELETE FROM long_term WHERE context_id=? AND id NOT IN (
                SELECT id FROM long_term WHERE context_id=? ORDER BY id DESC LIMIT ?
            )
        """, (context_id, context_id, MAX_LONG_TERM))
        conn.commit()
    except Exception as e:
        logger.error("save_fact: %s", e)
    finally:
        conn.close()


def get_facts(context_id: str, category: str = None) -> list:
    conn = _connect()
    if category:
        rows = conn.execute(
            "SELECT fact FROM long_term WHERE context_id=? AND category=? ORDER BY id DESC",
            (context_id, category)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT fact FROM long_term WHERE context_id=? ORDER BY id DESC",
            (context_id,)
        ).fetchall()
    conn.close()
    return [r["fact"] for r in rows]


def get_facts_text(context_id: str) -> str:
    facts = get_facts(context_id)
    if not facts:
        return ""
    return "Fakta yang diingat:\n" + "\n".join("- " + f for f in facts[:20])


def delete_fact(context_id: str, fact: str):
    conn = _connect()
    conn.execute("DELETE FROM long_term WHERE context_id=? AND fact=?", (context_id, fact))
    conn.commit()
    conn.close()


def clear_facts(context_id: str):
    conn = _connect()
    conn.execute("DELETE FROM long_term WHERE context_id=?", (context_id,))
    conn.commit()
    conn.close()


# ─── User Profile ─────────────────────────────────────────────────────────────

def upsert_user(phone: str, name: str):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO user_profile (phone, name, last_seen, msg_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(phone) DO UPDATE SET
            name      = excluded.name,
            last_seen = excluded.last_seen,
            msg_count = msg_count + 1
    """, (phone, name, ts))
    conn.commit()
    conn.close()


def get_user(phone: str) -> dict:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM user_profile WHERE phone=?", (phone,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def get_all_users() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT phone, name, last_seen, msg_count FROM user_profile ORDER BY msg_count DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Group Settings ───────────────────────────────────────────────────────────

def get_group_settings(group_id: str, group_name: str = None) -> dict:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM group_settings WHERE group_id=?", (group_id,)
    ).fetchone()
    
    if not row:
        ts = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT OR IGNORE INTO group_settings 
            (group_id, group_name, ai_enabled, ai_paused, provider, created_at, updated_at)
            VALUES (?, ?, 1, 0, 'auto', ?, ?)
        """, (group_id, group_name or group_id, ts, ts))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM group_settings WHERE group_id=?", (group_id,)
        ).fetchone()
    
    conn.close()
    return dict(row) if row else {}


def update_group_setting(group_id: str, **kwargs):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    kwargs["updated_at"] = ts
    
    sets  = ", ".join(k + "=?" for k in kwargs.keys())
    vals  = list(kwargs.values()) + [group_id]
    conn.execute(f"UPDATE group_settings SET {sets} WHERE group_id=?", vals)
    conn.commit()
    conn.close()


# ─── AI Log ──────────────────────────────────────────────────────────────────

def log_ai(
    context_id: str,
    is_group: bool,
    sender_phone: str,
    sender_name: str,
    prompt: str,
    response: str,
    provider: str,
    model: str,
    response_ms: int,
    retry_count: int = 0,
    fallback_used: bool = False,
    error: str = None,
):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO ai_log 
        (context_id, is_group, sender_phone, sender_name, prompt, response,
         provider, model, response_ms, retry_count, fallback_used, error, ts)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        context_id, int(is_group), sender_phone, sender_name,
        prompt[:2000], response[:2000], provider, model,
        response_ms, retry_count, int(fallback_used), error, ts
    ))
    conn.commit()
    conn.close()


def get_logs(context_id: str = None, limit: int = 20) -> list:
    conn = _connect()
    if context_id:
        rows = conn.execute(
            "SELECT * FROM ai_log WHERE context_id=? ORDER BY id DESC LIMIT ?",
            (context_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ai_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_tool(context_id: str, tool: str, args: dict, result: str):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO tool_log (context_id, tool, args, result, ts) VALUES (?,?,?,?,?)",
        (context_id, tool, json.dumps(args, ensure_ascii=False), str(result)[:500], ts)
    )
    conn.commit()
    conn.close()
