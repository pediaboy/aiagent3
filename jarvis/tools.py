"""
tools.py — Tool registry untuk Gemini Function Calling
Setiap tool didefinisikan sebagai Gemini FunctionDeclaration.
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ─── Tool Definitions (Gemini Function Calling format) ────────────────────────

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Buka aplikasi Android berdasarkan nama. Contoh: youtube, whatsapp, telegram, chrome, instagram, tiktok, spotify, gojek, shopee, tokopedia, camera, settings, calculator, gmail, clock, playstore, facebook, line, zoom, maps.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Nama aplikasi yang ingin dibuka"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "open_url",
        "description": "Buka URL atau website di browser Chrome",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL yang ingin dibuka, contoh: google.com atau https://..."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "youtube_play",
        "description": "Putar atau cari lagu/video di YouTube. Gunakan untuk: 'putar lagu X', 'play Y', 'cari lagu Z di youtube'.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Judul lagu atau nama artis yang ingin diputar"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "stop_music",
        "description": "Hentikan musik yang sedang diputar",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_battery",
        "description": "Cek status baterai HP: persentase, status charging, suhu, kesehatan baterai",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_ram",
        "description": "Cek penggunaan RAM: total, terpakai, tersisa",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_storage",
        "description": "Cek storage internal: total, terpakai, tersisa",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_cpu",
        "description": "Cek info CPU: model, jumlah core, frekuensi",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_device_info",
        "description": "Cek info lengkap perangkat: brand, model, Android version, SDK",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_system_status",
        "description": "Status lengkap sistem HP: baterai + RAM + storage sekaligus",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "take_screenshot",
        "description": "Ambil screenshot layar HP",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "open_camera",
        "description": "Buka kamera dan ambil foto",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "flashlight_on",
        "description": "Nyalakan flashlight / senter HP",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "flashlight_off",
        "description": "Matikan flashlight / senter HP",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_clipboard",
        "description": "Baca isi clipboard saat ini",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "set_clipboard",
        "description": "Set/copy teks ke clipboard",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Teks yang ingin disalin ke clipboard"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "get_volume",
        "description": "Cek level volume semua stream (media, ring, notification, alarm)",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "set_brightness",
        "description": "Set kecerahan layar (0-255)",
        "parameters": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "Level kecerahan 0-255. 0=gelap, 128=sedang, 255=terang"
                }
            },
            "required": ["level"]
        }
    },
    {
        "name": "get_wifi",
        "description": "Cek info koneksi WiFi: SSID, IP, kekuatan sinyal",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "set_alarm",
        "description": "Set alarm pada waktu tertentu. Contoh: '05:00', '07:30', '5 pagi', '3 sore'",
        "parameters": {
            "type": "object",
            "properties": {
                "time_str": {
                    "type": "string",
                    "description": "Waktu alarm, contoh: '05:00', '07:30', '5 pagi'"
                },
                "label": {
                    "type": "string",
                    "description": "Label alarm, default: Alarm"
                }
            },
            "required": ["time_str"]
        }
    },
    {
        "name": "set_reminder",
        "description": "Set reminder dengan pesan pada waktu tertentu",
        "parameters": {
            "type": "object",
            "properties": {
                "time_str": {
                    "type": "string",
                    "description": "Waktu reminder, contoh: '14:00', '3 sore'"
                },
                "message": {
                    "type": "string",
                    "description": "Pesan reminder yang akan muncul"
                }
            },
            "required": ["time_str", "message"]
        }
    },
    {
        "name": "set_timer",
        "description": "Set countdown timer. Contoh: '5 menit', '1 jam', '30 detik', '1 jam 30 menit'",
        "parameters": {
            "type": "object",
            "properties": {
                "duration_str": {
                    "type": "string",
                    "description": "Durasi timer, contoh: '5 menit', '1 jam 30 menit'"
                },
                "label": {
                    "type": "string",
                    "description": "Label timer"
                }
            },
            "required": ["duration_str"]
        }
    },
    {
        "name": "get_time",
        "description": "Cek waktu dan tanggal sekarang",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "web_search",
        "description": "Cari informasi di internet via DuckDuckGo",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query pencarian"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": "Cek cuaca kota tertentu: suhu, kondisi, kelembaban, angin",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Nama kota, contoh: Jakarta, Bandung, Surabaya"
                }
            }
        }
    },
    {
        "name": "fetch_webpage",
        "description": "Ambil dan baca isi halaman web / artikel dari URL",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL halaman yang ingin dibaca"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "get_exchange_rate",
        "description": "Cek kurs mata uang, contoh: USD ke IDR, EUR ke IDR",
        "parameters": {
            "type": "object",
            "properties": {
                "from_currency": {
                    "type": "string",
                    "description": "Mata uang asal, contoh: USD, EUR, SGD"
                },
                "to_currency": {
                    "type": "string",
                    "description": "Mata uang tujuan, contoh: IDR, USD"
                }
            }
        }
    },
    {
        "name": "translate",
        "description": "Terjemahkan teks ke bahasa lain",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Teks yang ingin diterjemahkan"
                },
                "target_lang": {
                    "type": "string",
                    "description": "Kode bahasa tujuan: id (Indonesia), en (Inggris), ja (Jepang), dll"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "send_notification",
        "description": "Kirim notifikasi ke Android",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Judul notifikasi"},
                "content": {"type": "string", "description": "Isi notifikasi"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "get_location",
        "description": "Ambil lokasi GPS perangkat saat ini",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "save_memory",
        "description": "Simpan fakta penting ke long-term memory agar bisa diingat di percakapan berikutnya",
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "Fakta yang ingin diingat"
                },
                "category": {
                    "type": "string",
                    "description": "Kategori: personal, preference, task, general"
                }
            },
            "required": ["fact"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Cari dan tampilkan fakta dari long-term memory",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Kategori memory yang ingin diingat (opsional)"
                }
            }
        }
    },
    {
        "name": "clear_chat_history",
        "description": "Hapus history percakapan dan mulai dari awal",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_sms",
        "description": "Baca SMS inbox terbaru",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Jumlah SMS yang ingin ditampilkan (default 5)"
                }
            }
        }
    },
    {
        "name": "search_contact",
        "description": "Cari kontak di phonebook berdasarkan nama",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nama kontak yang dicari"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "open_whatsapp_chat",
        "description": "Buka WhatsApp, opsional langsung ke chat dengan nomor tertentu",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {
                    "type": "string",
                    "description": "Nomor telepon (opsional), contoh: 08123456789 atau 6281234567890"
                }
            }
        }
    },
    {
        "name": "list_songs",
        "description": "Tampilkan daftar lagu yang sudah didownload",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
]


# ─── Tool Executor ────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, args: dict, user_id: str = None) -> str:
    """
    Eksekusi tool berdasarkan nama dan argumen.
    Dipanggil oleh ai.py ketika Gemini mengembalikan function call.
    """
    # Import lazy agar tidak ada circular import
    from jarvis import android, alarm, browser, music, memory

    logger.info("[TOOL] %s(%s)", tool_name, args)

    try:
        # ── App & URL ────────────────────────────────────────────────────────
        if tool_name == "open_app":
            return android.open_app(args.get("app_name", ""))

        elif tool_name == "open_url":
            return android.open_url(args.get("url", ""))

        elif tool_name == "open_whatsapp_chat":
            return android.open_whatsapp_chat(args.get("phone"))

        # ── Music ────────────────────────────────────────────────────────────
        elif tool_name == "youtube_play":
            result = music.play_youtube(args.get("query", ""))
            # Juga buka di browser sebagai fallback visual
            from jarvis.android import open_youtube_search
            open_youtube_search(args.get("query", ""))
            return result

        elif tool_name == "stop_music":
            return music.stop_music()

        elif tool_name == "list_songs":
            return music.list_downloaded()

        # ── Device Info ──────────────────────────────────────────────────────
        elif tool_name == "get_battery":
            return android.get_battery()

        elif tool_name == "get_ram":
            return android.get_ram_info()

        elif tool_name == "get_storage":
            return android.get_storage_info()

        elif tool_name == "get_cpu":
            return android.get_cpu_info()

        elif tool_name == "get_device_info":
            return android.get_device_info()

        elif tool_name == "get_system_status":
            return android.get_system_status()

        # ── Hardware Control ─────────────────────────────────────────────────
        elif tool_name == "take_screenshot":
            return android.take_screenshot()

        elif tool_name == "open_camera":
            return android.open_camera()

        elif tool_name == "flashlight_on":
            return android.flashlight_on()

        elif tool_name == "flashlight_off":
            return android.flashlight_off()

        elif tool_name == "get_clipboard":
            return android.get_clipboard()

        elif tool_name == "set_clipboard":
            return android.set_clipboard(args.get("text", ""))

        elif tool_name == "get_volume":
            return android.get_volume()

        elif tool_name == "set_brightness":
            return android.set_brightness(int(args.get("level", 128)))

        elif tool_name == "get_wifi":
            return android.get_wifi_info()

        elif tool_name == "get_location":
            return android.get_location()

        elif tool_name == "send_notification":
            return android.send_notification(
                args.get("title", "Pedia Agent"),
                args.get("content", "")
            )

        elif tool_name == "get_sms":
            return android.get_sms_inbox(int(args.get("limit", 5)))

        elif tool_name == "search_contact":
            return android.search_contact(args.get("name", ""))

        # ── Alarm/Timer ──────────────────────────────────────────────────────
        elif tool_name == "set_alarm":
            return alarm.set_alarm(
                args.get("time_str", ""),
                args.get("label", "Alarm")
            )

        elif tool_name == "set_reminder":
            return alarm.set_reminder(
                args.get("time_str", ""),
                args.get("message", "")
            )

        elif tool_name == "set_timer":
            return alarm.set_timer(
                args.get("duration_str", ""),
                args.get("label", "Timer")
            )

        elif tool_name == "get_time":
            return alarm.get_current_time()

        # ── Web/Browser ──────────────────────────────────────────────────────
        elif tool_name == "web_search":
            return browser.google_search(args.get("query", ""))

        elif tool_name == "get_weather":
            return browser.get_weather(args.get("city", "Jakarta"))

        elif tool_name == "fetch_webpage":
            return browser.fetch_page_text(args.get("url", ""))

        elif tool_name == "get_exchange_rate":
            return browser.get_exchange_rate(
                args.get("from_currency", "USD"),
                args.get("to_currency", "IDR")
            )

        elif tool_name == "translate":
            return browser.translate_text(
                args.get("text", ""),
                args.get("target_lang", "id")
            )

        # ── Memory ──────────────────────────────────────────────────────────
        elif tool_name == "save_memory":
            if user_id:
                memory.save_fact(
                    user_id,
                    args.get("fact", ""),
                    args.get("category", "general")
                )
                return f"✅ Disimpan ke memori: {args.get('fact', '')}"
            return "user_id tidak tersedia untuk simpan memori."

        elif tool_name == "recall_memory":
            if user_id:
                facts = memory.get_facts(user_id, args.get("category"))
                if not facts:
                    return "Belum ada fakta yang tersimpan di memori."
                return "🧠 Memori saya tentang kamu:\n" + "\n".join(f"- {f}" for f in facts)
            return "user_id tidak tersedia."

        elif tool_name == "clear_chat_history":
            if user_id:
                memory.clear_history(user_id)
                return "🗑️ History percakapan dihapus."
            return "user_id tidak tersedia."

        else:
            return f"Tool '{tool_name}' tidak dikenali."

    except Exception as e:
        logger.exception("[TOOL ERROR] %s: %s", tool_name, e)
        return f"Error menjalankan {tool_name}: {str(e)}"
