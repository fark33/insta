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

# ================= تابع دانلود سریع =================
def download_audio(query: str):
    """
    جستجو و دانلود مستقیم فرمت نیتیو M4A (فارغ از پردازش سنگین CPU)
    """
    try:
        logger.info(f"🔍 شروع دانلود مستقیم برای: {query}")

        # تنظیمات بهینه‌شده برای حداکثر سرعت روی سرور
        download_opts = {
            # فرمت 140 همان M4A نیتیو یوتیوب است (بدون نیاز به Re-encode با FFmpeg)
            'format': '140/ba[ext=m4a]/ba',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'cookiefile': COOKIE_FILE,
            'socket_timeout': 10,
            'retries': 3,
            # استفاده از کلاینت‌های بسیار سریع و بدون بن دیتاسنتر
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            # ۱. جستجو و استخراج اطلاعات
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if not info or 'entries' not in info or not info['entries']:
                return None, "هیچ آهنگی با این نام پیدا نشد."

            entry = info['entries'][0]
            if not entry:
                return None, "خطا در دریافت اطلاعات آهنگ."

            title = entry.get('title', 'Unknown Title')
            artist = entry.get('channel') or entry.get('uploader') or 'Unknown Artist'
            duration = int(entry.get('duration') or 0)

            # ۲. پیدا کردن دقیق مسیر فایل ایجاد شده روی دیسک
            expected_filename = ydl.prepare_filename(entry)
            
            # برسی چند حالت مختلف برای جلوگیری از خطای File Not Found
            actual_file = None
            if os.path.exists(expected_filename):
                actual_file = expected_filename
            else:
                # جستجو بر اساس ID ویدیو در پوشه دانلود
                video_id = entry.get('id')
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(video_id):
                        actual_file = os.path.join(DOWNLOAD_DIR, f)
                        break

            if actual_file and os.path.exists(actual_file):
                logger.info(f"✅ دانلود سریع انجام شد: {title} (مسیر: {actual_file})")
                return actual_file, {
                    "title": title,
                    "artist": artist,
                    "duration": duration,
                }

            return None, "فایل دانلود شده روی سرور یافت نشد."

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        logger.error(f"❌ خطای دانلود yt-dlp: {msg}")
        if 'Sign in to confirm' in msg or 'bot' in msg.lower() or 'cookies' in msg.lower():
            return None, "یوتیوب درخواست را بلاک کرد. فایل cookies.txt را بروز کن."
        return None, "دانلود ناموفق بود (ویدیو محدود است یا یافت نشد)."

    except Exception as e:
        logger.error(f"❌ خطا در دانلود: {str(e)}")
        logger.error(traceback.format_exc())
        return None, f"خطا در دانلود: {str(e)}"

# ================= دستور /start =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text(
        "👋 سلام!\n"
        "نام آهنگ مورد نظرت را بنویس تا دانلود کنم.\n"
        "مثال: `Shape of You`"
    )

# ================= دریافت متن کاربر =================
@app.on_message(filters.text & ~filters.command("start"))
async def handle_music(_, message):
    query = message.text.strip()
    if not query:
        return

    status_msg = await message.reply_text(f"🔍 در حال جستجو و دانلود: **{query}** ...")
    file_path = None

    try:
        logger.info(f"📩 درخواست جدید از کاربر {message.from_user.id}: {query}")

        result, meta = await asyncio.to_thread(download_audio, query)

        if result is None:
            await status_msg.edit_text(f"❌ {meta}")
            logger.warning(f"⛔ خطا برای کاربر {message.from_user.id}: {meta}")
            return

        file_path = result
        title = meta.get('title', 'Unknown')
        artist = meta.get('artist', 'Unknown')
        duration = meta.get('duration', 0)

        await status_msg.edit_text(f"📤 در حال ارسال **{title}** ...")

        try:
            await message.reply_audio(
                audio=file_path,
                title=title,
                performer=artist,
                duration=duration,
                caption=f"🎵 **{title}**\n👤 {artist}"
            )
            await status_msg.delete()
            logger.info(f"✅ فایل '{title}' برای کاربر {message.from_user.id} ارسال شد.")

        except RPCError as e:
            logger.error(f"❌ خطا در ارسال به تلگرام: {e}")
            await status_msg.edit_text("❌ خطا در ارسال فایل به تلگرام.")

    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        logger.error(traceback.format_exc())
        await status_msg.edit_text("❌ یک خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید.")

    finally:
        # پاکسازی هوشمند تمام فایل‌های باقی‌مانده مربوط به این دانلود
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ فایل موقت {file_path} پاک شد.")
        except Exception as e:
            logger.warning(f"⚠️ خطا در پاکسازی فایل: {e}")

# ================= اجرای ربات =================
if __name__ == "__main__":
    logger.info("🚀 ربات راه‌اندازی شد...")
    app.run()
