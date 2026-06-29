"""
telegram.py — Telegram Bot handler
Semua pesan user → AI → eksekusi tool → balas ke Telegram
"""
import logging
import os
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction, ParseMode

from jarvis.config import TELEGRAM_TOKEN, ALLOWED_USER_IDS, AGENT_NAME
from jarvis.ai import chat
from jarvis import memory as mem
from jarvis.android import get_screenshot_path

logger = logging.getLogger(__name__)


def _check_allowed(user_id: int) -> bool:
    """Cek apakah user diizinkan pakai bot."""
    if not ALLOWED_USER_IDS:
        return True  # Kalau kosong, semua boleh
    return user_id in ALLOWED_USER_IDS


async def _send_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )


# ─── Commands ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _check_allowed(user.id):
        await update.message.reply_text("❌ Kamu tidak diizinkan menggunakan bot ini.")
        return
    
    text = (
        f"👋 Halo {user.first_name}!\n\n"
        f"Aku *{AGENT_NAME}*, AI Agent kamu yang berjalan langsung di HP Android.\n\n"
        f"Yang bisa aku lakukan:\n"
        f"• Buka app (youtube, whatsapp, telegram, dll)\n"
        f"• Putar lagu dari YouTube\n"
        f"• Cek baterai, RAM, storage\n"
        f"• Set alarm, timer, reminder\n"
        f"• Screenshot, flashlight, kamera\n"
        f"• Cari info, cuaca, kurs\n"
        f"• Diskusi & buat konten\n\n"
        f"Ketik /help untuk bantuan lebih lanjut."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_allowed(update.effective_user.id):
        return
    
    text = (
        f"*📱 Perintah {AGENT_NAME}:*\n\n"
        f"*App & Media:*\n"
        f"`buka youtube` `buka whatsapp` `buka chrome`\n"
        f"`putar lagu noah separuh aku`\n"
        f"`stop musik`\n\n"
        f"*Device:*\n"
        f"`status hp` `baterai` `ram` `storage` `cpu`\n"
        f"`screenshot` `flashlight on/off`\n"
        f"`wifi info` `brightness 200`\n\n"
        f"*Alarm & Timer:*\n"
        f"`alarm jam 05:00`\n"
        f"`reminder jam 3 sore makan obat`\n"
        f"`timer 5 menit`\n\n"
        f"*Web & Info:*\n"
        f"`cuaca Jakarta` `kurs USD`\n"
        f"`cari [query]` `baca [url]`\n\n"
        f"*Memory:*\n"
        f"`ingat: [fakta]` `tampilkan memori`\n\n"
        f"*System:*\n"
        f"/start - Mulai\n"
        f"/clear - Hapus history chat\n"
        f"/memory - Tampilkan long-term memory\n"
        f"/status - Status koneksi AI\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_allowed(update.effective_user.id):
        return
    user_id = str(update.effective_user.id)
    mem.clear_history(user_id)
    await update.message.reply_text("🗑️ History percakapan dihapus. Mulai baru!")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_allowed(update.effective_user.id):
        return
    user_id = str(update.effective_user.id)
    facts = mem.get_facts(user_id)
    if not facts:
        await update.message.reply_text("🧠 Belum ada fakta tersimpan di long-term memory.")
        return
    text = "🧠 *Long-term Memory:*\n\n" + "\n".join(f"• {f}" for f in facts)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_allowed(update.effective_user.id):
        return
    from jarvis.config import GEMINI_API_KEY, GEMINI_MODEL
    user_id = str(update.effective_user.id)
    history_count = len(mem.get_history(user_id))
    facts_count   = len(mem.get_facts(user_id))
    
    text = (
        f"✅ *{AGENT_NAME} Status:*\n\n"
        f"AI Model  : `{GEMINI_MODEL}`\n"
        f"API Key   : `{'✓ Set' if GEMINI_API_KEY else '✗ Missing'}`\n"
        f"History   : {history_count} pesan\n"
        f"Memory    : {facts_count} fakta\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── Message Handler ──────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua pesan teks — dikirim ke AI."""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    if not _check_allowed(user.id):
        await update.message.reply_text("❌ Tidak diizinkan.")
        return
    
    user_id   = str(user.id)
    user_text = update.message.text.strip()
    
    logger.info("[MSG] User %s: %s", user_id, user_text[:100])
    
    # Tampilkan typing indicator
    await _send_typing(update, context)
    
    # Proses via AI
    try:
        response = chat(user_id, user_text)
    except Exception as e:
        logger.exception("chat() error: %s", e)
        response = f"⚠️ Error internal: {str(e)}"
    
    if not response:
        response = "Maaf, tidak ada respons."
    
    # Kirim respons (potong kalau terlalu panjang)
    MAX_LEN = 4096
    if len(response) > MAX_LEN:
        parts = [response[i:i+MAX_LEN] for i in range(0, len(response), MAX_LEN)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(response)
    
    # Cek kalau ada perintah screenshot → kirim file
    if "screenshot" in user_text.lower() and "disimpan" in response.lower():
        await _try_send_screenshot(update, context)


async def _try_send_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Coba kirim file screenshot ke Telegram."""
    try:
        path = get_screenshot_path()
        if path and os.path.exists(path):
            await _send_typing(update, context)
            with open(path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=f,
                    caption="📸 Screenshot"
                )
    except Exception as e:
        logger.error("send_screenshot: %s", e)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle foto yang dikirim user."""
    if not _check_allowed(update.effective_user.id):
        return
    caption = update.message.caption or "Apa yang ada di foto ini?"
    await update.message.reply_text(f"📸 Foto diterima. Caption: {caption}\n(Analisis gambar membutuhkan Gemini Vision — akan diimplementasi)")


# ─── Bot Runner ───────────────────────────────────────────────────────────────

def run_bot():
    """Start Telegram bot (blocking)."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN tidak di-set!")
        return
    
    logger.info("Starting Telegram bot...")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("clear",  cmd_clear))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("status", cmd_status))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Set bot commands (akan muncul di menu Telegram)
    async def post_init(app):
        await app.bot.set_my_commands([
            BotCommand("start",  "Mulai / Perkenalan"),
            BotCommand("help",   "Bantuan & daftar perintah"),
            BotCommand("clear",  "Hapus history percakapan"),
            BotCommand("memory", "Tampilkan long-term memory"),
            BotCommand("status", "Status koneksi AI"),
        ])
    
    app.post_init = post_init
    
    logger.info("Bot running! Tekan Ctrl+C untuk berhenti.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
