"""
ai.py — AI Router: Gemini → Cerebras → Groq (auto-fallback)
Full Function Calling + Memory
"""
import json
import logging
import time
import requests
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


def _build_system_prompt(context_id: str, is_group: bool, group_name: str = None) -> str:
    base = (
        "Kamu adalah " + AGENT_NAME + ", AI assistant yang berjalan di HP Android.\n\n"
        "Kepribadian:\n"
        "- Ngobrol natural seperti manusia Indonesia, bukan seperti bot\n"
        "- Bahasa Indonesia santai, boleh campur Inggris kalau wajar\n"
        "- Proaktif, langsung eksekusi tool tanpa banyak tanya\n"
        "- Bisa diskusi panjang, coding, debugging, analisis, nulis artikel\n"
        "- Punya opini, bisa bercanda, tapi tetap helpful\n\n"
        "Kemampuan:\n"
        "- Kontrol Android: buka app, screenshot, senter, kamera, dll\n"
        "- Device: baterai, RAM, storage, CPU, WiFi, Bluetooth\n"
        "- Alarm, Timer, Reminder\n"
        "- Musik: putar YouTube\n"
        "- Web: search, cuaca, kurs, baca artikel\n"
        "- Memory: simpan dan ingat info penting\n"
        "- Diskusi: semua topik, coding, writing, brainstorming\n\n"
        "PENTING:\n"
        "- Kalau ada request action (buka app, alarm, dll) → langsung pakai tool\n"
        "- Kalau diskusi/tanya → jawab natural tanpa tool\n"
        "- JANGAN bilang 'Saya tidak bisa' untuk hal yang ada toolnya\n"
        "- Respons singkat kalau pesannya singkat, panjang kalau perlu\n"
    )
    
    if is_group:
        base += (
            "\nKamu ada di grup WhatsApp '" + (group_name or "Grup") + "'.\n"
            "- Ikut diskusi seperti anggota grup biasa\n"
            "- Pahami konteks percakapan dari semua anggota\n"
            "- Balas natural, bukan seperti bot menjawab pertanyaan\n"
            "- Bisa nimbrung kalau relevan\n"
        )
    
    # Inject long-term memory
    facts = mem.get_facts_text(context_id)
    if facts:
        base += "\n\n" + facts
    
    return base


# ─── Provider: Gemini ─────────────────────────────────────────────────────────

def _call_gemini(messages: list, system: str, tools: list = None) -> dict:
    if not GEMINI_API_KEY:
        return {"error": "no_key"}
    
    url = f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    # Convert OpenAI-style messages to Gemini format
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": m["content"]}]
        })
    
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 1500,
        }
    }
    
    if tools:
        payload["tools"] = [{"function_declarations": tools}]
        payload["tool_config"] = {"function_calling_config": {"mode": "AUTO"}}
    
    try:
        r = requests.post(url, json=payload, timeout=AI_TIMEOUT)
        if r.status_code == 429:
            return {"error": "rate_limit"}
        if r.status_code == 403:
            return {"error": "quota_exceeded"}
        r.raise_for_status()
        data = r.json()
        
        candidates = data.get("candidates", [])
        if not candidates:
            return {"error": "no_candidates"}
        
        parts = candidates[0].get("content", {}).get("parts", [])
        
        # Cek function calls
        func_calls = []
        text_parts = []
        for p in parts:
            if "functionCall" in p:
                func_calls.append({
                    "name": p["functionCall"]["name"],
                    "args": p["functionCall"].get("args", {})
                })
            elif "text" in p:
                text_parts.append(p["text"])
        
        return {
            "text": "".join(text_parts).strip(),
            "tool_calls": func_calls,
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "raw_content": candidates[0].get("content", {})
        }
        
    except requests.Timeout:
        return {"error": "timeout"}
    except requests.RequestException as e:
        return {"error": str(e)}


