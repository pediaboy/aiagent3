"""
android.py — Android device control via Termux API
Semua fungsi real, menggunakan subprocess + termux-api commands.
"""
import subprocess
import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


def _run(cmd: list, timeout: int = 10) -> tuple[int, str, str]:
    """Run command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except FileNotFoundError as e:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def _run_json(cmd: list, timeout: int = 10):
    rc, out, err = _run(cmd, timeout)
    if rc != 0 or not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


# ─── App Launcher ─────────────────────────────────────────────────────────────

APP_PACKAGES = {
    "youtube":    "com.google.android.youtube",
    "whatsapp":   "com.whatsapp",
    "telegram":   "org.telegram.messenger",
    "chrome":     "com.android.chrome",
    "instagram":  "com.instagram.android",
    "tiktok":     "com.zhiliaoapp.musically",
    "maps":       "com.google.android.apps.maps",
    "gojek":      "com.gojek.app",
    "grab":       "com.grabtaxi.passenger",
    "tokopedia":  "com.tokopedia.tkpd",
    "shopee":     "com.shopee.id",
    "twitter":    "com.twitter.android",
    "x":          "com.twitter.android",
    "spotify":    "com.spotify.music",
    "camera":     "android.media.action.STILL_IMAGE_CAMERA",
    "settings":   "com.android.settings",
    "calculator": "com.android.calculator2",
    "gmail":      "com.google.android.gm",
    "clock":      "com.android.deskclock",
    "playstore":  "com.android.vending",
    "facebook":   "com.facebook.katana",
    "line":       "jp.naver.line.android",
    "zoom":       "us.zoom.videomeetings",
}


def open_app(app_name: str) -> str:
    """Buka aplikasi berdasarkan nama."""
    name_lower = app_name.lower().strip()
    
    # Cari di map
    package = None
    for key, pkg in APP_PACKAGES.items():
        if key in name_lower or name_lower in key:
            package = pkg
            break
    
    if not package:
        return f"Aplikasi '{app_name}' tidak dikenal. Coba: youtube, whatsapp, telegram, chrome, instagram, dll."
    
    # Gunakan am start untuk buka app
    cmd = ["am", "start", "-n", f"{package}/.MainActivity"]
    rc, out, err = _run(cmd)
    if rc != 0:
        # Coba cara alternatif via monkey
        rc2, out2, err2 = _run(["monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])
        if rc2 != 0:
            return f"Gagal buka {app_name}. Pastikan aplikasi terinstall."
    
    return f"✅ Membuka {app_name}..."


def open_url(url: str) -> str:
    """Buka URL di browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    rc, out, err = _run(["termux-open-url", url])
    if rc != 0:
        return f"Gagal buka URL: {err}"
    return f"✅ Membuka: {url}"


def open_youtube_search(query: str) -> str:
    """Cari di YouTube."""
    import urllib.parse
    q = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={q}"
    return open_url(url)


def open_whatsapp_chat(phone: str = None) -> str:
    """Buka WhatsApp, opsional langsung ke nomor."""
    if phone:
        phone = re.sub(r"[^0-9]", "", phone)
        if phone.startswith("0"):
            phone = "62" + phone[1:]
        url = f"https://wa.me/{phone}"
        return open_url(url)
    return open_app("whatsapp")


# ─── Device Info ──────────────────────────────────────────────────────────────

def get_battery() -> str:
    """Cek status baterai."""
    data = _run_json(["termux-battery-status"])
    if not data:
        # Fallback: baca dari sysfs
        try:
            cap = open("/sys/class/power_supply/battery/capacity").read().strip()
            status = open("/sys/class/power_supply/battery/status").read().strip()
            return f"🔋 Baterai: {cap}% ({status})"
        except:
            return "Tidak bisa baca status baterai."
    
    pct    = data.get("percentage", "?")
    status = data.get("status", "?")
    health = data.get("health", "?")
    temp   = data.get("temperature", 0)
    plug   = data.get("plugged", "UNPLUGGED")
    
    icon = "🔋" if pct > 20 else "🪫"
    charge_icon = "⚡" if plug != "UNPLUGGED" else ""
    
    return (
        f"{icon} Baterai: {pct}% {charge_icon}\n"
        f"Status: {status}\n"
        f"Kesehatan: {health}\n"
        f"Suhu: {temp:.1f}°C\n"
        f"Charger: {plug}"
    )


