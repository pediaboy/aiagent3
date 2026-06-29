"""
browser.py — Web browsing, scraping, search via requests
Tidak pakai selenium/playwright — pure requests + BeautifulSoup (ringan, 32-bit friendly)
"""
import re
import json
import logging
import requests
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 11; Realme C30) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
})
TIMEOUT = 15


def _get(url: str, **kwargs) -> Optional[requests.Response]:
    try:
        r = SESSION.get(url, timeout=TIMEOUT, **kwargs)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        logger.error("GET %s => %s", url, e)
        return None


def google_search(query: str, num: int = 5) -> str:
    """
    Cari di Google via DuckDuckGo HTML (tidak butuh API key).
    """
    q = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    r = _get(url)
    if not r:
        return f"Gagal search: {query}"
    
    # Parse hasil dengan regex (tanpa BeautifulSoup agar lebih ringan)
    # DDG HTML: <a class="result__a" href="...">Title</a>
    links = re.findall(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        r.text, re.DOTALL
    )
    snippets = re.findall(
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        r.text, re.DOTALL
    )
    
    if not links:
        return f"Tidak ada hasil untuk: {query}"
    
    results = []
    for i, (href, title) in enumerate(links[:num]):
        # Bersihkan HTML tags
        title_clean   = re.sub(r"<[^>]+>", "", title).strip()
        snippet_clean = re.sub(r"<[^>]+>", "", snippets[i] if i < len(snippets) else "").strip()
        
        # Decode URL dari DDG redirect
        url_match = re.search(r"uddg=([^&]+)", href)
        clean_url = urllib.parse.unquote(url_match.group(1)) if url_match else href
        
        results.append(f"{i+1}. {title_clean}\n   {snippet_clean}\n   🔗 {clean_url}")
    
    return f"🔍 Hasil pencarian '{query}':\n\n" + "\n\n".join(results)


def fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """Ambil teks dari halaman web."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    r = _get(url)
    if not r:
        return f"Gagal ambil halaman: {url}"
    
    # Strip HTML tags
    text = re.sub(r"<style[^>]*>.*?</style>", " ", r.text, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... (terpotong, total {len(text)} karakter)"
    
    return f"📄 Konten dari {url}:\n\n{text}"


def get_weather(city: str = "Jakarta") -> str:
    """Ambil cuaca dari wttr.in (gratis, no API key)."""
    city_enc = urllib.parse.quote(city)
    url = f"https://wttr.in/{city_enc}?format=j1"
    r = _get(url)
    if not r:
        return f"Gagal ambil cuaca untuk {city}."
    
    try:
        data = r.json()
        current = data["current_condition"][0]
        area    = data["nearest_area"][0]
        
        temp_c  = current.get("temp_C", "?")
        feels   = current.get("FeelsLikeC", "?")
        humidity= current.get("humidity", "?")
        desc    = current.get("weatherDesc", [{}])[0].get("value", "?")
        wind    = current.get("windspeedKmph", "?")
        
        location = area.get("areaName", [{}])[0].get("value", city)
        country  = area.get("country", [{}])[0].get("value", "")
        
        return (
            f"🌤️ Cuaca {location}, {country}:\n"
            f"Kondisi  : {desc}\n"
            f"Suhu     : {temp_c}°C (terasa {feels}°C)\n"
            f"Kelembaban: {humidity}%\n"
            f"Angin    : {wind} km/h"
        )
    except Exception as e:
        return f"Gagal parse cuaca: {e}"


def get_exchange_rate(from_curr: str = "USD", to_curr: str = "IDR") -> str:
    """Kurs mata uang via ExchangeRate-API (free tier)."""
    url = f"https://api.exchangerate-api.com/v4/latest/{from_curr.upper()}"
    r = _get(url)
    if not r:
        return f"Gagal ambil kurs {from_curr}/{to_curr}."
    try:
        data = r.json()
        rates = data.get("rates", {})
        rate  = rates.get(to_curr.upper())
        if rate is None:
            return f"Kurs {to_curr} tidak tersedia."
        return f"💱 1 {from_curr.upper()} = {rate:,.2f} {to_curr.upper()}"
    except Exception as e:
        return f"Error parse kurs: {e}"


def youtube_search_url(query: str) -> str:
    """Return YouTube search URL."""
    q = urllib.parse.quote_plus(query)
    return f"https://www.youtube.com/results?search_query={q}"


def translate_text(text: str, target_lang: str = "id") -> str:
    """Terjemahkan teks via MyMemory (gratis, no key)."""
    url = "https://api.mymemory.translated.net/get"
    params = {"q": text[:500], "langpair": f"auto|{target_lang}"}
    try:
        r = SESSION.get(url, params=params, timeout=10)
        data = r.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated:
            return f"🌐 Terjemahan:\n{translated}"
        return "Gagal menerjemahkan."
    except Exception as e:
        return f"Error terjemahan: {e}"
