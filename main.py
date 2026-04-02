import os
import tempfile
import shutil
import subprocess
import time
from pathlib import Path
from telebot import TeleBot, apihelper
import yt_dlp

# =========================
# CONFIG
# =========================
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

            # 🔥 Better file detection
            if "requested_downloads" in info:
                return info["requested_downloads"][0]["filepath"]

            return ydl.prepare_filename(info)

    except Exception as e:
        print("[DOWNLOAD FAILED]", e)
        return None

# =========================
# VIDEO DOWNLOAD (IG FIXED)
# =========================
def download_file(url):
    temp_dir = tempfile.mkdtemp()

    base_opts = {
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "quiet": False,
        "noplaylist": True,
        "retries": 5,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
        "cookiefile": COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
    }

    # 🔥 TRY BEST (needs ffmpeg)
    opts1 = {
        **base_opts,
        "format": "bestvideo[height<=720]+bestaudio/best",
        "merge_output_format": "mp4",
    }

    file_path = safe_download(url, temp_dir, opts1)

    # 🔥 FALLBACK (NO FFMPEG — VERY IMPORTANT)
    if not file_path:
        print("[FALLBACK MODE]")
        opts2 = {
            **base_opts,
            "format": "best[ext=mp4]/best",
        }
        file_path = safe_download(url, temp_dir, opts2)

    if file_path:
        return file_path, temp_dir

    cleanup(temp_dir)
    return None, None

# =========================
# SPOTIFY → MP3
# =========================
def convert_to_mp3(audio_path: Path) -> Path:
    try:
        mp3_path = audio_path.with_suffix(".mp3")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-codec:a", "libmp3lame",
            "-q:a", "2",
            str(mp3_path)
        ], check=True, timeout=60)
        return mp3_path
    except Exception as e:
        print("[MP3 ERROR]", e)
        return audio_path

def download_spotify(url):
    temp_dir = tempfile.mkdtemp()
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or ""
        artist = info.get("artist") or ""
        query = f"{artist} {title}".strip()

        if not query:
            query = "popular song"

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "default_search": "ytsearch1:",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            file_path = ydl.prepare_filename(info)

        mp3 = convert_to_mp3(Path(file_path))
        return str(mp3), temp_dir

    except Exception as e:
        print("[SPOTIFY ERROR]", e)
        cleanup(temp_dir)
        return None, None

# =========================
# SEND MEDIA
# =========================
def send_media(chat_id, file_path):
    path = Path(file_path)

    if not path.exists():
        bot.send_message(chat_id, "❌ File missing.")
        return

    size_mb = path.stat().st_size // (1024 * 1024)

    if size_mb > 49:
        bot.send_message(chat_id, "❌ File too large (49MB limit).")
        return

    with open(path, "rb") as f:
        if path.suffix.lower() in [".mp3", ".m4a"]:
            bot.send_audio(chat_id, f, caption=f"✅ {size_mb}MB")
        else:
            bot.send_video(chat_id, f, caption=f"✅ {size_mb}MB", supports_streaming=True)

# =========================
# HANDLER
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🚀 Bot Ready!\n\n"
        "Send a link:\n"
        "• Instagram (public/private)\n"
        "• TikTok\n"
        "• YouTube\n"
        "• Spotify → MP3"
    )

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
        if "spotify.com" in url.lower():
            file_path, temp_dir = download_spotify(url)
        else:
            file_path, temp_dir = download_file(url)

        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass

        if file_path:
            send_media(message.chat.id, file_path)
        else:
            bot.send_message(message.chat.id, "❌ Failed. Private, expired, or blocked link.")

    except Exception as e:
        print("[HANDLER ERROR]", e)
        bot.send_message(message.chat.id, "⚠️ Error occurred.")

    finally:
        cleanup(temp_dir)

# =========================
# RUN (409 FIX LOOP)
# =========================
def run_bot():
    while True:
        try:
            print("🚀 Running...")
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)

        except apihelper.ApiTelegramException as e:
            if "409" in str(e):
                print("⚠️ 409 conflict - retrying...")
                time.sleep(5)
            else:
                print("[TELEGRAM ERROR]", e)
                time.sleep(5)

        except Exception as e:
            print("[CRASH]", e)
            time.sleep(5)

if __name__ == "__main__":
    run_bot()
