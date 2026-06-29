"""
ai.py — Gemini AI engine dengan Function Calling + Memory + Plugin System
"""
import json
import logging
import re
import requests
from typing import Optional

from jarvis.config import GEMINI_API_KEY, GEMINI_MODEL, AGENT_NAME
from jarvis.tools import TOOL_DECLARATIONS, execute_tool
from jarvis import memory as mem

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_TOOL_ITERATIONS = 5  # Maksimal loop function calling


SYSTEM_PROMPT = f"""Kamu adalah {AGENT_NAME}, AI Agent personal yang berjalan di HP Android via Termux.

Kepribadian:
- Cerdas, singkat, dan to the point
- Bahasa Indonesia santai (boleh campur sedikit Inggris)
- Proaktif: langsung jalankan tool tanpa banyak tanya
- Jujur jika tidak bisa melakukan sesuatu

Kemampuan utama:
- Kontrol Android: buka app, screenshot, flashlight, kamera, volume, brightness
- Musik: putar YouTube, stop musik
- Info device: baterai, RAM, storage, CPU, WiFi
- Alarm/Timer/Reminder
- Browser/Search: web search, cuaca, kurs, baca artikel
- Memory: simpan dan ingat fakta penting
- AI: diskusi, analisis, buat konten, caption, dll

Aturan penting:
- Kalau user minta action (buka app, alarm, dll), langsung pakai tool yang sesuai
- Kalau user minta diskusi/analisis, jawab langsung tanpa tool
- Respons harus SINGKAT dan jelas
- Jangan bilang "saya tidak bisa" untuk hal-hal yang ada toolnya
"""


def _call_gemini_api(contents: list, tools: list = None) -> dict:
    """Raw call ke Gemini API."""
    url = f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
        }
    }
    
    if tools:
        payload["tools"] = [{"function_declarations": tools}]
        payload["tool_config"] = {"function_calling_config": {"mode": "AUTO"}}
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.Timeout:
        return {"error": "Timeout menghubungi Gemini API"}
    except requests.HTTPError as e:
        err_body = ""
        try:
            err_body = r.json().get("error", {}).get("message", "")
        except:
            pass
        return {"error": f"HTTP {r.status_code}: {err_body or str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def _extract_text(response: dict) -> Optional[str]:
    """Ambil teks dari Gemini response."""
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [p.get("text", "") for p in parts if "text" in p]
        return "".join(texts).strip() or None
    except Exception:
        return None


def _extract_function_calls(response: dict) -> list:
    """Ambil function calls dari Gemini response."""
    calls = []
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            return calls
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                calls.append({
                    "name": fc.get("name", ""),
                    "args": fc.get("args", {})
                })
    except Exception as e:
        logger.error("extract_function_calls: %s", e)
    return calls


def chat(user_id: str, user_message: str) -> str:
    """
    Main chat function.
    1. Load history + long-term memory
    2. Call Gemini dengan tools
    3. Kalau ada function call, eksekusi dan kirim hasilnya kembali ke Gemini
    4. Return final text response
    """
    # ── Simpan pesan user ke short-term memory ───────────────────────────────
    mem.add_message(user_id, "user", user_message)
    
    # ── Build contents ────────────────────────────────────────────────────────
    history = mem.get_history(user_id)
    
    # Inject long-term memory ke user message pertama atau sistem
    long_term_text = mem.get_all_facts_text(user_id)
    if long_term_text and len(history) <= 2:
        # Tambahkan sebagai context tambahan
        enriched_system = SYSTEM_PROMPT + f"\n\n{long_term_text}"
    
    contents = history.copy()
    
    # ── Iterasi Function Calling ──────────────────────────────────────────────
    tool_results = []
    
    for iteration in range(MAX_TOOL_ITERATIONS):
        response = _call_gemini_api(contents, TOOL_DECLARATIONS)
        
        if "error" in response:
            error_msg = f"Error Gemini API: {response['error']}"
            logger.error(error_msg)
            return error_msg
        
        # Cek apakah ada function calls
        function_calls = _extract_function_calls(response)
        
        if not function_calls:
            # Tidak ada function call — ambil teks final
            text = _extract_text(response)
            if not text:
                text = "Maaf, tidak ada respons dari AI."
            
            # Simpan respons ke history
            mem.add_message(user_id, "model", text)
            
            # Log tool results ke DB
            for tr in tool_results:
                mem.log_tool(user_id, tr["tool"], tr["args"], tr["result"])
            
            return text
        
        # Ada function calls — eksekusi semua
        # Tambahkan model response ke contents (dengan function calls)
        candidate_content = response["candidates"][0]["content"]
        contents.append(candidate_content)
        
        # Eksekusi setiap function call
        function_response_parts = []
        for fc in function_calls:
            tool_name = fc["name"]
            tool_args = fc["args"]
            
            logger.info("[AI] Tool call: %s(%s)", tool_name, tool_args)
            result = execute_tool(tool_name, tool_args, user_id)
            
            tool_results.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result
            })
            
            function_response_parts.append({
                "functionResponse": {
                    "name": tool_name,
                    "response": {"result": result}
                }
            })
        
        # Kirim tool results kembali ke Gemini
        contents.append({
            "role": "user",
            "parts": function_response_parts
        })
    
    # Kalau sudah MAX_TOOL_ITERATIONS tanpa teks final
    return "Proses selesai. (Maks iterasi tool tercapai)"


def simple_chat(user_id: str, message: str) -> str:
    """Chat tanpa tool calling — untuk mode debug/testing."""
    history = mem.get_history(user_id)
    mem.add_message(user_id, "user", message)
    
    response = _call_gemini_api(history, tools=None)
    
    if "error" in response:
        return f"Error: {response['error']}"
    
    text = _extract_text(response) or "Tidak ada respons."
    mem.add_message(user_id, "model", text)
    return text
