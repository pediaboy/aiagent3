"""
music.py — Music playback via termux-api + YouTube audio via yt-dlp
Playback audio langsung dari Termux menggunakan termux-media-player atau mpv.
"""
import subprocess
import os
import re
import logging
import urllib.parse
import requests
from pathlib import Path
from jarvis.android import _run

logger = logging.getLogger(__name__)

MUSIC_DIR = Path("/sdcard/Music/pedia-agent")
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

_current_process = None  # Track proses mpv yang sedang jalan


def _ytdlp_available() -> bool:
    rc, out, err = _run(["which", "yt-dlp"])
    return rc == 0 and bool(out)


def _mpv_available() -> bool:
    rc, out, err = _run(["which", "mpv"])
    return rc == 0 and bool(out)


def _get_youtube_audio_url(query: str) -> tuple[str, str]:
    """
    Cari video YouTube dan return (stream_url, title).
    Pakai yt-dlp jika tersedia, fallback ke Invidious API.
    """
    if _ytdlp_available():
        # yt-dlp search + get audio url
        cmd = [
            "yt-dlp",
            f"ytsearch1:{query}",
            "--get-url",
            "--get-title",
            "-f", "bestaudio/best",
            "--no-playlist",
            "--quiet"
        ]
        rc, out, err = _run(cmd, timeout=30)
        if rc == 0 and out:
            lines = out.strip().split("\n")
            if len(lines) >= 2:
                title = lines[0]
                url   = lines[-1]
                return url, title
    
    # Fallback: Invidious API (public, no key)
    try:
        q = urllib.parse.quote_plus(query)
        api_url = f"https://invidious.tiekoetter.com/api/v1/search?q={q}&type=video&fields=videoId,title"
        r = requests.get(api_url, timeout=10)
        data = r.json()
        if data and isinstance(data, list) and len(data) > 0:
            vid_id = data[0].get("videoId", "")
            title  = data[0].get("title", query)
            if vid_id:
                yt_url = f"https://www.youtube.com/watch?v={vid_id}"
                return yt_url, title
    except Exception as e:
        logger.error("Invidious search: %s", e)
    
    return "", query


def play_youtube(query: str) -> str:
    """
    Putar audio dari YouTube langsung.
    Fallback ke buka URL di browser jika mpv tidak tersedia.
    """
    global _current_process
    
    if not query.strip():
        return "Masukkan judul lagu yang ingin diputar."
    
    # Hentikan yang sedang putar
    stop_music()
    
    # Cari URL
    audio_url, title = _get_youtube_audio_url(query)
    
    if not audio_url:
        # Fallback: buka di YouTube browser
        from jarvis.android import open_youtube_search
        open_youtube_search(query)
        return f"🎵 Membuka YouTube untuk: {query}"
    
    # Coba putar dengan mpv
    if _mpv_available() and audio_url.startswith("http"):
        try:
            cmd = [
                "mpv",
                "--no-video",
                "--terminal=no",
                "--quiet",
                audio_url
            ]
            _current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return f"🎵 Memutar: {title}\nSumber: YouTube"
        except Exception as e:
            logger.error("mpv error: %s", e)
    
    # Fallback: termux-media-player jika ada file lokal
    if _ytdlp_available():
        return download_and_play(query)
    
    # Last resort: buka di browser
    from jarvis.android import open_url
    yt_search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
    open_url(yt_search_url)
    return f"🎵 Membuka YouTube: {title}"


def download_and_play(query: str) -> str:
    """Download audio ke lokal lalu putar."""
    global _current_process
    
    if not _ytdlp_available():
        return "yt-dlp tidak tersedia. Install: pip install yt-dlp"
    
    output_template = str(MUSIC_DIR / "%(title)s.%(ext)s")
    cmd = [
        "yt-dlp",
        f"ytsearch1:{query}",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "128K",
        "-o", output_template,
        "--no-playlist",
        "--quiet",
        "--print", "filename"
    ]
    
    rc, out, err = _run(cmd, timeout=120)
    if rc != 0 or not out:
        return f"Gagal download: {err or 'unknown error'}"
    
    filepath = out.strip().split("\n")[-1]
    if not os.path.exists(filepath):
        # Coba cari file yang baru didownload
        files = sorted(MUSIC_DIR.glob("*.mp3"), key=os.path.getmtime, reverse=True)
        if not files:
            return "File tidak ditemukan setelah download."
        filepath = str(files[0])
    
    return play_file(filepath)


def play_file(filepath: str) -> str:
    """Putar file audio lokal."""
    global _current_process
    
    if not os.path.exists(filepath):
        return f"File tidak ditemukan: {filepath}"
    
    stop_music()
    
    # Coba mpv dulu
    if _mpv_available():
        try:
            _current_process = subprocess.Popen(
                ["mpv", "--no-video", "--terminal=no", "--quiet", filepath],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            name = Path(filepath).stem
            return f"🎵 Memutar: {name}"
        except Exception as e:
            pass
    
    # Fallback: termux-media-player
    try:
        _current_process = subprocess.Popen(
            ["termux-media-player", "play", filepath],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        name = Path(filepath).stem
        return f"🎵 Memutar: {name}"
    except Exception as e:
        return f"Gagal putar: {e}"


def stop_music() -> str:
    """Hentikan musik yang sedang diputar."""
    global _current_process
    if _current_process and _current_process.poll() is None:
        _current_process.terminate()
        _current_process = None
        return "⏹️ Musik dihentikan."
    # Juga kill semua mpv yang mungkin berjalan
    _run(["pkill", "-f", "mpv"])
    _run(["termux-media-player", "stop"])
    return "⏹️ Musik dihentikan."


def pause_music() -> str:
    _run(["termux-media-player", "pause"])
    return "⏸️ Musik dijeda."


def resume_music() -> str:
    _run(["termux-media-player", "play"])
    return "▶️ Musik dilanjutkan."


def list_downloaded() -> str:
    """Daftar lagu yang sudah didownload."""
    files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.m4a"))
    if not files:
        return f"Belum ada lagu di {MUSIC_DIR}"
    files.sort(key=os.path.getmtime, reverse=True)
    lines = [f"{i+1}. {f.stem}" for i, f in enumerate(files[:15])]
    return "🎵 Lagu tersimpan:\n" + "\n".join(lines)
