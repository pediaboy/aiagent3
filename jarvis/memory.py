"""
memory.py — Full SQLite memory engine v3.0
Short-term, long-term, user profiles, group settings, AI logs, sessions, personalities
"""
import sqlite3, json, logging
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
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS short_term (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            context_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            sender     TEXT,
            content    TEXT NOT NULL,
            has_media  INTEGER DEFAULT 0,
            media_type TEXT,
            ts         TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS long_term (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            context_id TEXT NOT NULL,
            fact       TEXT NOT NULL,
            category   TEXT DEFAULT 'general',
            ts         TEXT NOT NULL,
            UNIQUE(session_id, context_id, fact)
        );
        CREATE TABLE IF NOT EXISTS user_profile (
            phone      TEXT NOT NULL,
            session_id TEXT NOT NULL DEFAULT 'default',
            name       TEXT,
            last_seen  TEXT,
            msg_count  INTEGER DEFAULT 0,
            personality TEXT DEFAULT 'default',
            notes      TEXT DEFAULT '',
            PRIMARY KEY(phone, session_id)
        );
        CREATE TABLE IF NOT EXISTS group_settings (
            group_id   TEXT NOT NULL,
            session_id TEXT NOT NULL DEFAULT 'default',
            group_name TEXT,
            ai_enabled INTEGER DEFAULT 1,
            ai_paused  INTEGER DEFAULT 0,
            provider   TEXT DEFAULT 'auto',
            personality TEXT DEFAULT 'default',
            created_at TEXT,
            updated_at TEXT,
            PRIMARY KEY(group_id, session_id)
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            phone       TEXT,
            name        TEXT,
            status      TEXT DEFAULT 'disconnected',
            qr_code     TEXT,
            ai_enabled  INTEGER DEFAULT 1,
            provider    TEXT DEFAULT 'auto',
            created_at  TEXT,
            updated_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS ai_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT DEFAULT 'default',
            context_id    TEXT,
            is_group      INTEGER DEFAULT 0,
            sender_phone  TEXT,
            sender_name   TEXT,
            prompt        TEXT,
            response      TEXT,
            provider      TEXT,
            model         TEXT,
            response_ms   INTEGER,
            input_tokens  INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            retry_count   INTEGER DEFAULT 0,
            fallback_used INTEGER DEFAULT 0,
            error         TEXT,
            ts            TEXT
        );
        CREATE TABLE IF NOT EXISTS tool_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT DEFAULT 'default',
            context_id TEXT,
            tool       TEXT,
            args       TEXT,
            result     TEXT,
            ts         TEXT
        );
        CREATE TABLE IF NOT EXISTS personalities (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT UNIQUE NOT NULL,
            display    TEXT NOT NULL,
            prompt     TEXT NOT NULL,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_short_ctx  ON short_term(session_id, context_id);
        CREATE INDEX IF NOT EXISTS idx_long_ctx   ON long_term(session_id, context_id);
        CREATE INDEX IF NOT EXISTS idx_log_ctx    ON ai_log(session_id, context_id);
        CREATE INDEX IF NOT EXISTS idx_log_ts     ON ai_log(ts);
    """)
    conn.commit()
    _seed_personalities(conn)
    conn.close()
    logger.info("DB initialized at %s", DB_PATH)

def _seed_personalities(conn):
    defaults = [
        ("default",    "Default Assistant", "Kamu adalah AI assistant yang helpful, natural, dan cerdas. Bicara santai seperti teman tapi tetap informatif."),
        ("jarvis",     "Jarvis",            "Kamu adalah Jarvis, AI assistant canggih seperti di film Iron Man. Formal, cerdas, proaktif, selalu menyebut user sebagai 'Tuan'."),
        ("programmer", "Programmer",        "Kamu adalah senior software engineer. Jawab pertanyaan teknis dengan tepat, berikan code yang clean, dan jelaskan dengan jelas. Suka debug, coding, arsitektur sistem."),
        ("trader",     "Trading Analyst",   "Kamu adalah analis trading berpengalaman. Pahami chart, bandarmologi, saham, forex, kripto. Berikan analisis teknikal dan fundamental yang akurat."),
        ("researcher", "Researcher",        "Kamu adalah peneliti yang cermat dan detail. Suka mencari fakta, menganalisis data, membuat kesimpulan berdasarkan bukti. Selalu cantumkan sumber jika tahu."),
        ("tutor",      "Tutor",             "Kamu adalah guru yang sabar dan menyenangkan. Jelaskan konsep dengan analogi sederhana, berikan contoh nyata, dan pastikan user paham sebelum lanjut."),
        ("translator", "Translator",        "Kamu adalah penerjemah profesional multi-bahasa. Terjemahkan dengan akurat, pertahankan makna dan nada asli, berikan penjelasan nuansa jika perlu."),
    ]
    for name, display, prompt in defaults:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO personalities (name, display, prompt, created_at) VALUES (?,?,?,?)",
                (name, display, prompt, datetime.utcnow().isoformat())
            )
        except:
            pass
    conn.commit()

# ── Short-term ─────────────────────────────────────────────────────────────────

def add_message(context_id, role, content, sender=None, session_id="default", has_media=False, media_type=None):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO short_term (session_id,context_id,role,sender,content,has_media,media_type,ts) VALUES (?,?,?,?,?,?,?,?)",
        (session_id, context_id, role, sender, content, int(has_media), media_type, ts)
    )
    conn.commit()
    conn.execute("""
        DELETE FROM short_term WHERE session_id=? AND context_id=? AND id NOT IN (
            SELECT id FROM short_term WHERE session_id=? AND context_id=? ORDER BY id DESC LIMIT ?
        )
    """, (session_id, context_id, session_id, context_id, SHORT_TERM_LIMIT))
    conn.commit()
    conn.close()

def get_history(context_id, session_id="default", limit=None):
    conn = _connect()
    lim = limit or SHORT_TERM_LIMIT
    rows = conn.execute(
        "SELECT role, sender, content FROM short_term WHERE session_id=? AND context_id=? ORDER BY id DESC LIMIT ?",
        (session_id, context_id, lim)
    ).fetchall()
    conn.close()
    result = []
    for r in reversed(rows):
        if r["role"] == "user" and r["sender"]:
            content = r["sender"] + ": " + r["content"]
        else:
            content = r["content"]
        result.append({"role": r["role"], "content": content})
    return result

def get_history_raw(context_id, session_id="default", limit=50):
    conn = _connect()
    rows = conn.execute(
        "SELECT role, sender, content, ts, has_media, media_type FROM short_term WHERE session_id=? AND context_id=? ORDER BY id DESC LIMIT ?",
        (session_id, context_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]

def clear_history(context_id, session_id="default"):
    conn = _connect()
    conn.execute("DELETE FROM short_term WHERE session_id=? AND context_id=?", (session_id, context_id))
    conn.commit(); conn.close()

def get_history_count(context_id, session_id="default"):
    conn = _connect()
    row = conn.execute("SELECT COUNT(*) as c FROM short_term WHERE session_id=? AND context_id=?", (session_id, context_id)).fetchone()
    conn.close()
    return row["c"] if row else 0

def export_history(context_id, session_id="default"):
    rows = get_history_raw(context_id, session_id, limit=1000)
    lines = []
    for r in rows:
        sender = r.get("sender") or r["role"]
        ts_str = r["ts"][:16] if r["ts"] else ""
        lines.append(f"[{ts_str}] {sender}: {r['content']}")
    return "\n".join(lines)

# ── Long-term ──────────────────────────────────────────────────────────────────

def save_fact(context_id, fact, category="general", session_id="default"):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO long_term (session_id,context_id,fact,category,ts) VALUES (?,?,?,?,?)",
            (session_id, context_id, fact, category, ts)
        )
        conn.commit()
        conn.execute("""
            DELETE FROM long_term WHERE session_id=? AND context_id=? AND id NOT IN (
                SELECT id FROM long_term WHERE session_id=? AND context_id=? ORDER BY id DESC LIMIT ?
            )
        """, (session_id, context_id, session_id, context_id, MAX_LONG_TERM))
        conn.commit()
    finally:
        conn.close()

def get_facts(context_id, session_id="default", category=None):
    conn = _connect()
    if category:
        rows = conn.execute("SELECT fact FROM long_term WHERE session_id=? AND context_id=? AND category=? ORDER BY id DESC", (session_id, context_id, category)).fetchall()
    else:
        rows = conn.execute("SELECT fact FROM long_term WHERE session_id=? AND context_id=? ORDER BY id DESC", (session_id, context_id)).fetchall()
    conn.close()
    return [r["fact"] for r in rows]

def get_facts_text(context_id, session_id="default"):
    facts = get_facts(context_id, session_id)
    if not facts: return ""
    return "Yang aku ingat tentang percakapan ini:\n" + "\n".join("- " + f for f in facts[:20])

def clear_facts(context_id, session_id="default"):
    conn = _connect()
    conn.execute("DELETE FROM long_term WHERE session_id=? AND context_id=?", (session_id, context_id))
    conn.commit(); conn.close()

def import_memory(context_id, facts_list, session_id="default"):
    for fact in facts_list:
        if fact.strip():
            save_fact(context_id, fact.strip(), session_id=session_id)

# ── User Profile ───────────────────────────────────────────────────────────────

def upsert_user(phone, name, session_id="default"):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO user_profile (phone, session_id, name, last_seen, msg_count)
        VALUES (?,?,?,?,1)
        ON CONFLICT(phone, session_id) DO UPDATE SET
            name=excluded.name, last_seen=excluded.last_seen, msg_count=msg_count+1
    """, (phone, session_id, name, ts))
    conn.commit(); conn.close()

