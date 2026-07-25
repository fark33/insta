import os
import time
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

# ایجاد کلاینت Pyrogram با پایداری شبکه در Render
app = Client(
    "MyBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    ipv6=False
)

# ================= وب‌سرور برای Render =================
def start_http_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"🌐 وب‌سرور روی پورت {port} فعال شد")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ================= تابع دانلود سریع و یکپارچه =================
def download_audio(query: str):
    t_start = time.perf_counter()
    logger.info(f"🔍 [شروع یکپارچه] جستجو و دانلود برای: '{query}'")

    download_opts = {
        # دریافت مستقیم فایل m4a بدون نیاز به تبدیل سنگین FFmpeg
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'cookiefile': COOKIE_FILE,
        'concurrent_fragment_downloads': 4,
        'extractor_args': {
            'youtube': {
                # استفاده از کلاینت‌های اندروید برای دور زدن پردازش جاوااسکریپت
                'player_client': ['android', 'mweb'],
            }
        },
    }

    search_target = query if query.startswith("http") else f"ytsearch1:{query}"

    try:
        t_ydl_start = time.perf_counter()
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            info = ydl.extract_info(search_target, download=True)
        t_ydl_end = time.perf_counter()
        
        logger.info(f"⏱️ [زمان yt-dlp] استخراج و دانلود مستقیم: {t_ydl_end - t_ydl_start:.2f} ثانیه")

        if not info:
            return None, "هیچ آهنگی پیدا نشد."

        entry = info['entries'][0] if 'entries' in info and info['entries'] else info
        
        base_name = ydl.prepare_filename(entry)
        file_path = os.path.splitext(base_name)[0] + '.m4a'

        if not os.path.exists(file_path) and os.path.exists(base_name):
            file_path = base_name

        if not os.path.exists(file_path):
            return None, "فایل دانلود شده یافت نشد."

        title = entry.get('title', 'Unknown Title')
        artist = entry.get('uploader') or entry.get('channel') or 'Unknown Artist'
        duration = int(entry.get('duration') or 0)

        t_total = time.perf_counter() - t_start
        logger.info(f"✅ [کل زمان پردازش دانلود]: {t_total:.2f} ثانیه")

        return file_path, {
            "title": title,
            "artist": artist,
            "duration": duration,
        }

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ خطای yt-dlp: {e}")
        return None, "دانلود ناموفق بود."
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}\n{traceback.format_exc()}")
        return None, f"خطا: {str(e)}"

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

    t_req_start = time.perf_counter()
    status_msg = await message.reply_text(f"🔍 در حال پردازش: **{query}** ...")
    file_path = None

    try:
        logger.info(f"📩 درخواست جدید از کاربر {message.from_user.id}: {query}")

        # دانلود یکپارچه
        result, meta = await asyncio.to_thread(download_audio, query)
        t_dl_done = time.perf_counter()

        if result is None:
            await status_msg.edit_text(f"❌ {meta}")
            return

        file_path = result
        title = meta.get('title', 'Unknown')
        artist = meta.get('artist', 'Unknown')
        duration = meta.get('duration', 0)

        await status_msg.edit_text(f"📤 در حال ارسال **{title}** به تلگرام ...")

        # آپلود به تلگرام
        t_up_start = time.perf_counter()
        await message.reply_audio(
            audio=file_path,
            title=title,
            performer=artist,
            duration=duration,
            caption=f"🎵 **{title}**\n👤 {artist}"
        )
        await status_msg.delete()
        t_up_end = time.perf_counter()

        # ثبت گزارش زمان‌بندی
        time_dl = t_dl_done - t_req_start
        time_up = t_up_end - t_up_start
        time_total = t_up_end - t_req_start

        logger.info(
            f"📊 [آمار زمان‌بندی دقیق]\n"
            f" ├ ⏱️ دانلود از یوتیوب: {time_dl:.2f} ثانیه\n"
            f" ├ 📤 آپلود به تلگرام: {time_up:.2f} ثانیه\n"
            f" └ 🚀 کل زمان پاسخ‌دهی: {time_total:.2f} ثانیه"
        )

    except RPCError as e:
        logger.error(f"❌ خطای تلگرام: {e}")
        await status_msg.edit_text("❌ خطا در ارسال فایل به تلگرام.")
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        await status_msg.edit_text("❌ خطایی رخ داد.")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

# ================= اجرای ربات =================
if __name__ == "__main__":
    logger.info("🚀 ربات با بهینه‌سازی کامل راه‌اندازی شد...")
    app.run()
