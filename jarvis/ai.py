"""
ai.py — AI Router v3.0: Gemini → Cerebras → Groq
Function Calling, Vision, Voice, Personality Manager
"""
import json, logging, time, base64, requests
from pathlib import Path
from typing import Optional
from jarvis.config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    CEREBRAS_API_KEY, CEREBRAS_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    AGENT_NAME, AI_TIMEOUT,
)
from jarvis.tools import TOOL_DECLARATIONS, execute_tool
from jarvis import memory as mem

logger = logging.getLogger(__name__)

GEMINI_BASE   = "https://generativelanguage.googleapis.com/v1beta"
CEREBRAS_BASE = "https://api.cerebras.ai/v1"
GROQ_BASE     = "https://api.groq.com/openai/v1"
MAX_TOOL_ITER = 5


def _get_personality_prompt(personality_name: str) -> str:
    p = mem.get_personality(personality_name)
    if p:
        return p["prompt"]
    return "Kamu adalah AI assistant yang helpful, natural, dan cerdas."


def _build_system(context_id, is_group, group_name, session_id, personality_name="default"):
    pers_prompt = _get_personality_prompt(personality_name)
    
    system = (
        pers_prompt + "\n\n"
        "Nama kamu: " + AGENT_NAME + "\n"
        "Kamu berjalan di HP Android via Termux.\n\n"
        "Aturan:\n"
        "- Bicara natural, tidak seperti bot\n"
        "- Bahasa Indonesia santai, boleh mix Inggris\n"
        "- Kalau ada request action → langsung eksekusi tool tanpa banyak tanya\n"
        "- Kalau diskusi → jawab natural\n"
        "- Tidak pernah bilang 'Saya tidak bisa' untuk hal yang ada toolnya\n"
        "- Variasikan kata pembuka, jangan monoton\n"
        "- Boleh menggunakan emoji secukupnya\n"
        "- Jawab singkat kalau pertanyaan singkat, panjang kalau perlu\n"
    )
    
    if is_group:
        system += (
            "\nKamu ada di grup WhatsApp '" + (group_name or "Grup") + "'.\n"
            "- Ikut diskusi seperti anggota grup biasa\n"
            "- Pahami konteks dari semua member\n"
            "- Balas natural, tahu siapa yang bicara\n"
        )
    
    facts = mem.get_facts_text(context_id, session_id)
    if facts:
        system += "\n\n" + facts
    
    return system


# ─── Gemini ───────────────────────────────────────────────────────────────────

def _call_gemini(messages, system, tools=None, image_data=None, image_mime=None):
    if not GEMINI_API_KEY:
        return {"error": "no_key"}
    
    url = f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    contents = []
    for i, m in enumerate(messages):
        role = "user" if m["role"] == "user" else "model"
        # Inject gambar ke pesan user terakhir
        if role == "user" and i == len(messages)-1 and image_data:
            parts = [
                {"inline_data": {"mime_type": image_mime or "image/jpeg", "data": image_data}},
                {"text": m["content"]}
            ]
        else:
            parts = [{"text": m["content"]}]
        contents.append({"role": role, "parts": parts})
    
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 2000}
    }
    if tools:
        payload["tools"] = [{"function_declarations": tools}]
        payload["tool_config"] = {"function_calling_config": {"mode": "AUTO"}}
    
    try:
        r = requests.post(url, json=payload, timeout=AI_TIMEOUT)
        if r.status_code == 429: return {"error": "rate_limit"}
        if r.status_code in (403, 402): return {"error": "quota_exceeded"}
        r.raise_for_status()
        data = r.json()
        
        cands = data.get("candidates", [])
        if not cands: return {"error": "no_candidates"}
        
        parts = cands[0].get("content", {}).get("parts", [])
        func_calls, texts = [], []
        for p in parts:
            if "functionCall" in p:
                func_calls.append({"name": p["functionCall"]["name"], "args": p["functionCall"].get("args", {})})
            elif "text" in p:
                texts.append(p["text"])
        
        return {
            "text": "".join(texts).strip(),
            "tool_calls": func_calls,
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "raw_content": cands[0].get("content", {}),
        }
    except requests.Timeout:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


