"""
dashboard/app.py — Admin Dashboard (Flask)
Web panel untuk semua konfigurasi AI Agent.
Tidak ada command di WhatsApp — semua dari sini.
"""
import json, os, sys, functools
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis.config import DASHBOARD_SECRET, DASHBOARD_HOST, DASHBOARD_PORT, AGENT_NAME
from jarvis import memory as mem

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = DASHBOARD_SECRET + "_flask_secret"


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_SECRET:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Password salah.", "error")
    return render_template("login.html", agent_name=AGENT_NAME)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    analytics = mem.get_analytics()
    sessions  = mem.get_all_sessions()
    logs      = mem.get_logs(limit=5)
    return render_template("index.html",
        agent_name=AGENT_NAME,
        analytics=analytics,
        sessions=sessions,
        recent_logs=logs,
        page="dashboard"
    )


# ─── Chats ────────────────────────────────────────────────────────────────────

@app.route("/chats")
@login_required
def chats():
    session_id = request.args.get("session_id", "default")
    users  = mem.get_all_users(session_id)
    groups = mem.get_all_groups(session_id)
    sessions_list = mem.get_all_sessions()
    return render_template("chats.html",
        agent_name=AGENT_NAME, users=users, groups=groups,
        sessions_list=sessions_list, current_session=session_id, page="chats")

@app.route("/chats/history")
@login_required
def chat_history():
    context_id = request.args.get("context_id", "")
    session_id = request.args.get("session_id", "default")
    history    = mem.get_history_raw(context_id, session_id, limit=100)
    return render_template("chat_history.html",
        agent_name=AGENT_NAME, history=history,
        context_id=context_id, session_id=session_id, page="chats")

@app.route("/chats/export")
@login_required
def export_chat():
    context_id = request.args.get("context_id", "")
    session_id = request.args.get("session_id", "default")
    text = mem.export_history(context_id, session_id)
    from flask import Response
    return Response(
        text,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename=chat_{context_id}_{session_id}.txt"}
    )

@app.route("/chats/clear", methods=["POST"])
@login_required
def clear_chat():
    context_id = request.form.get("context_id","")
    session_id = request.form.get("session_id","default")
    if context_id:
        mem.clear_history(context_id, session_id)
        flash("History dihapus.", "success")
    return redirect(url_for("chats", session_id=session_id))


# ─── Users ────────────────────────────────────────────────────────────────────

@app.route("/users")
@login_required
def users():
    session_id = request.args.get("session_id","default")
    users_list = mem.get_all_users(session_id)
    personalities = mem.get_all_personalities()
    sessions_list = mem.get_all_sessions()
    return render_template("users.html",
        agent_name=AGENT_NAME, users=users_list,
        personalities=personalities, sessions_list=sessions_list,
        current_session=session_id, page="users")

@app.route("/users/set_personality", methods=["POST"])
@login_required
def set_user_personality():
    phone      = request.form.get("phone","")
    personality= request.form.get("personality","default")
    session_id = request.form.get("session_id","default")
    if phone:
        mem.set_user_personality(phone, personality, session_id)
        flash("Personality diubah.", "success")
    return redirect(url_for("users", session_id=session_id))


# ─── Groups ───────────────────────────────────────────────────────────────────

@app.route("/groups")
@login_required
def groups():
    session_id  = request.args.get("session_id","default")
    groups_list = mem.get_all_groups(session_id)
    personalities  = mem.get_all_personalities()
    sessions_list  = mem.get_all_sessions()
    return render_template("groups.html",
        agent_name=AGENT_NAME, groups=groups_list,
        personalities=personalities, sessions_list=sessions_list,
        current_session=session_id, page="groups")

@app.route("/groups/update", methods=["POST"])
@login_required
def update_group():
    group_id   = request.form.get("group_id","")
    session_id = request.form.get("session_id","default")
    if not group_id:
        flash("Group ID kosong.", "error")
        return redirect(url_for("groups"))
    
    updates = {}
    if "ai_enabled" in request.form:
        updates["ai_enabled"] = int(request.form.get("ai_enabled","1"))
    if "ai_paused" in request.form:
        updates["ai_paused"] = int(request.form.get("ai_paused","0"))
    if "provider" in request.form:
        updates["provider"] = request.form.get("provider","auto")
    if "personality" in request.form:
        updates["personality"] = request.form.get("personality","default")
    
    if updates:
        mem.update_group_setting(group_id, session_id, **updates)
        flash("Group diperbarui.", "success")
    return redirect(url_for("groups", session_id=session_id))