def get_user(phone, session_id="default"):
    conn = _connect()
    row = conn.execute("SELECT * FROM user_profile WHERE phone=? AND session_id=?", (phone, session_id)).fetchone()
    conn.close()
    return dict(row) if row else {}

def set_user_personality(phone, personality, session_id="default"):
    conn = _connect()
    conn.execute("UPDATE user_profile SET personality=? WHERE phone=? AND session_id=?", (personality, phone, session_id))
    conn.commit(); conn.close()

def get_all_users(session_id="default"):
    conn = _connect()
    rows = conn.execute("SELECT * FROM user_profile WHERE session_id=? ORDER BY msg_count DESC", (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Group Settings ─────────────────────────────────────────────────────────────

def get_group_settings(group_id, group_name=None, session_id="default"):
    conn = _connect()
    row = conn.execute("SELECT * FROM group_settings WHERE group_id=? AND session_id=?", (group_id, session_id)).fetchone()
    if not row:
        ts = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT OR IGNORE INTO group_settings (group_id,session_id,group_name,ai_enabled,ai_paused,provider,created_at,updated_at)
            VALUES (?,?,?,1,0,'auto',?,?)
        """, (group_id, session_id, group_name or group_id, ts, ts))
        conn.commit()
        row = conn.execute("SELECT * FROM group_settings WHERE group_id=? AND session_id=?", (group_id, session_id)).fetchone()
    conn.close()
    return dict(row) if row else {}

def update_group_setting(group_id, session_id="default", **kwargs):
    conn = _connect()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(k + "=?" for k in kwargs)
    vals = list(kwargs.values()) + [group_id, session_id]
    conn.execute(f"UPDATE group_settings SET {sets} WHERE group_id=? AND session_id=?", vals)
    conn.commit(); conn.close()

def get_all_groups(session_id="default"):
    conn = _connect()
    rows = conn.execute("SELECT * FROM group_settings WHERE session_id=? ORDER BY updated_at DESC", (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Sessions ───────────────────────────────────────────────────────────────────

def upsert_session(session_id, **kwargs):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    kwargs["updated_at"] = ts
    existing = conn.execute("SELECT session_id FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if existing:
        sets = ", ".join(k + "=?" for k in kwargs)
        vals = list(kwargs.values()) + [session_id]
        conn.execute(f"UPDATE sessions SET {sets} WHERE session_id=?", vals)
    else:
        kwargs["session_id"] = session_id
        kwargs["created_at"] = ts
        cols = ", ".join(kwargs.keys())
        phs  = ", ".join("?" for _ in kwargs)
        conn.execute(f"INSERT OR REPLACE INTO sessions ({cols}) VALUES ({phs})", list(kwargs.values()))
    conn.commit(); conn.close()

def get_session(session_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def get_all_sessions():
    conn = _connect()
    rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Personalities ──────────────────────────────────────────────────────────────

def get_personality(name):
    conn = _connect()
    row = conn.execute("SELECT * FROM personalities WHERE name=?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_personalities():
    conn = _connect()
    rows = conn.execute("SELECT * FROM personalities ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_personality(name, display, prompt):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO personalities (name, display, prompt, created_at) VALUES (?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET display=excluded.display, prompt=excluded.prompt
    """, (name, display, prompt, ts))
    conn.commit(); conn.close()

# ── AI Log ─────────────────────────────────────────────────────────────────────

def log_ai(context_id, is_group, sender_phone, sender_name, prompt, response,
           provider, model, response_ms, retry_count=0, fallback_used=False,
           error=None, session_id="default", input_tokens=0, output_tokens=0):
    conn = _connect()
    ts = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO ai_log (session_id,context_id,is_group,sender_phone,sender_name,
        prompt,response,provider,model,response_ms,input_tokens,output_tokens,
        retry_count,fallback_used,error,ts)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (session_id, context_id, int(is_group), sender_phone, sender_name,
          prompt[:2000], response[:2000], provider, model, response_ms,
          input_tokens, output_tokens, retry_count, int(fallback_used), error, ts))
    conn.commit(); conn.close()

