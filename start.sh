#!/data/data/com.termux/files/usr/bin/bash
# PEDIA AI AGENT v3.0 — start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f ".env" ]; then
    echo "❌ .env tidak ditemukan! Jalankan: bash install.sh"
    exit 1
fi

set -a; source .env; set +a

HAS_AI=false
[ -n "$GEMINI_API_KEY" ]   && [ "$GEMINI_API_KEY" != "your-gemini-api-key-here" ]   && HAS_AI=true
[ -n "$CEREBRAS_API_KEY" ] && [ "$CEREBRAS_API_KEY" != "your-cerebras-api-key-here" ] && HAS_AI=true
[ -n "$GROQ_API_KEY" ]     && [ "$GROQ_API_KEY" != "your-groq-api-key-here" ]        && HAS_AI=true

if [ "$HAS_AI" = "false" ]; then
    echo "❌ Isi minimal satu API key di .env!"
    echo "   GEMINI_API_KEY → https://aistudio.google.com/app/apikey (GRATIS)"
    exit 1
fi

if [ -z "$CHROME_PATH" ]; then
    CHROME=$(which chromium 2>/dev/null || which chromium-browser 2>/dev/null || echo "")
    [ -n "$CHROME" ] && export CHROME_PATH="$CHROME"
fi

echo ""
echo "══════════════════════════════════════════"
echo "  PEDIA AI AGENT v3.0"
echo "══════════════════════════════════════════"
[ -n "$GEMINI_API_KEY"   ] && [ "$GEMINI_API_KEY"   != "your-gemini-api-key-here"   ] && echo "  ✅ Gemini"
[ -n "$CEREBRAS_API_KEY" ] && [ "$CEREBRAS_API_KEY" != "your-cerebras-api-key-here" ] && echo "  ✅ Cerebras"
[ -n "$GROQ_API_KEY"     ] && [ "$GROQ_API_KEY"     != "your-groq-api-key-here"     ] && echo "  ✅ Groq"
echo "  📊 Dashboard: http://localhost:${DASHBOARD_PORT:-8080}"
echo "══════════════════════════════════════════"
echo ""

if [ "$1" = "--cli" ]; then
    python -m jarvis.main --cli
elif [ "$1" = "--dashboard" ]; then
    python -m jarvis.main --dashboard-only
else
    python -m jarvis.main
fi
