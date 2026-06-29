#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# PEDIA AI AGENT — install.sh
# Target: Android 11, Termux, armeabi-v7a (32-bit)
# ============================================================

set -e

echo ""
echo "=========================================="
echo "  PEDIA AI AGENT — Installer"
echo "  Android Termux Setup"
echo "=========================================="
echo ""

# ── Step 1: Update packages ──────────────────────────────────
echo "[1/6] Update package list..."
pkg update -y 2>/dev/null || true

# ── Step 2: Install system packages ──────────────────────────
echo "[2/6] Install sistem dependencies..."
pkg install -y \
    python \
    git \
    termux-api \
    ffmpeg \
    openssl \
    libffi \
    libsqlite \
    clang \
    make \
    2>/dev/null || true

# Optional: mpv untuk playback audio
echo "      Install mpv (opsional, untuk playback audio)..."
pkg install -y mpv 2>/dev/null || echo "      [skip] mpv tidak tersedia di repo ini"

# ── Step 3: Upgrade pip ───────────────────────────────────────
echo "[3/6] Upgrade pip..."
pip install --upgrade pip 2>/dev/null || true

# ── Step 4: Install Python dependencies ──────────────────────
echo "[4/6] Install Python packages..."
pip install -r requirements.txt

# ── Step 5: Install yt-dlp (opsional) ────────────────────────
echo "[5/6] Install yt-dlp (untuk download audio YouTube)..."
pip install yt-dlp 2>/dev/null || echo "      [skip] yt-dlp gagal install"

# ── Step 6: Setup .env ───────────────────────────────────────
echo "[6/6] Setup konfigurasi..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ✅ File .env dibuat dari .env.example"
    echo "  ⚠️  WAJIB edit .env dan isi API key sebelum menjalankan!"
    echo ""
    echo "  Edit dengan: nano .env"
    echo ""
else
    echo "  .env sudah ada, skip."
fi

# Buat direktori data
mkdir -p data

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  ✅ Instalasi selesai!"
echo ""
echo "  Langkah selanjutnya:"
echo "  1. Edit .env: nano .env"
echo "  2. Isi GEMINI_API_KEY dan TELEGRAM_TOKEN"
echo "  3. Jalankan: bash start.sh"
echo ""
echo "  Untuk mode CLI (test tanpa Telegram):"
echo "  bash start.sh --cli"
echo "=========================================="
echo ""
