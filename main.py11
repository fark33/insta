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
API_ID = 3335796
API_HASH = "138b992a0e672e8346d8439c3f42ea78"
BOT_TOKEN = "5098580833:AAEzriKZYpbJOljEwP-8KrOsYlGY-hRyDXA"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Client("MyBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= وب‌سرور برای Render =================
def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"🌐 وب‌سرور روی پورت {port} برای سلامت رندر فعال شد")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ================= تابع دانلود با رویکرد جدید =================
def download_audio(query: str):
    """
    جستجو و دانلود اولین نتیجه از یوتیوب به صورت MP3 با کیفیت 192
    خروجی: (مسیر_فایل, دیکشنری_متادیتا) یا (None, پیام_خطا)
    """
    try:
        logger.info(f"🔍 شروع جستجو برای: {query}")

        # ===== مرحله ۱: فقط URL را بگیر (بدون درخواست فرمت) =====
        search_opts = {
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True,
            'extract_flat': True,          # فقط اطلاعات سطحی
            'ignoreerrors': True,
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        }

        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if not info or 'entries' not in info or len(info['entries']) == 0:
                return None, "هیچ آهنگی با این نام پیدا نشد."

            entry = info['entries'][0]
            if entry is None:
                return None, "خطا در دریافت اطلاعات آهنگ."

            # استخراج URL و متادیتا
            video_url = entry.get('url') or entry.get('webpage_url')
            if not video_url:
                return None, "آدرس ویدیو پیدا نشد."

            title = entry.get('title', 'Unknown Title')
            artist = entry.get('channel', entry.get('uploader', 'Unknown Artist'))
            duration = entry.get('duration', 0)

            logger.info(f"✅ پیدا شد: {title} - {artist}")

        # ===== مرحله ۲: دانلود با بهترین فرمت صوتی موجود =====
        download_opts = {
            'format': 'bestaudio',         # بهترین فرمت صوتی (هر کدکی)
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'ignoreerrors': True,
            'extractaudio': True,          # استخراج صوتی
            'audioformat': 'mp3',          # تبدیل نهایی به mp3
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl_download:
            logger.info(f"⬇️ شروع دانلود: {title}")
            ydl_download.download([video_url])

        # پیدا کردن فایل دانلود شده
        mp3_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.mp3')]
        if mp3_files:
            mp3_files.sort(
                key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)),
                reverse=True
            )
            file_path = os.path.join(DOWNLOAD_DIR, mp3_files[0])
            if os.path.exists(file_path):
                logger.info(f"✅ دانلود موفق: {title} - {artist}")
                return file_path, {
                    "title": title,
                    "artist": artist,
                    "duration": int(duration) if duration else 0
                }

        return None, "فایل دانلود شده یافت نشد."

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
            await status_msg.edit_text(f"❌ خطا در ارسال فایل: احتمالاً حجم فایل زیاد است یا اینترنت قطع است.")

    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        logger.error(traceback.format_exc())
        await status_msg.edit_text("❌ یک خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید.")

    finally:
        try:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ فایل موقت {file_path} پاک شد.")
        except Exception as e:
            logger.warning(f"⚠️ خطا در پاکسازی فایل: {e}")

# ================= اجرای ربات =================
if __name__ == "__main__":
    logger.info("🚀 ربات راه‌اندازی شد...")
    app.run()
