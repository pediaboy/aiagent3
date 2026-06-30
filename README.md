# PEDIA AI AGENT v2.0

**WhatsApp AI Agent** production-ready untuk Android 11 via Termux.

**Target:** Realme C30 · armeabi-v7a (32-bit) · Python 3.13 · Node.js

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/pediaboy/aiagent3.git
cd aiagent3

# 2. Install semua dependencies
bash install.sh

# 3. Isi API key
nano .env

# 4. Jalankan — QR Code muncul otomatis
bash start.sh
```

Scan QR Code dengan WhatsApp. Session tersimpan permanen.

---

## Konfigurasi .env

| Key | Keterangan | Link |
|-----|------------|------|
| `GEMINI_API_KEY` | Google Gemini (GRATIS) | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `CEREBRAS_API_KEY` | Cerebras (fallback) | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| `GROQ_API_KEY` | Groq (fallback) | [console.groq.com](https://console.groq.com) |

Minimal isi satu. AI Router otomatis fallback jika satu gagal.

---

## Fitur

### WhatsApp
- ✅ Chat pribadi — auto reply semua pesan
- ✅ Grup — AI ikut diskusi natural tanpa @mention
- ✅ Session permanen (tidak perlu scan ulang)
- ✅ Typing indicator (simulasi mengetik manusia)
- ✅ Memory per user, per grup

### AI Router (auto-fallback)
```
Gemini → Cerebras → Groq
```
Jika timeout / rate limit / quota habis → otomatis pindah provider.

### Android Control
| Perintah user | Tool |
|--------------|------|
| `buka youtube` | open_app |
| `putar lagu X` | youtube_play |
| `screenshot` | take_screenshot |
| `senter on/off` | flashlight |
| `baterai` / `ram` / `storage` | device info |
| `alarm jam 05:00` | set_alarm |
| `timer 5 menit` | set_timer |
| `cuaca Jakarta` | get_weather |

### Admin Commands (Grup)
```
/ai on        — Aktifkan AI
/ai off       — Nonaktifkan AI
/ai pause     — Jeda AI
/ai resume    — Lanjutkan AI
/ai reset     — Hapus long-term memory
/ai clear     — Hapus history chat
/ai gemini    — Paksa pakai Gemini
/ai groq      — Paksa pakai Groq
/ai auto      — Auto fallback (default)
/ai log       — Lihat log AI
/ai status    — Status AI grup
/ai help      — Bantuan
```

---

## Arsitektur

```
wa_bridge.js          # Node.js WhatsApp Web connection
    │ JSON protocol (stdin/stdout)
    ▼
jarvis/whatsapp.py    # Message handler & bridge manager
    │
    ├── jarvis/ai.py           # AI Router (Gemini/Cerebras/Groq)
    │       └── jarvis/tools.py    # 35+ Android tools
    │
    ├── jarvis/memory.py       # SQLite (short/long term, profiles, logs)
    │
    └── jarvis/android.py      # Termux API control

data/
├── memory.db          # SQLite database
├── wa_session/        # WhatsApp session (permanen)
└── agent.log          # Log file
```

---

## Mode Testing (tanpa WhatsApp)

```bash
bash start.sh --cli
```

---

## Stack

- **Node.js** — whatsapp-web.js (WhatsApp Web automation)
- **Python 3.13** — AI engine, memory, Android control
- **Google Gemini** — AI utama + Function Calling
- **Cerebras** — AI fallback 1
- **Groq** — AI fallback 2
- **SQLite** — Memory database (built-in Python)
- **Termux API** — Android device control
