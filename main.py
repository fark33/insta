import os
import asyncio
import logging
import traceback
import threading
import http.server
import socketserver
import yt_dlp
from pyrogram import Client, filters
from pyrogram.errors import RPCError

# ================= تنظیمات لاگ‌نویسی =================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= تنظیمات ربات =================
API_ID = int(os.environ.get("API_ID", "3335796"))
API_HASH = os.environ.get("API_HASH", "138b992a0e672e8346d8439c3f42ea78")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "5088657122:AAGGal-y6fXHjtwdD74AxE-dOWzPvcdfSjU")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIE_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None
if COOKIE_FILE:
    logger.info("🍪 فایل کوکی پیدا شد.")
else:
    logger.warning("⚠️ کوکی پیدا نشد — ممکن است محدودیت ایجاد شود.")

app = Client("MyBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= وب‌سرور =================
def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"🌐 وب‌سرور روی پورت {port} فعال شد")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ================= تابع دانلود سریع (بدون خطای فرمت) =================
def download_audio_fast(query: str):
    """
    دانلود سریع با انتخاب خودکار بهترین فرمت صوتی (بدون شرط اضافی)
    """
    try:
        logger.info(f"🔍 شروع دانلود سریع برای: {query}")

        download_opts = {
            'format': 'bestaudio',           # همیشه بهترین فرمت صوتی موجود
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'cookiefile': COOKIE_FILE,
            'socket_timeout': 10,
            'retries': 2,
            'fragment_retries': 2,
            'concurrent_fragment_downloads': 15,   # افزایش برای سرعت بیشتر
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    # 'skip': ['dash', 'hls'],   # حذف شده تا همه فرمت‌ها بررسی شوند
                }
            },
            # در صورت نیاز به MP3، خط زیر را فعال کنید (کیفیت ۱۲۸ برای سرعت)
            # 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}],
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if not info or 'entries' not in info or not info['entries']:
                return None, "هیچ آهنگی پیدا نشد."

            entry = info['entries'][0]
            title = entry.get('title', 'Unknown')
            artist = entry.get('channel') or entry.get('uploader') or 'Unknown'
            duration = int(entry.get('duration') or 0)

            # پیدا کردن فایل دانلود شده (با هر پسوندی)
            video_id = entry.get('id')
            actual_file = None
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(video_id):
                    actual_file = os.path.join(DOWNLOAD_DIR, f)
                    break

            if actual_file and os.path.exists(actual_file):
                file_size = os.path.getsize(actual_file) // 1024  # KB
                logger.info(f"✅ دانلود سریع انجام شد: {title} (حجم: {file_size} KB)")
                return actual_file, {"title": title, "artist": artist, "duration": duration}

            return None, "فایل دانلود شده یافت نشد."

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        logger.error(f"❌ خطای دانلود: {msg}")
        if 'cookies' in msg.lower() or 'sign in' in msg.lower():
            return None, "یوتیوب درخواست را بلاک کرد. کوکی را بروز کنید."
        return None, "دانلود ناموفق بود."

    except Exception as e:
        logger.error(f"❌ خطا: {traceback.format_exc()}")
        return None, f"خطا: {str(e)}"

# ================= دستور /start =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text(
        "👋 سلام!\n"
        "نام آهنگ را بفرستید تا با سرعت بالا دانلود کنم."
    )

# ================= دریافت متن کاربر =================
@app.on_message(filters.text & ~filters.command("start"))
async def handle_music(_, message):
    query = message.text.strip()
    if not query:
        return

    status_msg = await message.reply_text(f"🔍 در حال دانلود **{query}** ...")
    file_path = None

    try:
        logger.info(f"📩 درخواست از کاربر {message.from_user.id}: {query}")

        result, meta = await asyncio.to_thread(download_audio_fast, query)

        if result is None:
            await status_msg.edit_text(f"❌ {meta}")
            return

        file_path = result
        title = meta['title']
        artist = meta['artist']
        duration = meta['duration']

        await status_msg.edit_text(f"📤 ارسال **{title}** ...")

        await message.reply_audio(
            audio=file_path,
            title=title,
            performer=artist,
            duration=duration,
            caption=f"🎵 **{title}**\n👤 {artist}"
        )

        await status_msg.delete()
        logger.info(f"✅ فایل '{title}' ارسال شد.")

    except Exception as e:
        logger.error(traceback.format_exc())
        await status_msg.edit_text("❌ خطای غیرمنتظره.")

    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info("🗑️ فایل موقت پاک شد.")
        except Exception as e:
            logger.warning(f"خطا در پاکسازی: {e}")

# ================= اجرا =================
if __name__ == "__main__":
    logger.info("🚀 ربات با حالت سریع و بدون خطای فرمت راه‌اندازی شد.")
    app.run()
