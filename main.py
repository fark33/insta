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

# ================= تابع دانلود و تبدیل به MP3 =================
def download_audio_as_mp3(query: str):
    """
    جستجو، دانلود بهترین فرمت صوتی و تبدیل خودکار به MP3
    """
    try:
        logger.info(f"🔍 شروع دانلود برای: {query} (تبدیل به MP3)")

        download_opts = {
            'format': 'bestaudio/best',   # بهترین کیفیت صوتی
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'cookiefile': COOKIE_FILE,
            'socket_timeout': 20,
            'retries': 3,
            'fragment_retries': 3,
            'concurrent_fragment_downloads': 5,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
            # ========== پس‌پردازش برای تبدیل به MP3 ==========
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',   # کیفیت ۱۹۲ کیلوبیت بر ثانیه
            }],
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if not info or 'entries' not in info or not info['entries']:
                return None, "هیچ آهنگی با این نام پیدا نشد."

            entry = info['entries'][0]
            if not entry:
                return None, "خطا در دریافت اطلاعات آهنگ."

            title = entry.get('title', 'Unknown Title')
            artist = entry.get('channel') or entry.get('uploader') or 'Unknown Artist'
            duration = int(entry.get('duration') or 0)

            # پس از تبدیل، نام فایل به .mp3 تغییر می‌کند، بنابراین باید جستجو کنیم
            video_id = entry.get('id')
            actual_file = None
            for f in os.listdir(DOWNLOAD_DIR):
                # فایل نهایی ممکن است با id شروع شود و پسوند mp3 داشته باشد
                if f.startswith(video_id) and f.endswith('.mp3'):
                    actual_file = os.path.join(DOWNLOAD_DIR, f)
                    break

            if not actual_file:
                # اگر به هر دلیل پیدا نشد، فایل اصلی را چک می‌کنیم (احتمالاً تبدیل نشده)
                expected = ydl.prepare_filename(entry)
                if os.path.exists(expected):
                    actual_file = expected
                else:
                    return None, "فایل MP3 ساخته نشد."

            if actual_file and os.path.exists(actual_file):
                logger.info(f"✅ دانلود و تبدیل به MP3 انجام شد: {title} (مسیر: {actual_file})")
                return actual_file, {
                    "title": title,
                    "artist": artist,
                    "duration": duration,
                }

            return None, "فایل نهایی یافت نشد."

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
        "نام آهنگ مورد نظرت را بنویس تا به صورت MP3 دانلود کنم.\n"
        "مثال: `Shape of You`"
    )

# ================= دریافت متن کاربر =================
@app.on_message(filters.text & ~filters.command("start"))
async def handle_music(_, message):
    query = message.text.strip()
    if not query:
        return

    status_msg = await message.reply_text(f"🔍 در حال جستجو و دانلود (تبدیل به MP3): **{query}** ...")
    file_path = None

    try:
        logger.info(f"📩 درخواست جدید از کاربر {message.from_user.id}: {query}")

        result, meta = await asyncio.to_thread(download_audio_as_mp3, query)

        if result is None:
            await status_msg.edit_text(f"❌ {meta}")
            logger.warning(f"⛔ خطا برای کاربر {message.from_user.id}: {meta}")
            return

        file_path = result
        title = meta.get('title', 'Unknown')
        artist = meta.get('artist', 'Unknown')
        duration = meta.get('duration', 0)

        await status_msg.edit_text(f"📤 در حال ارسال **{title}** (MP3) ...")

        try:
            await message.reply_audio(
                audio=file_path,
                title=title,
                performer=artist,
                duration=duration,
                caption=f"🎵 **{title}**\n👤 {artist}\n📀 MP3"
            )
            await status_msg.delete()
            logger.info(f"✅ فایل MP3 '{title}' برای کاربر {message.from_user.id} ارسال شد.")

        except RPCError as e:
            logger.error(f"❌ خطا در ارسال به تلگرام: {e}")
            await status_msg.edit_text("❌ خطا در ارسال فایل به تلگرام.")

    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        logger.error(traceback.format_exc())
        await status_msg.edit_text("❌ یک خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید.")

    finally:
        # پاکسازی فایل‌های نهایی و موقت
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ فایل MP3 {file_path} پاک شد.")
            # همچنین فایل‌های موقت دیگر (پسوندهای دیگر) را پاک کن
            for f in os.listdir(DOWNLOAD_DIR):
                if f.endswith(('.m4a', '.webm', '.opus', '.aac')):
                    os.remove(os.path.join(DOWNLOAD_DIR, f))
                    logger.info(f"🗑️ فایل موقت {f} پاک شد.")
        except Exception as e:
            logger.warning(f"⚠️ خطا در پاکسازی فایل: {e}")

# ================= اجرای ربات =================
if __name__ == "__main__":
    logger.info("🚀 ربات با قابلیت تبدیل به MP3 راه‌اندازی شد...")
    app.run()