def _call_openai_compat(messages, system, api_key, model, base_url, provider_name):
    if not api_key: return {"error": "no_key"}
    
    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    all_msgs = [{"role": "system", "content": system}] + messages
    payload  = {"model": model, "messages": all_msgs, "temperature": 0.85, "max_tokens": 2000}
    
    try:
        r = requests.post(base_url + "/chat/completions", json=payload, headers=headers, timeout=AI_TIMEOUT)
        if r.status_code in (429, 503): return {"error": "rate_limit"}
        if r.status_code == 402: return {"error": "quota_exceeded"}
        r.raise_for_status()
        data   = r.json()
        choice = data.get("choices", [{}])[0]
        text   = choice.get("message", {}).get("content", "") or ""
        return {"text": text.strip(), "tool_calls": [], "provider": provider_name, "model": model}
    except requests.Timeout:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


def _route_fallback(messages, system):
    """Fallback: Cerebras → Groq (tanpa tool calling)."""
    providers = [
        ("cerebras", lambda: _call_openai_compat(messages, system, CEREBRAS_API_KEY, CEREBRAS_MODEL, CEREBRAS_BASE, "cerebras")),
        ("groq",     lambda: _call_openai_compat(messages, system, GROQ_API_KEY, GROQ_MODEL, GROQ_BASE, "groq")),
    ]
    for name, fn in providers:
        res = fn()
        if "error" not in res:
            return res, name, True
    return {"text": "Maaf, semua AI provider tidak tersedia saat ini.", "tool_calls": []}, "none", True


# ─── Transcription ────────────────────────────────────────────────────────────

def transcribe_audio(file_path: str) -> str:
    """Transkripsi audio via Groq Whisper atau fallback."""
    if GROQ_API_KEY:
        try:
            with open(file_path, "rb") as f:
                headers = {"Authorization": "Bearer " + GROQ_API_KEY}
                files   = {"file": (Path(file_path).name, f, "audio/ogg")}
                data    = {"model": "whisper-large-v3"}
                r = requests.post(GROQ_BASE + "/audio/transcriptions",
                                  headers=headers, files=files, data=data, timeout=30)
                r.raise_for_status()
                return r.json().get("text", "").strip()
        except Exception as e:
            logger.error("Groq transcribe: %s", e)
    
    # Fallback: Gemini audio understanding
    if GEMINI_API_KEY:
        try:
            with open(file_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            url = f"{GEMINI_BASE}/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"role":"user","parts":[
                {"inline_data":{"mime_type":"audio/ogg","data":audio_b64}},
                {"text":"Transkripsi audio ini ke teks bahasa Indonesia."}
            ]}]}
            r = requests.post(url, json=payload, timeout=30)
            r.raise_for_status()
            cands = r.json().get("candidates",[])
            if cands:
                parts = cands[0].get("content",{}).get("parts",[])
                return "".join(p.get("text","") for p in parts).strip()
        except Exception as e:
            logger.error("Gemini transcribe: %s", e)
    
    return "[Tidak bisa mentranskrip audio]"


def analyze_image(file_path: str, user_question: str = "") -> str:
    """Analisis gambar via Gemini Vision."""
    if not GEMINI_API_KEY:
        return "[Vision tidak tersedia — isi GEMINI_API_KEY]"
    try:
        with open(file_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        mime = "image/jpeg"
        if file_path.lower().endswith(".png"):  mime = "image/png"
        elif file_path.lower().endswith(".gif"): mime = "image/gif"
        elif file_path.lower().endswith(".webp"):mime = "image/webp"
        
        question = user_question or "Jelaskan isi gambar ini secara detail dalam bahasa Indonesia."
        url = f"{GEMINI_BASE}/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents":[{"role":"user","parts":[
            {"inline_data":{"mime_type":mime,"data":img_b64}},
            {"text": question}
        ]}]}
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        cands = r.json().get("candidates",[])
        if cands:
            parts = cands[0].get("content",{}).get("parts",[])
            return "".join(p.get("text","") for p in parts).strip()
    except Exception as e:
        logger.error("analyze_image: %s", e)
    return "[Gagal menganalisis gambar]"


# ─── Main chat ────────────────────────────────────────────────────────────────

