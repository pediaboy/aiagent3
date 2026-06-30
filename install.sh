#!/data/data/com.termux/files/usr/bin/bash
# PEDIA AI AGENT v3.0 — install.sh

set -e
echo ""
echo "══════════════════════════════════════════"
echo "  PEDIA AI AGENT v3.0"
echo "  WhatsApp AI Agent + Dashboard"
echo "══════════════════════════════════════════"
echo ""

echo "[1/7] Update packages..."
pkg update -y 2>/dev/null || true

echo "[2/7] Install system packages..."
pkg install -y python nodejs git termux-api ffmpeg chromium openssl libffi 2>/dev/null || true
pkg install -y mpv 2>/dev/null || true

echo "[3/7] Install Node.js packages..."
npm install 2>/dev/null || npm install --legacy-peer-deps

echo "[4/7] Configure Puppeteer..."
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
CHROME=$(which chromium 2>/dev/null || which chromium-browser 2>/dev/null || ls /data/data/com.termux/files/usr/bin/chromium* 2>/dev/null | head -1 || echo "")
if [ -n "$CHROME" ]; then
    echo "  Chrome: $CHROME"
fi

echo "[5/7] Install Python packages..."
pip install --upgrade pip 2>/dev/null || true
pip install -r requirements.txt
pip install yt-dlp 2>/dev/null || true

echo "[6/7] Setup directories..."
mkdir -p data data/wa_session data/media

echo "[7/7] Setup .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    [ -n "$CHROME" ] && echo "CHROME_PATH=$CHROME" >> .env
    echo ""
    echo "  ✅ .env dibuat! Wajib edit sebelum jalan:"
    echo "  nano .env"
else
    echo "  .env sudah ada."
fi

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ Instalasi selesai!"
echo ""
echo "  1. Edit .env → nano .env"
echo "     Isi minimal: GEMINI_API_KEY"
echo "     Ganti: DASHBOARD_SECRET"
echo ""
echo "  2. Jalankan → bash start.sh"
echo "     QR Code muncul untuk login WhatsApp"
echo "     Dashboard: http://localhost:8080"
echo "══════════════════════════════════════════"
echo ""