@app.route("/groups/reset_memory", methods=["POST"])
@login_required
def reset_group_memory():
    group_id   = request.form.get("group_id","")
    session_id = request.form.get("session_id","default")
    if group_id:
        mem.clear_facts(group_id, session_id)
        flash("Memory grup direset.", "success")
    return redirect(url_for("groups", session_id=session_id))

@app.route("/groups/clear_history", methods=["POST"])
@login_required
def clear_group_history():
    group_id   = request.form.get("group_id","")
    session_id = request.form.get("session_id","default")
    if group_id:
        mem.clear_history(group_id, session_id)
        flash("History grup dihapus.", "success")
    return redirect(url_for("groups", session_id=session_id))


# ─── Memory ───────────────────────────────────────────────────────────────────

@app.route("/memory")
@login_required
def memory_page():
    session_id = request.args.get("session_id","default")
    context_id = request.args.get("context_id","")
    facts = mem.get_facts(context_id, session_id) if context_id else []
    users = mem.get_all_users(session_id)
    groups= mem.get_all_groups(session_id)
    return render_template("memory.html",
        agent_name=AGENT_NAME, facts=facts, context_id=context_id,
        users=users, groups=groups,
        session_id=session_id, page="memory")

@app.route("/memory/import", methods=["POST"])
@login_required
def import_memory():
    context_id = request.form.get("context_id","")
    session_id = request.form.get("session_id","default")
    raw        = request.form.get("facts","")
    if context_id and raw:
        facts_list = [l.strip() for l in raw.split("\n") if l.strip()]
        mem.import_memory(context_id, facts_list, session_id)
        flash(f"{len(facts_list)} fakta diimport.", "success")
    return redirect(url_for("memory_page", session_id=session_id, context_id=context_id))

@app.route("/memory/clear", methods=["POST"])
@login_required
def clear_memory():
    context_id = request.form.get("context_id","")
    session_id = request.form.get("session_id","default")
    if context_id:
        mem.clear_facts(context_id, session_id)
        flash("Memory dihapus.", "success")
    return redirect(url_for("memory_page", session_id=session_id))


# ─── AI Providers ─────────────────────────────────────────────────────────────

@app.route("/providers")
@login_required
def providers():
    from jarvis.config import GEMINI_API_KEY, CEREBRAS_API_KEY, GROQ_API_KEY
    return render_template("providers.html",
        agent_name=AGENT_NAME,
        gemini_ok=bool(GEMINI_API_KEY),
        cerebras_ok=bool(CEREBRAS_API_KEY),
        groq_ok=bool(GROQ_API_KEY),
        page="providers")

@app.route("/providers/test", methods=["POST"])
@login_required
def test_provider():
    provider = request.form.get("provider","gemini")
    result = _test_ai(provider)
    return jsonify(result)

