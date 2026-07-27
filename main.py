import os
import asyncio
import logging
import threading
import http.server
import socketserver
import yt_dlp
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.environ.get("API_ID", 3335796))
API_HASH = os.environ.get("API_HASH", "138b992a0e672e8346d8439c3f42ea78")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "5088657122:AAGGal-y6fXHjtwdD74AxE-dOWzPvcdfSjU")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Client("MyBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= وب‌سرور =================
def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
        logger.info(f"🌐 وب‌سرور روی پورت {port} فعال شد")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ================= دانلود و تبدیل به MP3 =================
def download_mp3(query):
    try:
        opts = {
            'format': 'bestaudio',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 10,
            'retries': 3,
            'concurrent_fragment_downloads': 10,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            if not info or not info.get('entries'):
                return None, "آهنگی پیدا نشد"
            entry = info['entries'][0]
            video_id = entry['id']
            title = entry.get('title', 'Unknown')
            artist = entry.get('uploader', 'Unknown')
            duration = entry.get('duration', 0)

            # پیدا کردن فایل MP3
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(video_id) and f.endswith('.mp3'):
                    return os.path.join(DOWNLOAD_DIR, f), {"title": title, "artist": artist, "duration": duration}
            return None, "فایل MP3 ساخته نشد"
    except Exception as e:
        logger.error(f"خطا: {e}")
        return None, str(e)

# ================= دستورات =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("اسم آهنگ رو بفرست تا MP3 بگیرم.")

@app.on_message(filters.text & ~filters.command("start"))
async def handle(_, message):
    query = message.text.strip()
    if not query:
        return
    msg = await message.reply_text(f"⏳ دانلود و تبدیل {query} ...")
    file_path, meta = await asyncio.to_thread(download_mp3, query)
    if not file_path:
        await msg.edit_text(f"❌ {meta}")
        return
    await msg.edit_text(f"📤 ارسال ...")
    await message.reply_audio(file_path, title=meta['title'], performer=meta['artist'], duration=meta['duration'])
    await msg.delete()
    os.remove(file_path)

# ================= اجرا =================
if __name__ == "__main__":
    logger.info("🚀 ربات راه‌اندازی شد.")
    app.run()
