#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# PEDIA AI AGENT v2.0 — install.sh
# Target: Android 11, Termux, Realme C30, armeabi-v7a (32-bit)
# ============================================================

set -e

echo ""
echo "══════════════════════════════════════════"
echo "  PEDIA AI AGENT v2.0"
echo "  WhatsApp AI Agent — Installer"
echo "══════════════════════════════════════════"
echo ""

# ── Step 1: Update ───────────────────────────────────────────
echo "[1/7] Update package list..."
pkg update -y 2>/dev/null || true
pkg upgrade -y 2>/dev/null || true

# ── Step 2: System packages ──────────────────────────────────
echo "[2/7] Install system packages..."
pkg install -y \
    python \
    nodejs \
    git \
    termux-api \
    ffmpeg \
    chromium \
    openssl \
    libffi \
    2>/dev/null || true

# Set CHROME_PATH untuk whatsapp-web.js
CHROME_BIN=$(which chromium 2>/dev/null || which chromium-browser 2>/dev/null || echo "")
if [ -n "$CHROME_BIN" ]; then
    echo "  ✅ Chromium: $CHROME_BIN"
    export CHROME_PATH="$CHROME_BIN"
fi

# Optional: mpv untuk audio
echo "      Install mpv (opsional)..."
pkg install -y mpv 2>/dev/null || true

# ── Step 3: Node.js dependencies ─────────────────────────────
echo "[3/7] Install Node.js packages (whatsapp-web.js)..."
npm install --prefer-offline 2>/dev/null || npm install

# ── Step 4: Puppeteer config untuk Android ───────────────────
echo "[4/7] Configure Puppeteer untuk Android Termux..."
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Cek ulang chrome path
CHROME=$(which chromium 2>/dev/null \
    || which chromium-browser 2>/dev/null \
    || ls /data/data/com.termux/files/usr/bin/chromium* 2>/dev/null | head -1 \
    || echo "")

if [ -n "$CHROME" ]; then
    echo "  Chrome: $CHROME"
    # Simpan ke .env agar start.sh bisa baca
    if ! grep -q "CHROME_PATH" .env 2>/dev/null; then
        echo "" >> .env 2>/dev/null || true
        echo "CHROME_PATH=$CHROME" >> .env 2>/dev/null || true
    fi
fi

# ── Step 5: Python packages ───────────────────────────────────
echo "[5/7] Install Python packages..."
pip install --upgrade pip 2>/dev/null || true
pip install -r requirements.txt

# Optional: yt-dlp
echo "      Install yt-dlp (opsional, untuk download audio)..."
pip install yt-dlp 2>/dev/null || echo "      [skip] yt-dlp gagal"

# ── Step 6: Setup directories ─────────────────────────────────
echo "[6/7] Setup direktori..."
mkdir -p data
mkdir -p data/wa_session

# ── Step 7: Setup .env ───────────────────────────────────────
echo "[7/7] Setup konfigurasi..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ✅ File .env dibuat dari .env.example"
    if [ -n "$CHROME" ]; then
        echo "CHROME_PATH=$CHROME" >> .env
    fi
    echo ""
    echo "  ⚠️  WAJIB edit .env sebelum menjalankan!"
    echo "  nano .env"
else
    echo "  .env sudah ada."
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  ✅ Instalasi selesai!"
echo ""
echo "  Langkah selanjutnya:"
echo "  1. Edit .env  →  nano .env"
echo "  2. Isi minimal satu API key:"
echo "     GEMINI_API_KEY   → https://aistudio.google.com/app/apikey"
echo "     CEREBRAS_API_KEY → https://cloud.cerebras.ai"
echo "     GROQ_API_KEY     → https://console.groq.com"
echo "  3. Jalankan  →  bash start.sh"
echo ""
echo "  QR Code akan muncul otomatis untuk login WhatsApp."
echo "  Session disimpan permanen setelah scan."
echo "══════════════════════════════════════════"
echo ""
