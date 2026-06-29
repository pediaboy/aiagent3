# PEDIA AI AGENT

AI Agent production-ready untuk Android 11 via Termux.

**Target device:** Realme C30 · armeabi-v7a (32-bit) · Python 3.13

---

## Quick Start

```bash
# 1. Clone repo
git clone https://github.com/pediaboy/aiagent3.git
cd aiagent3

# 2. Install semua dependencies
bash install.sh

# 3. Edit konfigurasi
nano .env

# 4. Jalankan
bash start.sh
```

## Konfigurasi .env

| Key | Keterangan | Link |
|-----|------------|------|
| `GEMINI_API_KEY` | Google Gemini API key | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `TELEGRAM_TOKEN` | Bot token dari @BotFather | [t.me/BotFather](https://t.me/BotFather) |
| `ALLOWED_USER_IDS` | User ID Telegram kamu | [t.me/userinfobot](https://t.me/userinfobot) |
| `GEMINI_MODEL` | Model AI (default: gemini-1.5-flash) | - |
| `AGENT_NAME` | Nama agent (default: Pedia) | - |

---

## Stack

- **Python 3.13** — Termux compatible
- **Gemini API** — AI engine + Function Calling
- **python-telegram-bot** — Telegram interface
- **SQLite** — Memory (built-in Python)
- **Termux API** — Android device control
- **requests** — HTTP client

---

## Fitur

### Android Control
| Perintah | Fungsi |
|----------|--------|
| `buka youtube` | Buka aplikasi |
| `screenshot` | Ambil screenshot |
| `flashlight on` | Nyalakan senter |
| `baterai` | Cek baterai |
| `ram` `storage` `cpu` | Info device |
| `wifi info` | Info koneksi WiFi |
| `brightness 200` | Set kecerahan |
| `clipboard` | Baca/set clipboard |

### Alarm & Timer
| Perintah | Fungsi |
|----------|--------|
| `alarm jam 05:00` | Set alarm |
| `reminder jam 3 sore makan obat` | Set reminder |
| `timer 5 menit` | Countdown timer |

### Musik
| Perintah | Fungsi |
|----------|--------|
| `putar lagu noah separuh aku` | Putar dari YouTube |
| `stop musik` | Hentikan musik |

### Web & Info
| Perintah | Fungsi |
|----------|--------|
| `cuaca Bandung` | Info cuaca |
| `kurs USD` | Kurs mata uang |
| `cari [query]` | Web search |

### AI & Diskusi
- Diskusi bandarmologi, analisis saham
- Buat caption Instagram
- Terjemahan
- Semua pertanyaan umum

---

## Struktur File

```
jarvis/
├── main.py       # Entry point
├── ai.py         # Gemini engine + Function Calling
├── telegram.py   # Telegram Bot handler
├── memory.py     # SQLite memory (short + long term)
├── tools.py      # Tool registry & executor
├── android.py    # Android/Termux API control
├── browser.py    # Web search, weather, scraping
├── music.py      # YouTube audio playback
├── alarm.py      # Alarm, timer, reminder
└── config.py     # Config loader

data/
├── memory.db     # Database SQLite
└── agent.log     # Log file
```

---

## Mode CLI (Testing)

```bash
# Test tanpa Telegram
bash start.sh --cli

# Atau langsung:
python -m jarvis.main --cli
```

---

## Telegram Commands

| Command | Fungsi |
|---------|--------|
| `/start` | Mulai & perkenalan |
| `/help` | Daftar perintah |
| `/clear` | Hapus history chat |
| `/memory` | Tampilkan long-term memory |
| `/status` | Status koneksi AI |