def get_device_info() -> str:
    """Info perangkat Android."""
    info = {}
    
    # Brand & Model
    rc, brand, _ = _run(["getprop", "ro.product.brand"])
    rc, model, _ = _run(["getprop", "ro.product.model"])
    rc, android, _ = _run(["getprop", "ro.build.version.release"])
    rc, sdk, _ = _run(["getprop", "ro.build.version.sdk"])
    rc, cpu, _ = _run(["getprop", "ro.product.cpu.abi"])
    
    return (
        f"📱 Info Perangkat:\n"
        f"Brand: {brand or '?'}\n"
        f"Model: {model or '?'}\n"
        f"Android: {android or '?'} (SDK {sdk or '?'})\n"
        f"CPU: {cpu or '?'}\n"
    )


def get_ram_info() -> str:
    """Info RAM dari /proc/meminfo."""
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    val = int(parts[1])  # kB
                    meminfo[key] = val
        
        total  = meminfo.get("MemTotal", 0)
        avail  = meminfo.get("MemAvailable", 0)
        used   = total - avail
        pct    = (used / total * 100) if total else 0
        
        def mb(kb): return f"{kb // 1024} MB"
        
        return (
            f"🧠 RAM:\n"
            f"Total : {mb(total)}\n"
            f"Dipakai : {mb(used)} ({pct:.1f}%)\n"
            f"Tersisa : {mb(avail)}"
        )
    except Exception as e:
        return f"Gagal baca RAM: {e}"


def get_storage_info() -> str:
    """Info storage via df."""
    rc, out, err = _run(["df", "-h", "/storage/emulated/0"])
    if rc != 0 or not out:
        rc, out, err = _run(["df", "-h", "/data"])
    if rc != 0:
        return "Tidak bisa baca info storage."
    lines = out.strip().split("\n")
    if len(lines) < 2:
        return out
    header = lines[0]
    data   = lines[1]
    parts  = data.split()
    if len(parts) >= 5:
        return (
            f"💾 Storage:\n"
            f"Total : {parts[1]}\n"
            f"Dipakai : {parts[2]} ({parts[4]})\n"
            f"Tersisa : {parts[3]}"
        )
    return f"💾 Storage:\n{out}"


def get_cpu_info() -> str:
    """Info CPU dari /proc/cpuinfo + /proc/stat."""
    try:
        # Baca CPU model
        model = "?"
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "Hardware" in line or "model name" in line or "Processor" in line:
                    model = line.split(":", 1)[-1].strip()
                    break
        
        # Core count
        rc, cores_out, _ = _run(["nproc"])
        cores = cores_out.strip() if cores_out else "?"
        
        # CPU freq (jika tersedia)
        freq = "?"
        try:
            freq_raw = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read().strip()
            freq = f"{int(freq_raw)//1000} MHz"
        except:
            pass
        
        return (
            f"⚙️ CPU:\n"
            f"Model: {model}\n"
            f"Cores: {cores}\n"
            f"Freq: {freq}"
        )
    except Exception as e:
        return f"Gagal baca CPU: {e}"


def get_system_status() -> str:
    """Gabungan: baterai + RAM + storage."""
    batt    = get_battery()
    ram     = get_ram_info()
    storage = get_storage_info()
    return f"{batt}\n\n{ram}\n\n{storage}"


# ─── Screenshot ───────────────────────────────────────────────────────────────

def take_screenshot() -> str:
    """Ambil screenshot via termux-screenshot."""
    path = f"/sdcard/screenshot_{int(time.time())}.png"
    rc, out, err = _run(["termux-screenshot", "-p", path], timeout=15)
    if rc != 0:
        return f"Gagal screenshot: {err}"
    return f"✅ Screenshot disimpan: {path}"


def get_screenshot_path() -> Optional[str]:
    """Ambil screenshot dan return path file."""
    path = f"/sdcard/screenshot_{int(time.time())}.png"
    rc, out, err = _run(["termux-screenshot", "-p", path], timeout=15)
    if rc != 0:
        return None
    return path


# ─── Camera ───────────────────────────────────────────────────────────────────

def open_camera() -> str:
    rc, out, err = _run(["termux-camera-photo", f"/sdcard/photo_{int(time.time())}.jpg"], timeout=20)
    if rc != 0:
        return f"Gagal buka kamera: {err}"
    return "✅ Kamera dibuka, foto disimpan di /sdcard/"


# ─── Flashlight ───────────────────────────────────────────────────────────────

def flashlight_on() -> str:
    rc, out, err = _run(["termux-torch", "on"])
    return "🔦 Flashlight ON" if rc == 0 else f"Gagal: {err}"

def flashlight_off() -> str:
    rc, out, err = _run(["termux-torch", "off"])
    return "🔦 Flashlight OFF" if rc == 0 else f"Gagal: {err}"


# ─── Clipboard ────────────────────────────────────────────────────────────────

def get_clipboard() -> str:
    rc, out, err = _run(["termux-clipboard-get"])
    if rc != 0:
        return f"Gagal baca clipboard: {err}"
    return f"📋 Clipboard:\n{out}" if out else "📋 Clipboard kosong."

