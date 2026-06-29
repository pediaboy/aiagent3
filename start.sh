#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# PEDIA AI AGENT — start.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Load .env ─────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "❌ File .env tidak ditemukan!"
    echo "   Jalankan: bash install.sh"
    echo "   Lalu edit: nano .env"
    exit 1
fi

# Validasi API keys
source .env 2>/dev/null || true

if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your-gemini-api-key-here" ]; then
    echo "❌ GEMINI_API_KEY belum diset di .env!"
    echo "   Dapatkan gratis di: https://aistudio.google.com/app/apikey"
    exit 1
fi

if [ -z "$TELEGRAM_TOKEN" ] || [ "$TELEGRAM_TOKEN" = "your-telegram-bot-token-here" ]; then
    echo "❌ TELEGRAM_TOKEN belum diset di .env!"
    echo "   Buat bot di: https://t.me/BotFather"
    exit 1
fi

# ── Banner ────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  PEDIA AI AGENT"
echo "  Android 11 · Termux"
echo "========================================"
echo "  Gemini: ${GEMINI_MODEL:-gemini-1.5-flash}"
echo "  Mode: ${1:-telegram}"
echo "========================================"
echo ""

# ── Run ───────────────────────────────────────────────────────
if [ "$1" = "--cli" ]; then
    echo "  Starting CLI mode..."
    echo "  Ketik 'quit' untuk keluar."
    echo ""
    python -m jarvis.main --cli
else
    echo "  Starting Telegram Bot..."
    echo "  Bot aktif. Tekan Ctrl+C untuk berhenti."
    echo ""
    python -m jarvis.main
fi
