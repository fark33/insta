import os
import asyncio
import logging
import traceback
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message
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

# ================= تابع دانلود (همگام) =================
def download_audio(query: str):
    """
    جستجو و دانلود اولین نتیجه از یوتیوب به صورت MP3 با کیفیت 192
    خروجی: (مسیر_فایل, دیکشنری_متادیتا) یا (None, پیام_خطا)
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'cookiefile': 'cookies.txt',  # استفاده از کوکی
        'quiet': True,               # خروجی کم yt-dlp
        'no_warnings': True,
        'default_search': 'ytsearch', # اگر آدرس نبود، جستجو کن
        'noplaylist': True,           # فقط اولین آهنگ
    }

    try:
        logger.info(f"🔍 شروع جستجو برای: {query}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # با ytsearch1 دقیقاً اولین نتیجه را می‌گیریم
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if not info or 'entries' not in info or len(info['entries']) == 0:
                logger.warning(f"⚠️ نتیجه‌ای برای '{query}' پیدا نشد.")
                return None, "هیچ آهنگی با این نام پیدا نشد."

            entry = info['entries'][0]
            if entry is None:
                return None, "خطا در دریافت اطلاعات آهنگ."

            # گرفتن مسیر فایل دانلود شده
            file_path = None
            if 'requested_downloads' in entry and entry['requested_downloads']:
                file_path = entry['requested_downloads'][0].get('filepath')

            # اگر مسیر را نگرفت، جدیدترین فایل mp3 پوشه را پیدا کن
            if not file_path or not os.path.exists(file_path):
                mp3_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.mp3')]
                if mp3_files:
                    # مرتب‌سازی بر اساس زمان تغییر (جدیدترین)
                    mp3_files.sort(
                        key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)),
                        reverse=True
                    )
                    file_path = os.path.join(DOWNLOAD_DIR, mp3_files[0])
                else:
                    return None, "فایل دانلود شده در سرور پیدا نشد."

            if not os.path.exists(file_path):
                logger.error(f"❌ فایل در مسیر {file_path} وجود ندارد.")
                return None, "فایل دانلود شده یافت نشد."

            # استخراج متادیتا برای ارسال به تلگرام
            artist = entry.get('artist') or entry.get('uploader') or 'Unknown Artist'
            title = entry.get('title', 'Unknown Title')
            duration = entry.get('duration', 0)

            logger.info(f"✅ دانلود موفق: {title} - {artist}")
            return file_path, {
                "title": title,
                "artist": artist,
                "duration": int(duration)
            }

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

# ================= دریافت متن کاربر (جستجوی آهنگ) =================
@app.on_message(filters.text & ~filters.command("start"))
async def handle_music(_, message: Message):
    query = message.text.strip()
    if not query:
        return

    # پیام وضعیت (درحال جستجو)
    status_msg = await message.reply_text(f"🔍 در حال جستجو برای: **{query}** ...")

    try:
        logger.info(f"📩 درخواست جدید از کاربر {message.from_user.id}: {query}")

        # اجرای تابع دانلود در یک thread جداگانه (تا ربات قفل نشود)
        result, meta = await asyncio.to_thread(download_audio, query)

        # بررسی خطا
        if result is None:
            await status_msg.edit_text(f"❌ {meta}")
            logger.warning(f"⛔ خطا برای کاربر {message.from_user.id}: {meta}")
            return

        file_path = result
        title = meta.get('title', 'Unknown')
        artist = meta.get('artist', 'Unknown')
        duration = meta.get('duration', 0)

        # بروزرسانی وضعیت
        await status_msg.edit_text(f"📤 در حال ارسال **{title}** ...")

        # ارسال فایل صوتی به کاربر
        try:
            await message.reply_audio(
                audio=file_path,
                title=title,
                performer=artist,
                duration=duration,
                caption=f"🎵 **{title}**\n👤 {artist}"
            )
            await status_msg.delete()  # پاک کردن پیام وضعیت
            logger.info(f"✅ فایل '{title}' برای کاربر {message.from_user.id} ارسال شد.")

        except RPCError as e:
            logger.error(f"❌ خطا در ارسال به تلگرام: {e}")
            await status_msg.edit_text(f"❌ خطا در ارسال فایل: احتمالاً حجم فایل زیاد است یا اینترنت قطع است.")

    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        logger.error(traceback.format_exc())
        await status_msg.edit_text("❌ یک خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید.")

    finally:
        # پاکسازی فایل دانلود شده (حتی اگر خطا رخ داده باشد)
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
