#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# PEDIA AI AGENT v2.0 — start.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Load .env ─────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "❌ File .env tidak ditemukan!"
    echo "   Jalankan: bash install.sh"
    exit 1
fi

set -a
source .env
set +a

# ── Validasi minimal satu AI key ──────────────────────────────
HAS_AI=false
[ -n "$GEMINI_API_KEY" ]   && [ "$GEMINI_API_KEY" != "your-gemini-api-key-here" ]   && HAS_AI=true
[ -n "$CEREBRAS_API_KEY" ] && [ "$CEREBRAS_API_KEY" != "your-cerebras-api-key-here" ] && HAS_AI=true
[ -n "$GROQ_API_KEY" ]     && [ "$GROQ_API_KEY" != "your-groq-api-key-here" ]        && HAS_AI=true

if [ "$HAS_AI" = "false" ]; then
    echo "❌ Belum ada API key yang di-set di .env!"
    echo ""
    echo "   Minimal satu dari berikut:"
    echo "   GEMINI_API_KEY   → https://aistudio.google.com/app/apikey (GRATIS)"
    echo "   CEREBRAS_API_KEY → https://cloud.cerebras.ai"
    echo "   GROQ_API_KEY     → https://console.groq.com"
    echo ""
    echo "   Edit: nano .env"
    exit 1
fi

# ── Set Chrome path ───────────────────────────────────────────
if [ -z "$CHROME_PATH" ]; then
    CHROME=$(which chromium 2>/dev/null \
        || which chromium-browser 2>/dev/null \
        || ls /data/data/com.termux/files/usr/bin/chromium* 2>/dev/null | head -1 \
        || echo "")
    if [ -n "$CHROME" ]; then
        export CHROME_PATH="$CHROME"
    fi
fi

# ── Banner ────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  PEDIA AI AGENT v2.0"
echo "  WhatsApp AI Agent · Android Termux"
echo "══════════════════════════════════════════"

# Tampilkan provider aktif
PROVIDERS=""
[ -n "$GEMINI_API_KEY" ]   && [ "$GEMINI_API_KEY" != "your-gemini-api-key-here" ]   && PROVIDERS="$PROVIDERS Gemini"
[ -n "$CEREBRAS_API_KEY" ] && [ "$CEREBRAS_API_KEY" != "your-cerebras-api-key-here" ] && PROVIDERS="$PROVIDERS Cerebras"
[ -n "$GROQ_API_KEY" ]     && [ "$GROQ_API_KEY" != "your-groq-api-key-here" ]        && PROVIDERS="$PROVIDERS Groq"

echo "  AI: $PROVIDERS"
echo "  Session: data/wa_session/"
echo ""
echo "  Jika ini pertama kali: scan QR Code dengan WhatsApp."
echo "  Jika sudah pernah login: langsung terhubung otomatis."
echo "══════════════════════════════════════════"
echo ""

# ── Run ───────────────────────────────────────────────────────
if [ "$1" = "--cli" ]; then
    python -m jarvis.main --cli
else
    python -m jarvis.main
fi