def _gemini_tool_response(contents: list, tool_results: list) -> dict:
    """Kirim tool results ke Gemini untuk dapat final response."""
    if not GEMINI_API_KEY:
        return {"error": "no_key"}
    
    url = f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    func_parts = [
        {
            "functionResponse": {
                "name": tr["name"],
                "response": {"result": tr["result"]}
            }
        }
        for tr in tool_results
    ]
    
    new_contents = list(contents) + [{"role": "user", "parts": func_parts}]
    
    payload = {
        "contents": new_contents,
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 1500,
        }
    }
    
    try:
        r = requests.post(url, json=payload, timeout=AI_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return {"error": "no_candidates"}
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
        return {
            "text": text,
            "tool_calls": [],
            "provider": "gemini",
            "model": GEMINI_MODEL,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Provider: Cerebras / Groq (OpenAI-compatible) ───────────────────────────

def _call_openai_compat(
    messages: list,
    system: str,
    api_key: str,
    model: str,
    base_url: str,
    provider_name: str,
    tools: list = None,
) -> dict:
    if not api_key:
        return {"error": "no_key"}
    
    url = base_url + "/chat/completions"
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }
    
    all_messages = [{"role": "system", "content": system}] + messages
    
    # Convert Gemini tool declarations to OpenAI format
    oai_tools = None
    if tools:
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                }
            }
            for t in tools
        ]
    
    payload = {
        "model": model,
        "messages": all_messages,
        "temperature": 0.8,
        "max_tokens": 1500,
    }
    if oai_tools:
        payload["tools"] = oai_tools
        payload["tool_choice"] = "auto"
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=AI_TIMEOUT)
        if r.status_code in (429, 503):
            return {"error": "rate_limit"}
        if r.status_code == 402:
            return {"error": "quota_exceeded"}
        r.raise_for_status()
        data = r.json()
        
        choice = data.get("choices", [{}])[0]
        msg    = choice.get("message", {})
        text   = msg.get("content", "") or ""
        
        # Tool calls
        func_calls = []
        for tc in (msg.get("tool_calls") or []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except:
                args = {}
            func_calls.append({
                "name": fn.get("name", ""),
                "args": args
            })
        
        return {
            "text": text.strip(),
            "tool_calls": func_calls,
            "provider": provider_name,
            "model": model,
        }
        
    except requests.Timeout:
        return {"error": "timeout"}
    except requests.RequestException as e:
        return {"error": str(e)}


# ─── AI Router ────────────────────────────────────────────────────────────────

PROVIDERS = [
    {
        "name": "gemini",
        "call": lambda msgs, sys, tools: _call_gemini(msgs, sys, tools),
    },
    {
        "name": "cerebras",
        "call": lambda msgs, sys, tools: _call_openai_compat(
            msgs, sys, CEREBRAS_API_KEY, CEREBRAS_MODEL, CEREBRAS_BASE, "cerebras", tools
        ),
    },
    {
        "name": "groq",
        "call": lambda msgs, sys, tools: _call_openai_compat(
            msgs, sys, GROQ_API_KEY, GROQ_MODEL, GROQ_BASE, "groq", tools
        ),
    },
]

FATAL_ERRORS = {"no_key"}
RETRY_ERRORS = {"rate_limit", "quota_exceeded", "timeout"}


def _route(messages: list, system: str, tools: list = None) -> tuple:
    """
    Coba provider berurutan: Gemini → Cerebras → Groq.
    Return: (result_dict, provider_name, retry_count, fallback_used)
    """
    retry_count   = 0
    fallback_used = False
    
    for i, provider in enumerate(PROVIDERS):
        if i > 0:
            fallback_used = True
        
        # Skip jika tidak ada API key
        result = provider["call"](messages, system, tools)
        
        if "error" not in result:
            return result, provider["name"], retry_count, fallback_used
        
        err = result["error"]
        if err == "no_key":
            continue  # Skip provider ini
        
        logger.warning("[AI Router] %s error: %s → fallback", provider["name"], err)
        retry_count += 1
    
    return {"error": "all_providers_failed", "text": "Maaf, semua AI provider sedang tidak tersedia."}, "none", retry_count, fallback_used


# ─── Main chat function ───────────────────────────────────────────────────────

def chat(
    context_id: str,
    user_message: str,
    sender_phone: str = "",
    sender_name: str = "",
    is_group: bool = False,
    group_name: str = None,
) -> str:
    t_start = time.time()
    
    # Simpan pesan user
    mem.add_message(context_id, "user", user_message, sender=sender_name if is_group else None)
    mem.upsert_user(sender_phone, sender_name)
    
    # Build system prompt
    system = _build_system_prompt(context_id, is_group, group_name)
    
    # Build message history
    history = mem.get_history(context_id)
    # Convert ke format provider-agnostic
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    
    # ── Gemini dengan Function Calling ────────────────────────────────────────
    # Coba Gemini dulu dengan tool calling, karena paling powerful
    final_text   = None
    provider_used = None
    retry_count  = 0
    fallback_used = False
    error_msg    = None
    
    # Coba function calling dengan Gemini
    if GEMINI_API_KEY:
        gemini_contents = [
            {"role": "user" if m["role"] == "user" else "model",
             "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        
        for iteration in range(MAX_TOOL_ITER):
            result = _call_gemini(messages, system, TOOL_DECLARATIONS)
            
            if "error" in result:
                break  # Fallback ke router tanpa tools
            
            tool_calls = result.get("tool_calls", [])
            
            if not tool_calls:
                final_text    = result.get("text", "")
                provider_used = "gemini"
                break
            
            # Eksekusi tools
            tool_results_for_gemini = []
            for tc in tool_calls:
                t_result = execute_tool(tc["name"], tc["args"], context_id)
                mem.log_tool(context_id, tc["name"], tc["args"], t_result)
                tool_results_for_gemini.append({
                    "name": tc["name"],
                    "result": t_result
                })
                logger.info("[TOOL] %s → %s", tc["name"], str(t_result)[:80])
            
            # Kirim tool results kembali ke Gemini
            # Update contents untuk iterasi berikutnya
            gemini_contents.append(result["raw_content"])
            
            func_parts = [
                {"functionResponse": {"name": tr["name"], "response": {"result": tr["result"]}}}
                for tr in tool_results_for_gemini
            ]
            gemini_contents.append({"role": "user", "parts": func_parts})
            
            # Call Gemini lagi dengan updated contents (tanpa tools agar dapat text)
            url = f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": gemini_contents,
                "generationConfig": {"temperature": 0.8, "maxOutputTokens": 1500}
            }
            try:
                r = requests.post(url, json=payload, timeout=AI_TIMEOUT)
                r.raise_for_status()
                data = r.json()
                cands = data.get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    raw_content = cands[0].get("content", {})
                    text_parts = [p.get("text", "") for p in parts if "text" in p]
                    new_func_calls = [p for p in parts if "functionCall" in p]
                    
                    if new_func_calls:
                        # Ada lagi function calls — loop
                        result["raw_content"] = raw_content
                        result["tool_calls"] = [
                            {"name": p["functionCall"]["name"], "args": p["functionCall"].get("args", {})}
                            for p in new_func_calls
                        ]
                        continue
                    
                    final_text    = "".join(text_parts).strip()
                    provider_used = "gemini"
                    break
            except Exception as e:
                logger.error("Gemini tool-result call: %s", e)
                break
    
    # Fallback ke router (Cerebras / Groq) tanpa tool calling
    if not final_text:
        result, provider_used, retry_count, fallback_used = _route(messages, system, tools=None)
        if "error" in result and result.get("text"):
            final_text = result["text"]
            error_msg  = result.get("error")
        else:
            final_text = result.get("text") or "Maaf, tidak ada respons."
    
    if not final_text:
        final_text = "Maaf, tidak ada respons dari AI."
    
    # Simpan respons ke memory
    mem.add_message(context_id, "assistant", final_text)
    
    # Log
    t_ms = int((time.time() - t_start) * 1000)
    mem.log_ai(
        context_id=context_id,
        is_group=is_group,
        sender_phone=sender_phone,
        sender_name=sender_name,
        prompt=user_message,
        response=final_text,
        provider=provider_used or "unknown",
        model=GEMINI_MODEL if provider_used == "gemini" else (CEREBRAS_MODEL if provider_used == "cerebras" else GROQ_MODEL),
        response_ms=t_ms,
        retry_count=retry_count,
        fallback_used=fallback_used,
        error=error_msg,
    )
    
    logger.info("[AI] %s | %s | %dms | %s chars",
                provider_used, context_id[:20], t_ms, len(final_text))
    
    return final_text
