import os
import tempfile
import shutil
import subprocess
from pathlib import Path
from telebot import TeleBot
import yt_dlp

TOKEN = "8272287740:AAFVY5tHErqaj_llBrBFLnmZskckJEsAE7U"
bot = TeleBot(TOKEN)

MAX_FILE_SIZE = 49 * 1024 * 1024
LAST_URL = None

COOKIE_FILE = "cookies.txt"

# =========================
# CLEANUP
# =========================
def cleanup(temp_dir):
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

# =========================
# SAFE DOWNLOAD
# =========================
def safe_download(url, temp_dir, ydl_opts):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        print("[PRIMARY FAILED]", e)
        return None

# =========================
# VIDEO DOWNLOAD (FIXED)
# =========================
def download_file(url):
    temp_dir = tempfile.mkdtemp()

    base_opts = {
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "quiet": False,
        "noplaylist": True,
        "retries": 5,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    # 🔥 FIRST TRY (best quality)
    opts1 = {
        **base_opts,
        "format": "bestvideo[height<=720]+bestaudio/best",
        "merge_output_format": "mp4",
        "cookiefile": COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
    }

    file_path = safe_download(url, temp_dir, opts1)

    # 🔥 FALLBACK (NO FFMPEG NEEDED)
    if not file_path:
        print("[FALLBACK MODE]")
        opts2 = {
            **base_opts,
            "format": "best[height<=720]",
            "cookiefile": COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
        }
        file_path = safe_download(url, temp_dir, opts2)

    if file_path:
        return file_path, temp_dir

    cleanup(temp_dir)
    return None, None

# =========================
# SPOTIFY → YOUTUBE MP3
# =========================
def download_spotify(url):
    temp_dir = tempfile.mkdtemp()

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or ""
        artist = info.get("artist") or ""
        query = f"{artist} {title}".strip()

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "default_search": "ytsearch1:",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            file_path = ydl.prepare_filename(info)

        return file_path, temp_dir

    except Exception as e:
        print("[SPOTIFY ERROR]", e)
        cleanup(temp_dir)
        return None, None

# =========================
# SEND
# =========================
def send_media(chat_id, file_path):
    path = Path(file_path)

    if not path.exists():
        bot.send_message(chat_id, "❌ File missing.")
        return

    size_mb = path.stat().st_size // (1024 * 1024)

    with open(path, "rb") as f:
        if path.suffix.lower() in [".mp3", ".m4a"]:
            bot.send_audio(chat_id, f, caption=f"✅ {size_mb}MB")
        else:
            bot.send_video(chat_id, f, caption=f"✅ {size_mb}MB", supports_streaming=True)

# =========================
# HANDLER
# =========================
@bot.message_handler(func=lambda m: m.text)
def handle(message):
    global LAST_URL

    url = message.text.strip()

    if not url.startswith("http"):
        return

    if url == LAST_URL:
        return

    LAST_URL = url

    msg = bot.send_message(message.chat.id, "⏳ Downloading...")
    temp_dir = None

    try:
        if "spotify.com" in url:
            file_path, temp_dir = download_spotify(url)
        else:
            file_path, temp_dir = download_file(url)

        bot.delete_message(message.chat.id, msg.message_id)

        if file_path:
            send_media(message.chat.id, file_path)
        else:
            bot.send_message(message.chat.id, "❌ Failed. Private or blocked link.")

    except Exception as e:
        print("[ERROR]", e)
        bot.send_message(message.chat.id, "⚠️ Error.")

    finally:
        cleanup(temp_dir)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    print("🚀 Running...")
    bot.infinity_polling(skip_pending=True)
