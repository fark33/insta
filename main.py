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
# بهتر است این مقادیر را از متغیرهای محیطی (Environment Variables) بخوانی
API_ID = int(os.environ.get("API_ID", "3335796"))
API_HASH = os.environ.get("API_HASH", "138b992a0e672e8346d8439c3f42ea78")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "5098580833:AAEzriKZYpbJOljEwP-8KrOsYlGY-hRyDXA")

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

# ================= تابع دانلود =================
def download_audio(query: str):
    """
    جستجو و دانلود اولین نتیجه از یوتیوب به صورت MP3 با کیفیت 192
    خروجی: (مسیر_فایل، دیکشنری_متادیتا) یا (None، پیام_خطا)
    """
    try:
        logger.info(f"🔍 شروع جستجو برای: {query}")

        # ===== مرحله ۱: جستجو و گرفتن شناسه ویدیو =====
        search_opts = {
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True,
            'extract_flat': True,
            'skip_download': True,
            'cookiefile': COOKIE_FILE,
        }

        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)

        if not info or not info.get('entries'):
            return None, "هیچ آهنگی با این نام پیدا نشد."

        entry = info['entries'][0]
        if not entry:
            return None, "خطا در دریافت اطلاعات آهنگ."

        # ساخت URL معتبر — در حالت extract_flat ممکن است url خام باشد
        video_id = entry.get('id')
        video_url = entry.get('url') or entry.get('webpage_url')
        if video_url and not str(video_url).startswith('http'):
            video_url = f"https://www.youtube.com/watch?v={video_url}"
        if not video_url and video_id:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        if not video_url:
            return None, "آدرس ویدیو پیدا نشد."

        title = entry.get('title', 'Unknown Title')
        artist = entry.get('channel') or entry.get('uploader') or 'Unknown Artist'

        logger.info(f"✅ پیدا شد: {title} - {artist}")

        # ===== مرحله ۲: دانلود با فرمت انعطاف‌پذیر =====
        # کلید فیکس: bestaudio/best (اگر صوتی خالص نبود، بهترین فرمت ترکیبی)
        download_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'cookiefile': COOKIE_FILE,
            # استفاده از کلاینت‌های مختلف برای دور زدن محدودیت فرمت در سرورهای ابری
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web_safari', 'web'],
                }
            },
            # توجه: ignoreerrors را عمداً حذف کردیم تا خطای واقعی دیده شود
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl_download:
            logger.info(f"⬇️ شروع دانلود: {title}")
            dl_info = ydl_download.extract_info(video_url, download=True)
            # مسیر فایل نهایی بعد از تبدیل به mp3 (بدون اسکن پوشه)
            base_name = ydl_download.prepare_filename(dl_info)
            file_path = os.path.splitext(base_name)[0] + '.mp3'
            duration = int(dl_info.get('duration') or entry.get('duration') or 0)

        if os.path.exists(file_path):
            logger.info(f"✅ دانلود موفق: {title} - {artist}")
            return file_path, {
                "title": title,
                "artist": artist,
                "duration": duration,
            }

        return None, "فایل دانلود شده یافت نشد."

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        logger.error(f"❌ خطای دانلود yt-dlp: {msg}")
        if 'Sign in to confirm' in msg or 'bot' in msg.lower() or 'cookies' in msg.lower():
            return None, "یوتیوب درخواست را بلاک کرد. فایل cookies.txt را بروز کن."
        return None, "دانلود ناموفق بود (فرمت موجود نیست یا ویدیو محدود است)."

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

    status_msg = await message.reply_text(f"🔍 در حال جستجو برای: **{query}** ...")
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
            await status_msg.edit_text("❌ خطا در ارسال فایل: احتمالاً حجم فایل زیاد است یا اینترنت قطع است.")

    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        logger.error(traceback.format_exc())
        await status_msg.edit_text("❌ یک خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید.")

    finally:
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
