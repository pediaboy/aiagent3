"""
whatsapp.py — WhatsApp AI Agent handler
Mengelola komunikasi antara wa_bridge.js dan AI engine.
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from queue import Queue, Empty

from jarvis.config import AGENT_NAME, GROUP_AI_ENABLED_DEFAULT
from jarvis.ai import chat
from jarvis import memory as mem

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent

# ─── Admin commands (grup) ───────────────────────────────────────────────────

ADMIN_COMMANDS = {
    # Enable/Disable
    "/ai on":      "enable",
    "/ai off":     "disable",
    "/ai pause":   "pause",
    "/ai resume":  "resume",
    # Memory
    "/ai reset":   "reset_memory",
    "/ai clear":   "clear_history",
    # Provider
    "/ai gemini":  "set_provider_gemini",
    "/ai cerebras":"set_provider_cerebras",
    "/ai groq":    "set_provider_groq",
    "/ai auto":    "set_provider_auto",
    # Info
    "/ai log":     "show_log",
    "/ai status":  "show_status",
    "/ai help":    "show_help",
}


def _is_admin(msg: dict) -> bool:
    """Cek apakah pengirim adalah admin grup."""
    # Untuk kesederhanaan: admin bisa dikenali dari mention atau list
    # Di production: cek via WhatsApp participant isAdmin
    # Saat ini: semua bisa pakai admin command (bisa dikunci nanti)
    return True  # TODO: enforce real admin check via WA participant data


def _handle_admin_command(cmd: str, group_id: str, group_name: str, bridge) -> str:
    action = ADMIN_COMMANDS.get(cmd.lower().strip())
    if not action:
        return None
    
    s = mem.get_group_settings(group_id, group_name)
    
    if action == "enable":
        mem.update_group_setting(group_id, ai_enabled=1, ai_paused=0)
        return "✅ AI diaktifkan di grup ini."
    
    elif action == "disable":
        mem.update_group_setting(group_id, ai_enabled=0)
        return "🔴 AI dinonaktifkan di grup ini."
    
    elif action == "pause":
        mem.update_group_setting(group_id, ai_paused=1)
        return "⏸️ AI dijeda. Ketik /ai resume untuk melanjutkan."
    
    elif action == "resume":
        mem.update_group_setting(group_id, ai_paused=0)
        return "▶️ AI dilanjutkan."
    
    elif action == "reset_memory":
        mem.clear_facts(group_id)
        return "🧠 Long-term memory grup dihapus."
    
    elif action == "clear_history":
        mem.clear_history(group_id)
        return "🗑️ History percakapan grup dihapus."
    
    elif action.startswith("set_provider_"):
        provider = action.replace("set_provider_", "")
        mem.update_group_setting(group_id, provider=provider)
        return "⚙️ Provider AI diganti ke: " + provider
    
    elif action == "show_log":
        logs = mem.get_logs(group_id, limit=5)
        if not logs:
            return "📋 Belum ada log AI."
        lines = ["📋 *AI Log (5 terakhir):*"]
        for log in logs:
            lines.append(
                f"• {log['ts'][:16]} | {log['provider']} | {log['response_ms']}ms | "
                f"{'✅' if not log['error'] else '❌'}"
            )
        return "\n".join(lines)
    
    elif action == "show_status":
        s = mem.get_group_settings(group_id)
        hist_count = mem.get_history_count(group_id)
        facts_count = len(mem.get_facts(group_id))
        return (
            "📊 *Status AI Grup:*\n"
            "Nama: " + group_name + "\n"
            "AI: " + ("✅ Aktif" if s.get("ai_enabled") and not s.get("ai_paused") else "❌ Nonaktif/Jeda") + "\n"
            "Provider: " + s.get("provider", "auto") + "\n"
            "History: " + str(hist_count) + " pesan\n"
            "Memory: " + str(facts_count) + " fakta"
        )
    
    elif action == "show_help":
        return (
            "🤖 *Admin Commands:*\n"
            "/ai on — Aktifkan AI\n"
            "/ai off — Nonaktifkan AI\n"
            "/ai pause — Jeda AI\n"
            "/ai resume — Lanjutkan AI\n"
            "/ai reset — Hapus long-term memory\n"
            "/ai clear — Hapus history chat\n"
            "/ai gemini — Pakai Gemini\n"
            "/ai cerebras — Pakai Cerebras\n"
            "/ai groq — Pakai Groq\n"
            "/ai auto — Auto fallback\n"
            "/ai log — Lihat log AI\n"
            "/ai status — Status AI\n"
            "/ai help — Bantuan ini"
        )
    
    return None


# ─── Message Processor ───────────────────────────────────────────────────────

class WhatsAppAgent:
    def __init__(self):
        self.bridge_proc   = None
        self.message_queue = Queue()
        self.cmd_futures   = {}  # id -> threading.Event + result
        self.ready         = threading.Event()
        self.running       = False
        self._lock         = threading.Lock()

    def start(self):
        """Start wa_bridge.js dan listen events."""
        self.running = True
        
        node_path = self._find_node()
        bridge_path = str(BASE_DIR / "wa_bridge.js")
        
        if not os.path.exists(bridge_path):
            logger.error("wa_bridge.js tidak ditemukan di %s", bridge_path)
            sys.exit(1)
        
        env = os.environ.copy()
        env["TYPING_WPM"] = str(300)
        
        logger.info("Starting wa_bridge.js...")
        self.bridge_proc = subprocess.Popen(
            [node_path, bridge_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # Langsung ke terminal (QR code muncul di sini)
            env=env,
            bufsize=1,
            text=True,
        )
        
        # Thread baca stdout dari bridge
        t_read = threading.Thread(target=self._read_bridge_stdout, daemon=True)
        t_read.start()
        
        # Thread proses pesan
        t_proc = threading.Thread(target=self._process_messages, daemon=True)
        t_proc.start()
        
        logger.info("Bridge started, waiting for WhatsApp ready...")
        self.ready.wait(timeout=300)  # Max 5 menit nunggu scan QR
        
        if self.bridge_proc.poll() is not None:
            logger.error("wa_bridge.js berhenti secara tidak terduga.")
            sys.exit(1)
        
        return self

    def _find_node(self) -> str:
        """Cari path node.js."""
        for path in ["node", "/data/data/com.termux/files/usr/bin/node"]:
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    return path
            except:
                pass
        logger.error("Node.js tidak ditemukan! Install: pkg install nodejs")
        sys.exit(1)

    def _read_bridge_stdout(self):
        """Baca JSON events dari wa_bridge.js stdout."""
        for line in self.bridge_proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                self._handle_bridge_event(event)
            except json.JSONDecodeError:
                pass  # Bukan JSON, skip

    def _handle_bridge_event(self, event: dict):
        t    = event.get("type")
        data = event.get("data", {})
        
        if t == "ready":
            logger.info("WhatsApp ready! Phone: %s (%s)", data.get("phone"), data.get("name"))
            self.ready.set()
        
        elif t == "qr":
            pass  # QR sudah tampil di stderr oleh bridge
        
        elif t == "authenticated":
            logger.info("WhatsApp authenticated!")
        
        elif t == "message":
            self.message_queue.put(data)
        
        elif t == "disconnected":
            logger.warning("WhatsApp disconnected: %s", data.get("reason"))
        
        elif t == "cmd_result":
            cmd_id = data.get("id")
            if cmd_id and cmd_id in self.cmd_futures:
                self.cmd_futures[cmd_id]["result"] = data
                self.cmd_futures[cmd_id]["event"].set()
        
        elif t == "loading":
            logger.debug("Loading: %s%% %s", data.get("percent"), data.get("message"))

    def _process_messages(self):
        """Worker thread: proses pesan dari queue."""
        while self.running:
            try:
                msg = self.message_queue.get(timeout=1.0)
                # Proses dalam thread terpisah agar tidak blocking
                t = threading.Thread(
                    target=self._handle_message,
                    args=(msg,),
                    daemon=True
                )
                t.start()
            except Empty:
                continue
            except Exception as e:
                logger.exception("process_messages error: %s", e)

    def _handle_message(self, msg: dict):
        """Handle satu pesan masuk."""
        try:
            is_group     = msg.get("isGroup", False)
            body         = msg.get("body", "").strip()
            sender_phone = msg.get("senderPhone", "")
            sender_name  = msg.get("senderName", "")
            group_id     = msg.get("groupId")
            group_name   = msg.get("groupName", "")
            from_id      = msg.get("from", "")
            
            # Skip pesan kosong
            if not body:
                return
            
            if is_group:
                context_id = group_id
                
                # Cek settings grup
                s = mem.get_group_settings(group_id, group_name)
                
                # Cek admin commands
                if body.startswith("/ai"):
                    if _is_admin(msg):
                        response = _handle_admin_command(body, group_id, group_name, self)
                        if response:
                            self.send_message(from_id, response)
                            return
                
                # Cek apakah AI enabled
                if not s.get("ai_enabled", 1):
                    return
                if s.get("ai_paused", 0):
                    return
                
                logger.info("[MSG/GROUP] %s (%s): %s", sender_name, group_name, body[:80])
                
            else:
                context_id = sender_phone
                logger.info("[MSG/DM] %s: %s", sender_name or sender_phone, body[:80])
            
            # Generate AI response
            response = chat(
                context_id=context_id,
                user_message=body,
                sender_phone=sender_phone,
                sender_name=sender_name,
                is_group=is_group,
                group_name=group_name,
            )
            
            if response:
                self.send_message(from_id, response)
        
        except Exception as e:
            logger.exception("handle_message error: %s", e)

    def send_message(self, to: str, message: str):
        """Kirim pesan via wa_bridge.js."""
        cmd_id = str(uuid.uuid4())[:8]
        
        event = threading.Event()
        self.cmd_futures[cmd_id] = {"event": event, "result": None}
        
        cmd = json.dumps({
            "id":   cmd_id,
            "type": "send_message",
            "data": {"to": to, "message": message}
        })
        
        try:
            with self._lock:
                self.bridge_proc.stdin.write(cmd + "\n")
                self.bridge_proc.stdin.flush()
            
            # Wait for result (max 15 detik)
            event.wait(timeout=15)
            result = self.cmd_futures.pop(cmd_id, {}).get("result", {})
            
            if not result.get("ok"):
                logger.error("send_message failed: %s", result.get("error"))
        
        except Exception as e:
            logger.error("send_message error: %s", e)
            self.cmd_futures.pop(cmd_id, None)

    def send_image(self, to: str, path: str, caption: str = ""):
        """Kirim gambar via wa_bridge.js."""
        cmd_id = str(uuid.uuid4())[:8]
        event  = threading.Event()
        self.cmd_futures[cmd_id] = {"event": event, "result": None}
        
        cmd = json.dumps({
            "id":   cmd_id,
            "type": "send_image",
            "data": {"to": to, "path": path, "caption": caption}
        })
        
        try:
            with self._lock:
                self.bridge_proc.stdin.write(cmd + "\n")
                self.bridge_proc.stdin.flush()
            event.wait(timeout=15)
        except Exception as e:
            logger.error("send_image error: %s", e)
        finally:
            self.cmd_futures.pop(cmd_id, None)

    def wait(self):
        """Block sampai bridge berhenti."""
        try:
            self.bridge_proc.wait()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        if self.bridge_proc and self.bridge_proc.poll() is None:
            self.bridge_proc.terminate()
            try:
                self.bridge_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.bridge_proc.kill()
        logger.info("WhatsApp agent stopped.")
