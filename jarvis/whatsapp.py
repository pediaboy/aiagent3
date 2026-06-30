"""
whatsapp.py — WhatsApp Agent v3.0
Auto reply semua pesan, tanpa command/prefix/mention.
Semua konfigurasi via Dashboard.
"""
import json, logging, os, subprocess, sys, threading, time, uuid
from pathlib import Path
from queue import Queue, Empty

from jarvis.config import AGENT_NAME
from jarvis.ai import chat, transcribe_audio, analyze_image
from jarvis import memory as mem

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent


class WhatsAppAgent:
    def __init__(self, session_id="default"):
        self.session_id    = session_id
        self.bridge_proc   = None
        self.msg_queue     = Queue()
        self.cmd_futures   = {}
        self.ready         = threading.Event()
        self.running       = False
        self._lock         = threading.Lock()
        self._phone        = None
        self._name         = None

    def start(self):
        self.running = True
        node = self._find_node()
        bridge = str(BASE_DIR / "wa_bridge.js")
        if not os.path.exists(bridge):
            logger.error("wa_bridge.js tidak ditemukan!")
            sys.exit(1)

        env = os.environ.copy()
        env["TYPING_WPM"] = "250"

        logger.info("[%s] Starting wa_bridge.js...", self.session_id)
        self.bridge_proc = subprocess.Popen(
            [node, bridge],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            env=env, bufsize=1, text=True,
        )

        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._process_queue, daemon=True).start()

        logger.info("[%s] Waiting for WhatsApp ready...", self.session_id)
        self.ready.wait(timeout=300)

        if self.bridge_proc.poll() is not None:
            logger.error("[%s] Bridge exited unexpectedly.", self.session_id)
            sys.exit(1)

        mem.upsert_session(self.session_id,
                           phone=self._phone or "",
                           name=self._name or "",
                           status="connected")
        return self

    def _find_node(self):
        for p in ["node", "/data/data/com.termux/files/usr/bin/node"]:
            try:
                r = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=3)
                if r.returncode == 0: return p
            except: pass
        logger.error("Node.js tidak ditemukan!")
        sys.exit(1)

    def _read_stdout(self):
        for line in self.bridge_proc.stdout:
            line = line.strip()
            if not line: continue
            try:
                event = json.loads(line)
                self._handle_event(event)
            except: pass

    def _handle_event(self, event):
        t    = event.get("type")
        data = event.get("data", {})
        if t == "ready":
            self._phone = data.get("phone")
            self._name  = data.get("name")
            logger.info("[%s] Ready! %s (%s)", self.session_id, self._phone, self._name)
            self.ready.set()
        elif t == "message":
            self.msg_queue.put(data)
        elif t == "disconnected":
            logger.warning("[%s] Disconnected: %s", self.session_id, data.get("reason"))
            mem.upsert_session(self.session_id, status="disconnected")
        elif t == "cmd_result":
            cid = data.get("id")
            if cid and cid in self.cmd_futures:
                self.cmd_futures[cid]["result"] = data
                self.cmd_futures[cid]["event"].set()
        elif t == "authenticated":
            mem.upsert_session(self.session_id, status="authenticated")

    def _process_queue(self):
        while self.running:
            try:
                msg = self.msg_queue.get(timeout=1.0)
                threading.Thread(target=self._handle_message, args=(msg,), daemon=True).start()
            except Empty:
                continue
            except Exception as e:
                logger.exception("queue error: %s", e)

    def _handle_message(self, msg):
        try:
            is_group    = msg.get("isGroup", False)
            body        = (msg.get("body") or "").strip()
            sender_phone= msg.get("senderPhone", "")
            sender_name = msg.get("senderName", "") or sender_phone
            group_id    = msg.get("groupId")
            group_name  = msg.get("groupName", "")
            from_id     = msg.get("from", "")
            msg_id      = msg.get("id")
            media_path  = msg.get("mediaPath")
            media_mime  = msg.get("mediaMime", "")
            quoted_body = msg.get("quotedBody")
            msg_type    = msg.get("type", "chat")

            context_id = group_id if is_group else sender_phone

            # ── Group settings check ───────────────────────────────────────────
            if is_group:
                s = mem.get_group_settings(group_id, group_name, self.session_id)
                if not s.get("ai_enabled", 1): return
                if s.get("ai_paused", 0): return

            # ── Personality ───────────────────────────────────────────────────
            personality = "default"
            if not is_group:
                user = mem.get_user(sender_phone, self.session_id)
                personality = user.get("personality", "default") or "default"
            else:
                s = mem.get_group_settings(group_id, group_name, self.session_id)
                personality = s.get("personality", "default") or "default"

            # ── Build user message ────────────────────────────────────────────
            image_data = None
            image_mime_type = None
            final_message = body

            if msg_type == "ptt" or (media_mime and "audio" in media_mime):
                # Voice note → transkripsi
                if media_path and os.path.exists(media_path):
                    transcript = transcribe_audio(media_path)
                    final_message = "[Voice Note]: " + transcript
                    logger.info("[%s] Voice transcribed: %s", self.session_id, transcript[:60])
                elif not body:
                    return

            elif msg_type in ("image","sticker") or (media_mime and "image" in media_mime):
                # Gambar → analisis
                if media_path and os.path.exists(media_path):
                    analysis = analyze_image(media_path, body or "Jelaskan gambar ini.")
                    final_message = "[Gambar diterima]\n" + analysis
                    if body:
                        final_message = body + "\n\n" + analysis
                elif not body:
                    return

            elif media_path and (media_mime or "").startswith("application/"):
                # Dokumen/PDF
                final_message = (body or "") + "\n[Dokumen diterima: " + os.path.basename(media_path) + "]"
            
            if not final_message and not body:
                return

            # Tambahkan konteks quoted message
            if quoted_body and quoted_body != body:
                final_message = "(Membalas: \"" + quoted_body[:100] + "\")\n" + final_message

            logger.info("[MSG] %s | %s | %s: %s",
                        self.session_id,
                        "GROUP:" + (group_name or "") if is_group else "DM",
                        sender_name, final_message[:80])

            # ── AI response ────────────────────────────────────────────────────
            response = chat(
                context_id=context_id,
                user_message=final_message,
                sender_phone=sender_phone,
                sender_name=sender_name,
                is_group=is_group,
                group_name=group_name,
                session_id=self.session_id,
                image_data=image_data,
                image_mime=image_mime_type,
                personality_name=personality,
            )

            if response:
                self.send_message(from_id, response, quote_id=msg_id)

        except Exception as e:
            logger.exception("handle_message error: %s", e)

    def send_message(self, to, message, quote_id=None):
        cmd_id = str(uuid.uuid4())[:8]
        ev = threading.Event()
        self.cmd_futures[cmd_id] = {"event": ev, "result": None}
        cmd = json.dumps({"id": cmd_id, "type": "send_message",
                          "data": {"to": to, "message": message, "quote_id": quote_id}})
        try:
            with self._lock:
                self.bridge_proc.stdin.write(cmd + "\n")
                self.bridge_proc.stdin.flush()
            ev.wait(timeout=20)
        except Exception as e:
            logger.error("send_message: %s", e)
        finally:
            self.cmd_futures.pop(cmd_id, None)

    def send_image(self, to, path, caption=""):
        cmd_id = str(uuid.uuid4())[:8]
        ev = threading.Event()
        self.cmd_futures[cmd_id] = {"event": ev, "result": None}
        cmd = json.dumps({"id": cmd_id, "type": "send_image",
                          "data": {"to": to, "path": path, "caption": caption}})
        try:
            with self._lock:
                self.bridge_proc.stdin.write(cmd + "\n")
                self.bridge_proc.stdin.flush()
            ev.wait(timeout=20)
        except Exception as e:
            logger.error("send_image: %s", e)
        finally:
            self.cmd_futures.pop(cmd_id, None)

    def wait(self):
        try:
            self.bridge_proc.wait()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        mem.upsert_session(self.session_id, status="disconnected")
        if self.bridge_proc and self.bridge_proc.poll() is None:
            self.bridge_proc.terminate()
            try:
                self.bridge_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.bridge_proc.kill()