def _test_ai(provider):
    import time, requests as req
    from jarvis.config import (GEMINI_API_KEY,GEMINI_MODEL,
        CEREBRAS_API_KEY,CEREBRAS_MODEL,CEREBRAS_BASE,
        GROQ_API_KEY,GROQ_MODEL,GROQ_BASE)
    t = time.time()
    try:
        if provider == "gemini" and GEMINI_API_KEY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            r = req.post(url, json={"contents":[{"role":"user","parts":[{"text":"Hi"}]}]}, timeout=10)
            r.raise_for_status()
            return {"ok": True, "ms": int((time.time()-t)*1000), "provider": "gemini"}
        elif provider == "cerebras" and CEREBRAS_API_KEY:
            r = req.post(CEREBRAS_BASE+"/chat/completions",
                headers={"Authorization":"Bearer "+CEREBRAS_API_KEY},
                json={"model":CEREBRAS_MODEL,"messages":[{"role":"user","content":"Hi"}],"max_tokens":5},
                timeout=10)
            r.raise_for_status()
            return {"ok": True, "ms": int((time.time()-t)*1000), "provider": "cerebras"}
        elif provider == "groq" and GROQ_API_KEY:
            r = req.post(GROQ_BASE+"/chat/completions",
                headers={"Authorization":"Bearer "+GROQ_API_KEY},
                json={"model":GROQ_MODEL,"messages":[{"role":"user","content":"Hi"}],"max_tokens":5},
                timeout=10)
            r.raise_for_status()
            return {"ok": True, "ms": int((time.time()-t)*1000), "provider": provider}
        return {"ok": False, "error": "API key tidak ada"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Personalities ────────────────────────────────────────────────────────────

@app.route("/personalities")
@login_required
def personalities():
    all_p = mem.get_all_personalities()
    return render_template("personalities.html",
        agent_name=AGENT_NAME, personalities=all_p, page="personalities")

@app.route("/personalities/save", methods=["POST"])
@login_required
def save_personality():
    name    = request.form.get("name","").strip().lower().replace(" ","_")
    display = request.form.get("display","").strip()
    prompt  = request.form.get("prompt","").strip()
    if name and display and prompt:
        mem.save_personality(name, display, prompt)
        flash("Personality disimpan.", "success")
    else:
        flash("Semua field wajib diisi.", "error")
    return redirect(url_for("personalities"))


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.route("/analytics")
@login_required
def analytics():
    session_id = request.args.get("session_id", None)
    data = mem.get_analytics(session_id)
    logs = mem.get_logs(session_id=session_id, limit=20)
    sessions_list = mem.get_all_sessions()
    return render_template("analytics.html",
        agent_name=AGENT_NAME, analytics=data, logs=logs,
        sessions_list=sessions_list, current_session=session_id or "all",
        page="analytics")


# ─── Logs ─────────────────────────────────────────────────────────────────────

@app.route("/logs")
@login_required
def logs():
    session_id = request.args.get("session_id", None)
    page_num   = int(request.args.get("page", 1))
    limit      = 50
    logs_data  = mem.get_logs(session_id=session_id, limit=limit * page_num)
    sessions_list = mem.get_all_sessions()
    return render_template("logs.html",
        agent_name=AGENT_NAME, logs=logs_data,
        sessions_list=sessions_list, current_session=session_id or "all",
        page_num=page_num, page="logs")


# ─── Android Tools ────────────────────────────────────────────────────────────

@app.route("/tools")
@login_required
def tools_page():
    from jarvis.tools import TOOL_DECLARATIONS
    return render_template("tools.html",
        agent_name=AGENT_NAME, tools=TOOL_DECLARATIONS, page="tools")

@app.route("/tools/run", methods=["POST"])
@login_required
def run_tool():
    from jarvis.tools import execute_tool
    tool_name = request.form.get("tool_name","")
    args_raw  = request.form.get("args","{}")
    try:
        args = json.loads(args_raw)
    except:
        args = {}
    result = execute_tool(tool_name, args, "dashboard", "default")
    return jsonify({"result": result})


# ─── Settings ─────────────────────────────────────────────────────────────────

@app.route("/settings")
@login_required
def settings():
    env_path = Path(__file__).parent.parent / ".env"
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip()
    return render_template("settings.html",
        agent_name=AGENT_NAME, env_vars=env_vars, page="settings")

@app.route("/settings/save", methods=["POST"])
@login_required
def save_settings():
    env_path = Path(__file__).parent.parent / ".env"
    updates = request.form.to_dict()
    
    existing = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    
    existing.update(updates)
    
    lines = []
    for k, v in existing.items():
        lines.append(f"{k}={v}")
    
    env_path.write_text("\n".join(lines) + "\n")
    flash("Settings disimpan. Restart agent agar berlaku.", "success")
    return redirect(url_for("settings"))


# ─── API (untuk AJAX) ─────────────────────────────────────────────────────────

@app.route("/api/analytics")
@login_required
def api_analytics():
    session_id = request.args.get("session_id", None)
    return jsonify(mem.get_analytics(session_id))

@app.route("/api/logs")
@login_required
def api_logs():
    session_id = request.args.get("session_id", None)
    limit = int(request.args.get("limit", 20))
    return jsonify(mem.get_logs(session_id=session_id, limit=limit))


def run_dashboard():
    from jarvis.config import DASHBOARD_HOST, DASHBOARD_PORT
    print(f"\n  Dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print(f"  Password : dari DASHBOARD_SECRET di .env\n")
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False, threaded=True)
