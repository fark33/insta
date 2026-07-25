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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "5088657122:AAF3Hzm9lx6-UUQEWlI4_k1T7CJ330X6GKc")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIE_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None
if COOKIE_FILE:
    logger.info("🍪 فایل کوکی پیدا شد و استفاده می‌شود.")
else:
    logger.warning("⚠️ فایل cookies.txt پیدا نشد — احتمال بلاک شدن توسط یوتیوب بالاست.")

app = Client("MyBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= وب‌سرور برای Render =================
def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"🌐 وب‌سرور روی پورت {port} برای سلامت رندر فعال شد")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ================= تابع دانلود فوق سریع =================
def download_audio(query: str):
    """
    جستجو و دانلود مستقیم در یک مرحله بدون نیاز به کانورت FFmpeg
    """
    try:
        logger.info(f"🔍 شروع جستجو و دانلود همزمان برای: {query}")

        download_opts = {
            # کلید سرعت: فرمت 140 همان M4A اختصاصی یوتیوب است. دانلود مستقیم، بدون نیاز به تبدیل!
            'format': '140/bestaudio[ext=m4a]/bestaudio',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,           # خاموش کردن لاگ‌های اضافه برای افزایش سرعت I/O
            'no_warnings': True,
            'noplaylist': True,
            'cookiefile': COOKIE_FILE,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'tv'], # استفاده ترکیبی برای دور زدن لیمیت و لود سریع‌تر
                }
            }
            # ما postprocessors (FFmpeg) را حذف کردیم چون زمان زیادی هدر می‌داد
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            # ytsearch1 به صورت خودکار اولین نتیجه را هم پیدا و هم همان لحظه دانلود می‌کند
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if not info or 'entries' not in info or not info['entries']:
                return None, "هیچ آهنگی با این نام پیدا نشد."

            entry = info['entries'][0]
            if not entry:
                return None, "خطا در دریافت اطلاعات آهنگ."

            title = entry.get('title', 'Unknown Title')
            artist = entry.get('channel') or entry.get('uploader') or 'Unknown Artist'
            duration = int(entry.get('duration') or 0)
            video_id = entry.get('id')

            # پیدا کردن مسیر فایل دانلود شده در پوشه
            file_path = ydl.prepare_filename(entry)
            
            if os.path.exists(file_path):
                logger.info(f"✅ دانلود موفق: {title} - {artist}")
                return file_path, {"title": title, "artist": artist, "duration": duration}
            else:
                # در صورتی که افزونه به صورت پیش‌فرض چیز دیگری ذخیره کرده باشد، از روی ID پیدایش می‌کنیم
                for file in os.listdir(DOWNLOAD_DIR):
                    if file.startswith(video_id):
                        real_path = os.path.join(DOWNLOAD_DIR, file)
                        logger.info(f"✅ دانلود موفق: {title} - {artist}")
                        return real_path, {"title": title, "artist": artist, "duration": duration}

        return None, "فایل دانلود شده یافت نشد."

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        logger.error(f"❌ خطای دانلود yt-dlp: {msg}")
        if 'Sign in to confirm' in msg or 'bot' in msg.lower() or 'cookies' in msg.lower():
            return None, "یوتیوب درخواست را بلاک کرد. فایل cookies.txt را بروز کن."
        return None, "دانلود ناموفق بود (فرمت موجود نیست یا ویدیو محدود است)."

    except Exception as e:
        logger.error(f"❌ خطا در دانلود: {str(e)}")
        return None, f"خطا در دانلود: {str(e)}"

# ================= دستور /start =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text(
        "👋 سلام!\n"
        "نام آهنگ مورد نظرت را بنویس تا در چند ثانیه دانلود کنم.\n"
        "مثال: `Shape of You`"
    )

# ================= دریافت متن کاربر =================
@app.on_message(filters.text & ~filters.command("start"))
async def handle_music(_, message):
    query = message.text.strip()
    if not query:
        return

    status_msg = await message.reply_text(f"🔍 در حال دریافت **{query}** ...")
    file_path = None

    try:
        logger.info(f"📩 درخواست جدید از کاربر {message.from_user.id}: {query}")

        result, meta = await asyncio.to_thread(download_audio, query)

        if result is None:
            await status_msg.edit_text(f"❌ {meta}")
            return

        file_path = result
        title = meta.get('title', 'Unknown')
        artist = meta.get('artist', 'Unknown')
        duration = meta.get('duration', 0)

        await status_msg.edit_text(f"📤 در حال آپلود **{title}** در تلگرام...")

        try:
            await message.reply_audio(
                audio=file_path,
                title=title,
                performer=artist,
                duration=duration,
                caption=f"🎵 **{title}**\n👤 {artist}"
            )
            await status_msg.delete()
            logger.info(f"✅ فایل '{title}' ارسال شد.")

        except RPCError as e:
            logger.error(f"❌ خطا در ارسال به تلگرام: {e}")
            await status_msg.edit_text("❌ خطا در ارسال فایل به تلگرام.")

    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        await status_msg.edit_text("❌ یک خطای غیرمنتظره رخ داد.")

    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ فایل موقت {file_path} پاک شد.")
        except Exception as e:
            pass

# ================= اجرای ربات =================
if __name__ == "__main__":
    logger.info("🚀 ربات راه‌اندازی شد...")
    app.run()
