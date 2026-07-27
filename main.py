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

# ================= تابع دانلود و تبدیل به MP3 با اولویت M4A =================
def download_audio_fast(query: str):
    try:
        logger.info(f"🔍 شروع دانلود سریع برای: {query}")

        # تنظیمات بهینه: اولویت با M4A، در غیر این صورت BESTAUDIO، و در نهایت تبدیل به MP3
        download_opts = {
            # 'bestaudio[ext=m4a]' یعنی اگر M4A موجود بود همان را بگیر (سریع‌ترین دانلود)،
            # در غیر این صورت '/bestaudio' یعنی هر بهترین فرمت صوتی دیگر را بگیر.
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'cookiefile': COOKIE_FILE,
            'socket_timeout': 8,
            'retries': 2,
            'fragment_retries': 2,
            'concurrent_fragment_downloads': 20,  # دانلود همزمان قطعات برای سرعت بالا
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
            # ===== بخش تبدیل به MP3 =====
            # کیفیت ۱۲۸ کیلوبیت بهترین تعادل بین حجم (حدود ۳-۴ مگابایت) و سرعت تبدیل است
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            # دریافت اطلاعات و دانلود همزمان (با توجه به تنظیمات postprocessor، خروجی نهایی MP3 است)
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if not info or 'entries' not in info or not info['entries']:
                return None, "هیچ آهنگی پیدا نشد."

            entry = info['entries'][0]
            video_id = entry.get('id')
            title = entry.get('title', 'Unknown')
            artist = entry.get('channel') or entry.get('uploader') or 'Unknown'
            duration = int(entry.get('duration') or 0)

            # پیدا کردن فایل نهایی (با پسوند mp3)
            actual_file = None
            for f in os.listdir(DOWNLOAD_DIR):
                # فایل نهایی بعد از تبدیل، با id شروع می‌شود و پسوند mp3 دارد
                if f.startswith(video_id) and f.endswith('.mp3'):
                    actual_file = os.path.join(DOWNLOAD_DIR, f)
                    break

            # اگر فایل mp3 پیدا نشد (احتمالاً تبدیل ناموفق)، فایل اصلی را چک کن
            if not actual_file:
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(video_id):
                        actual_file = os.path.join(DOWNLOAD_DIR, f)
                        break

            if actual_file and os.path.exists(actual_file):
                file_size = os.path.getsize(actual_file) // 1024  # KB
                logger.info(f"✅ دانلود و تبدیل به MP3 انجام شد: {title} (حجم: {file_size} KB)")
                return actual_file, {"title": title, "artist": artist, "duration": duration}

            return None, "فایل نهایی یافت نشد."

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
        "نام آهنگ را بفرستید تا با سرعت بالا به صورت MP3 دانلود کنم."
    )

# ================= دریافت متن کاربر =================
@app.on_message(filters.text & ~filters.command("start"))
async def handle_music(_, message):
    query = message.text.strip()
    if not query:
        return

    status_msg = await message.reply_text(f"🔍 در حال دانلود و تبدیل به MP3 **{query}** ...")
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

        await status_msg.edit_text(f"📤 ارسال **{title}** (MP3) ...")

        await message.reply_audio(
            audio=file_path,
            title=title,
            performer=artist,
            duration=duration,
            caption=f"🎵 **{title}**\n👤 {artist}\n📀 MP3"
        )

        await status_msg.delete()
        logger.info(f"✅ فایل MP3 '{title}' ارسال شد.")

    except Exception as e:
        logger.error(traceback.format_exc())
        await status_msg.edit_text("❌ خطای غیرمنتظره.")

    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info("🗑️ فایل موقت پاک شد.")
            # پاکسازی فایل‌های موقت دیگر (اگر yt-dlp فایل اضافی باقی گذاشته باشد)
            for f in os.listdir(DOWNLOAD_DIR):
                if f.endswith(('.m4a', '.webm', '.opus', '.aac')):
                    os.remove(os.path.join(DOWNLOAD_DIR, f))
        except Exception as e:
            logger.warning(f"خطا در پاکسازی: {e}")

# ================= اجرا =================
if __name__ == "__main__":
    logger.info("🚀 ربات با اولویت M4A و تبدیل به MP3 راه‌اندازی شد.")
    app.run()