def set_clipboard(text: str) -> str:
    try:
        p = subprocess.Popen(["termux-clipboard-set"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode())
        return f"✅ Clipboard diset: {text[:50]}..."
    except Exception as e:
        return f"Gagal set clipboard: {e}"


# ─── Volume ───────────────────────────────────────────────────────────────────

def get_volume() -> str:
    data = _run_json(["termux-volume"])
    if not data:
        return "Tidak bisa baca volume."
    lines = []
    for item in (data if isinstance(data, list) else [data]):
        stream = item.get("stream", "?")
        vol    = item.get("volume", "?")
        maxv   = item.get("max_volume", "?")
        lines.append(f"{stream}: {vol}/{maxv}")
    return "🔊 Volume:\n" + "\n".join(lines)

def set_volume(stream: str, level: int) -> str:
    rc, out, err = _run(["termux-volume", stream.lower(), str(level)])
    if rc != 0:
        return f"Gagal set volume: {err}"
    return f"🔊 Volume {stream} diset ke {level}"


# ─── Brightness ───────────────────────────────────────────────────────────────

def set_brightness(level: int) -> str:
    """Level: 0-255."""
    level = max(0, min(255, level))
    rc, out, err = _run(["termux-brightness", str(level)])
    if rc != 0:
        return f"Gagal set brightness: {err}"
    return f"☀️ Brightness diset ke {level}"


# ─── WiFi ─────────────────────────────────────────────────────────────────────

def get_wifi_info() -> str:
    data = _run_json(["termux-wifi-connectioninfo"])
    if not data:
        return "Tidak bisa baca info WiFi."
    ssid  = data.get("ssid", "?")
    ip    = data.get("ip", "?")
    rssi  = data.get("rssi", "?")
    speed = data.get("link_speed_mbps", "?")
    return (
        f"📶 WiFi:\n"
        f"SSID : {ssid}\n"
        f"IP   : {ip}\n"
        f"RSSI : {rssi} dBm\n"
        f"Speed: {speed} Mbps"
    )

def scan_wifi() -> str:
    data = _run_json(["termux-wifi-scaninfo"])
    if not data or not isinstance(data, list):
        return "Tidak bisa scan WiFi."
    nets = sorted(data, key=lambda x: x.get("rssi", -999), reverse=True)[:8]
    lines = []
    for n in nets:
        lines.append(f"  {n.get('ssid','?')} ({n.get('rssi','?')} dBm) - {n.get('security_type','?')}")
    return "📶 WiFi tersedia:\n" + "\n".join(lines)


# ─── Location ─────────────────────────────────────────────────────────────────

def get_location() -> str:
    data = _run_json(["termux-location", "-p", "network", "-r", "once"], timeout=20)
    if not data:
        return "Tidak bisa ambil lokasi (pastikan location permission aktif)."
    lat  = data.get("latitude", "?")
    lon  = data.get("longitude", "?")
    acc  = data.get("accuracy", "?")
    return (
        f"📍 Lokasi:\n"
        f"Lat: {lat}\n"
        f"Lon: {lon}\n"
        f"Akurasi: {acc}m\n"
        f"Maps: https://maps.google.com/?q={lat},{lon}"
    )


# ─── Notification ─────────────────────────────────────────────────────────────

def send_notification(title: str, content: str) -> str:
    rc, out, err = _run(["termux-notification", "-t", title, "-c", content])
    if rc != 0:
        return f"Gagal kirim notifikasi: {err}"
    return f"🔔 Notifikasi dikirim: {title}"


# ─── SMS ──────────────────────────────────────────────────────────────────────

def get_sms_inbox(limit: int = 5) -> str:
    data = _run_json(["termux-sms-list", "-l", str(limit), "-t", "inbox"])
    if not data:
        return "Tidak bisa baca SMS (pastikan SMS permission aktif)."
    if not data:
        return "Inbox kosong."
    lines = []
    for sms in data[:limit]:
        sender = sms.get("number", "?")
        body   = sms.get("body", "")[:80]
        date   = sms.get("received", "?")
        lines.append(f"Dari: {sender}\n{body}\n({date})\n")
    return "📨 SMS Inbox:\n\n" + "\n".join(lines)


# ─── Contacts ─────────────────────────────────────────────────────────────────

def search_contact(name: str) -> str:
    data = _run_json(["termux-contact-list"])
    if not data:
        return "Tidak bisa baca kontak."
    name_lower = name.lower()
    found = [c for c in data if name_lower in (c.get("name","") or "").lower()]
    if not found:
        return f"Kontak '{name}' tidak ditemukan."
    lines = []
    for c in found[:5]:
        lines.append(f"👤 {c.get('name','?')}: {c.get('number','?')}")
    return "\n".join(lines)
