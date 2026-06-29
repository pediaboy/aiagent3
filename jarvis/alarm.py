"""
alarm.py — Alarm, reminder, timer via termux-api
"""
import subprocess
import re
import time
import logging
from datetime import datetime, timedelta
from jarvis.android import _run, send_notification

logger = logging.getLogger(__name__)


def _parse_time(time_str: str):
    """
    Parse waktu dari string.
    Contoh: '05:00', '05.00', '5 pagi', '3 sore', '14:30'
    """
    now = datetime.now()
    time_str = time_str.strip().lower()

    m = re.match(r"(\d{1,2})[:\.](\d{2})", time_str)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        dt = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if dt < now:
            dt += timedelta(days=1)
        return dt

    m2 = re.match(r"(\d{1,2})\s*(pagi|siang|sore|malam)?", time_str)
    if m2:
        h = int(m2.group(1))
        period = m2.group(2) or ""
        if period in ("sore", "malam") and h < 12:
            h += 12
        dt = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if dt < now:
            dt += timedelta(days=1)
        return dt

    return None


def _parse_duration(dur_str: str) -> int:
    """Parse durasi ke detik. Contoh: '5 menit', '1 jam 30 menit'"""
    dur_str = dur_str.lower()
    total = 0
    patterns = [
        (r"(\d+)\s*(jam|hour|hr|h)", 3600),
        (r"(\d+)\s*(menit|minute|min|m)", 60),
        (r"(\d+)\s*(detik|second|sec|s)", 1),
    ]
    for pattern, mult in patterns:
        m = re.search(pattern, dur_str)
        if m:
            total += int(m.group(1)) * mult
    return total


def set_alarm(time_str: str, label: str = "Alarm") -> str:
    """Set alarm pada waktu tertentu."""
    dt = _parse_time(time_str)
    if not dt:
        return "Format waktu tidak dikenali: '{}'. Gunakan HH:MM atau '5 pagi'.".format(time_str)

    seconds_until = int((dt - datetime.now()).total_seconds())
    if seconds_until < 0:
        return "Waktu alarm sudah lewat."

    time_display = dt.strftime("%H:%M")
    date_display = dt.strftime("%d %b %Y")

    safe_label = label.replace("'", "").replace('"', "")
    cmd = (
        "( sleep " + str(seconds_until) + " && "
        "termux-notification -t '\u23f0 " + safe_label + "' "
        "-c 'Alarm: " + time_display + "' "
        "--sound --vibrate 500,500,500 ) &"
    )
    subprocess.Popen(cmd, shell=True)

    return (
        "\u23f0 Alarm diset!\n"
        "Waktu: " + time_display + " (" + date_display + ")\n"
        "Label: " + label + "\n"
        "Dalam: " + str(seconds_until // 60) + " menit " + str(seconds_until % 60) + " detik"
    )


def set_reminder(time_str: str, message: str) -> str:
    """Set reminder dengan pesan kustom."""
    dt = _parse_time(time_str)
    if not dt:
        return "Format waktu tidak dikenali: '{}'.".format(time_str)

    seconds_until = int((dt - datetime.now()).total_seconds())
    if seconds_until < 0:
        return "Waktu reminder sudah lewat."

    time_display = dt.strftime("%H:%M")
    safe_msg = message.replace("'", "").replace('"', '')[:100]

    cmd = (
        "( sleep " + str(seconds_until) + " && "
        "termux-notification -t '\U0001f4cc Reminder' "
        "-c '" + safe_msg + "' "
        "--sound --vibrate 300,300 ) &"
    )
    subprocess.Popen(cmd, shell=True)

    return (
        "\U0001f4cc Reminder diset!\n"
        "Waktu: " + time_display + "\n"
        "Pesan: " + message + "\n"
        "Dalam: " + str(seconds_until // 60) + " menit"
    )


def set_timer(duration_str: str, label: str = "Timer") -> str:
    """Set countdown timer."""
    seconds = _parse_duration(duration_str)
    if seconds <= 0:
        return "Durasi tidak valid: '{}'. Contoh: '5 menit', '1 jam 30 menit'.".format(duration_str)

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    display_parts = []
    if h:
        display_parts.append(str(h) + " jam")
    if m:
        display_parts.append(str(m) + " menit")
    if s:
        display_parts.append(str(s) + " detik")
    display = " ".join(display_parts)

    safe_label = label.replace("'", "").replace('"', "")
    cmd = (
        "( sleep " + str(seconds) + " && "
        "termux-notification -t '\u23f1\ufe0f " + safe_label + " Selesai!' "
        "-c 'Timer " + display + " telah habis.' "
        "--sound --vibrate 500,500,500,500 ) &"
    )
    subprocess.Popen(cmd, shell=True)

    return (
        "\u23f1\ufe0f Timer dimulai!\n"
        "Durasi: " + display + "\n"
        "Label: " + label + "\n"
        "Notifikasi akan muncul saat selesai."
    )


def get_current_time() -> str:
    now = datetime.now()
    return (
        "\U0001f550 Waktu sekarang:\n"
        + now.strftime("%H:%M:%S") + "\n"
        + now.strftime("%A, %d %B %Y")
    )
