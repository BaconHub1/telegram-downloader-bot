import os
import tempfile
import shutil
import subprocess
from pathlib import Path
from telebot import TeleBot
import yt_dlp

# =========================
# CONFIG
# =========================
TOKEN = "8272287740:AAGZvU8KGZJlLNpBNzfzKHLu1nGthOkyQLY"  # your token
bot = TeleBot(TOKEN)

MAX_FILE_SIZE = 49 * 1024 * 1024
SEND_TIMEOUT = 300
LAST_URL = None

# =========================
# LOGGER
# =========================
class MyLogger:
    def debug(self, msg): pass
    def warning(self, msg): print(f"[yt_dlp WARNING] {msg}")
    def error(self, msg): print(f"[yt_dlp ERROR] {msg}")

# =========================
# CLEANUP
# =========================
def cleanup(temp_dir):
    if temp_dir:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

# =========================
# CHECK FFMPEG
# =========================
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except:
        print("[ERROR] ffmpeg not found! Install it.")
        return False

# =========================
# AUDIO → MP3
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
        print(f"[MP3 ERROR] {e}")
        return audio_path

# =========================
# SPOTIFY → YOUTUBE SEARCH
# =========================
def download_spotify(url: str):
    temp_dir = tempfile.mkdtemp()
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "extract_flat": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or ""
        artist = info.get("artist") or info.get("uploader") or ""
        search_query = f"{artist} - {title}".strip(" -") or title or "popular song 2026"

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "default_search": "ytsearch1:",
            "quiet": False
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            file_path = ydl.prepare_filename(info)

        mp3 = convert_to_mp3(Path(file_path))
        return str(mp3), temp_dir

    except Exception as e:
        print(f"[SPOTIFY ERROR] {e}")
        cleanup(temp_dir)
        return None, None

# =========================
# VIDEO DOWNLOAD (YT / TikTok / Instagram)
# =========================
def download_file(url: str):
    temp_dir = tempfile.mkdtemp()
    cookie_file = "cookies.txt"  # must exist in same folder

    ydl_opts = {
        "format": "bestvideo[height<=720]+bestaudio/best/best",
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": False,
        "logger": MyLogger(),
        "retries": 5,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
        "cookiefile": cookie_file if os.path.exists(cookie_file) else None
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        return file_path, temp_dir

    except Exception as e:
        print(f"[DOWNLOAD ERROR] {e}")
        cleanup(temp_dir)
        return None, None

# =========================
# SEND MEDIA
# =========================
def send_media(chat_id, file_path):
    try:
        path = Path(file_path)
        if not path.exists():
            bot.send_message(chat_id, "❌ File missing.")
            return

        size_mb = path.stat().st_size // (1024*1024)

        with open(path, "rb") as f:
            if path.suffix.lower() == ".mp3":
                bot.send_audio(chat_id, f, caption=f"✅ Done ({size_mb} MB)", timeout=SEND_TIMEOUT)
            else:
                bot.send_video(chat_id, f, caption=f"✅ Done ({size_mb} MB)", supports_streaming=True, timeout=SEND_TIMEOUT)

    except Exception as e:
        print(f"[SEND ERROR] {e}")
        bot.send_message(chat_id, "⚠️ Failed to send file.")

# =========================
# HANDLERS
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🚀 Bot Online!\n\n"
        "Send a link:\n"
        "• YouTube / TikTok / IG → Video\n"
        "• Spotify → MP3"
    )

@bot.message_handler(func=lambda m: m.text)
def handle(message):
    global LAST_URL
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        return
    if url == LAST_URL:
        return
    LAST_URL = url

    status = bot.send_message(message.chat.id, "⏳ Downloading...")
    temp_dir = None

    try:
        if "spotify.com" in url.lower():
            file_path, temp_dir = download_spotify(url)
        else:
            file_path, temp_dir = download_file(url)

        bot.delete_message(message.chat.id, status.message_id)

        if file_path:
            send_media(message.chat.id, file_path)
        else:
            bot.send_message(message.chat.id, "❌ Download failed. Check link or cookies.")

    except Exception as e:
        print(f"[HANDLER ERROR] {e}")
        bot.send_message(message.chat.id, "⚠️ Error occurred.")

    finally:
        cleanup(temp_dir)

# =========================
# RUN BOT
# =========================
if __name__ == "__main__":
    if not check_ffmpeg():
        print("[ERROR] Install ffmpeg first!")
    else:
        print("🚀 Bot running...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