def get_logs(context_id=None, session_id=None, limit=50):
    conn = _connect()
    if context_id and session_id:
        rows = conn.execute("SELECT * FROM ai_log WHERE context_id=? AND session_id=? ORDER BY id DESC LIMIT ?", (context_id, session_id, limit)).fetchall()
    elif session_id:
        rows = conn.execute("SELECT * FROM ai_log WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ai_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_analytics(session_id=None):
    conn = _connect()
    q_filter = "WHERE session_id=?" if session_id else ""
    params   = (session_id,) if session_id else ()
    
    total_msgs = conn.execute(f"SELECT COUNT(*) as c FROM ai_log {q_filter}", params).fetchone()["c"]
    total_users= conn.execute(f"SELECT COUNT(DISTINCT sender_phone) as c FROM ai_log {q_filter}", params).fetchone()["c"]
    avg_ms     = conn.execute(f"SELECT AVG(response_ms) as a FROM ai_log {q_filter}", params).fetchone()["a"] or 0
    errors     = conn.execute(f"SELECT COUNT(*) as c FROM ai_log {q_filter} {'AND' if q_filter else 'WHERE'} error IS NOT NULL", params if q_filter else ()).fetchone()["c"]
    fallbacks  = conn.execute(f"SELECT COUNT(*) as c FROM ai_log {q_filter} {'AND' if q_filter else 'WHERE'} fallback_used=1", params if q_filter else ()).fetchone()["c"]
    
    by_provider= conn.execute(f"SELECT provider, COUNT(*) as c FROM ai_log {q_filter} GROUP BY provider ORDER BY c DESC", params).fetchall()
    total_grp  = conn.execute(f"SELECT COUNT(DISTINCT context_id) as c FROM ai_log {q_filter} {'AND' if q_filter else 'WHERE'} is_group=1", params if q_filter else ()).fetchone()["c"]
    
    conn.close()
    return {
        "total_messages": total_msgs,
        "total_users":    total_users,
        "total_groups":   total_grp,
        "avg_response_ms": round(avg_ms),
        "error_count":    errors,
        "fallback_count": fallbacks,
        "by_provider":    [dict(r) for r in by_provider],
    }

def log_tool(context_id, tool, args, result, session_id="default"):
    conn = _connect()
    conn.execute(
        "INSERT INTO tool_log (session_id,context_id,tool,args,result,ts) VALUES (?,?,?,?,?,?)",
        (session_id, context_id, tool, json.dumps(args, ensure_ascii=False), str(result)[:500], datetime.utcnow().isoformat())
    )
    conn.commit(); conn.close()