def chat(context_id, user_message, sender_phone="", sender_name="",
         is_group=False, group_name=None, session_id="default",
         image_data=None, image_mime=None, personality_name="default"):
    
    t_start = time.time()
    mem.add_message(context_id, "user", user_message, sender=sender_name if is_group else None, session_id=session_id)
    mem.upsert_user(sender_phone, sender_name, session_id=session_id)
    
    system   = _build_system(context_id, is_group, group_name, session_id, personality_name)
    history  = mem.get_history(context_id, session_id)
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    
    final_text    = None
    provider_used = None
    retry_count   = 0
    fallback_used = False
    error_msg     = None
    
    # ── Gemini dengan Function Calling ────────────────────────────────────────
    if GEMINI_API_KEY:
        # Kalau ada gambar, gunakan model vision tanpa tools dulu
        if image_data:
            res = _call_gemini(messages, system, tools=None, image_data=image_data, image_mime=image_mime)
            if "error" not in res:
                final_text    = res.get("text", "")
                provider_used = "gemini"
        
        if not final_text:
            # Gemini dengan tool calling
            gemini_contents = [
                {"role": "user" if m["role"]=="user" else "model", "parts":[{"text":m["content"]}]}
                for m in messages
            ]
            
            for iteration in range(MAX_TOOL_ITER):
                res = _call_gemini(messages, system, TOOL_DECLARATIONS)
                if "error" in res:
                    error_msg = res["error"]
                    break
                
                tool_calls = res.get("tool_calls", [])
                if not tool_calls:
                    final_text    = res.get("text", "")
                    provider_used = "gemini"
                    break
                
                # Eksekusi tools
                func_resp_parts = []
                for tc in tool_calls:
                    t_result = execute_tool(tc["name"], tc["args"], context_id, session_id)
                    mem.log_tool(context_id, tc["name"], tc["args"], t_result, session_id)
                    logger.info("[TOOL] %s → %s", tc["name"], str(t_result)[:60])
                    func_resp_parts.append({"functionResponse":{"name":tc["name"],"response":{"result":t_result}}})
                
                # Update contents dan call lagi
                gemini_contents.append(res["raw_content"])
                gemini_contents.append({"role":"user","parts":func_resp_parts})
                
                url = f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "system_instruction":{"parts":[{"text":system}]},
                    "contents": gemini_contents,
                    "generationConfig":{"temperature":0.85,"maxOutputTokens":2000}
                }
                try:
                    r = requests.post(url, json=payload, timeout=AI_TIMEOUT)
                    r.raise_for_status()
                    data2  = r.json()
                    cands2 = data2.get("candidates",[])
                    if cands2:
                        parts2 = cands2[0].get("content",{}).get("parts",[])
                        new_fc = [p for p in parts2 if "functionCall" in p]
                        if new_fc:
                            res["raw_content"] = cands2[0].get("content",{})
                            res["tool_calls"]  = [{"name":p["functionCall"]["name"],"args":p["functionCall"].get("args",{})} for p in new_fc]
                            continue
                        final_text    = "".join(p.get("text","") for p in parts2 if "text" in p).strip()
                        provider_used = "gemini"
                        break
                except Exception as e:
                    logger.error("Gemini post-tool: %s", e)
                    break
    
    # ── Fallback ──────────────────────────────────────────────────────────────
    if not final_text:
        res, provider_used, fallback_used = _route_fallback(messages, system)
        final_text = res.get("text") or "Maaf, tidak ada respons."
        retry_count += 1
    
    if not final_text:
        final_text = "Maaf, ada kendala teknis."
    
    mem.add_message(context_id, "assistant", final_text, session_id=session_id)
    
    t_ms = int((time.time() - t_start) * 1000)
    mem.log_ai(
        context_id=context_id, is_group=is_group,
        sender_phone=sender_phone, sender_name=sender_name,
        prompt=user_message, response=final_text,
        provider=provider_used or "unknown",
        model=GEMINI_MODEL if provider_used=="gemini" else (CEREBRAS_MODEL if provider_used=="cerebras" else GROQ_MODEL),
        response_ms=t_ms, retry_count=retry_count,
        fallback_used=fallback_used, error=error_msg, session_id=session_id,
    )
    
    logger.info("[AI] %s | %s | %dms | provider=%s", context_id[:20], session_id, t_ms, provider_used)
    return final_text
