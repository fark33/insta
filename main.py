import os
import time
import html
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

# ================= متغیرهای محیطی =================
API_ID = int(os.environ.get("API_ID", "3335796"))
API_HASH = os.environ.get("API_HASH", "138b992a0e672e8346d8439c3f42ea78")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "5088657122:AAGGal-y6fXHjtwdD74AxE-dOWzPvcdfSjU")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIE_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None
if COOKIE_FILE:
    logger.info("🍪 فایل کوکی پیدا شد و استفاده می‌شود.")

# ================= کلاینت پایروگرام =================
app = Client(
    "MyBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    ipv6=False,
    workers=4
)

# ================= وب‌سرور جهت پینگ Render =================
def start_http_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"🌐 وب‌سرور پینگ روی پورت {port} فعال شد.")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ================= منطق دانلود سریع =================
def download_audio(query: str):
    t_start = time.perf_counter()

    download_opts = {
        # فرمت اختصاصی M4A با بالا‌ترین اولویت + حذف کامل webm
        'format': 'bestaudio[ext=m4a]/bestaudio/ba',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'cookiefile': COOKIE_FILE,
        
        # --- بهینه‌سازی‌های ویژه سرعت (Turbo Speed) ---
        'concurrent_fragment_downloads': 4,
        'http_chunk_size': 1048576,  # چانک‌های ۱ مگابایتی برای حداکثر پهنای باند
        'nocheckcertificate': True,
        'geo_bypass': True,
    }

    search_target = query if query.startswith("http") else f"ytsearch1:{query}"

    try:
        t_ydl_start = time.perf_counter()
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            info = ydl.extract_info(search_target, download=True)
        t_ydl_end = time.perf_counter()

        if not info:
            return None, "هیچ آهنگی پیدا نشد."

        entry = info['entries'][0] if 'entries' in info and info['entries'] else info
        file_path = ydl.prepare_filename(entry)

        if not os.path.exists(file_path):
            return None, "فایل دانلود شده یافت نشد."

        title = entry.get('title', 'Unknown Title')
        artist = entry.get('uploader') or entry.get('channel') or 'Unknown Artist'
        duration = int(entry.get('duration') or 0)

        t_total = time.perf_counter() - t_start
        logger.info(f"⏱️ [yt-dlp] دریافت استریم m4a در {t_ydl_end - t_ydl_start:.2f} ثانیه (کل پردازش: {t_total:.2f} ثانیه)")

        return file_path, {
            "title": title,
            "artist": artist,
            "duration": duration,
        }

    except Exception as e:
        logger.error(f"❌ خطای yt-dlp: {e}\n{traceback.format_exc()}")
        return None, f"خطا در دریافت فایل: {str(e)}"

# ================= دستور /start =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text(
        "👋 **سلام! به ربات دانلود موزیک خوش آمدید.**\n\n"
        "کافیست نام آهنگ یا لینک یوتیوب را بفرستید تا سریعاً دانلود شود."
    )

# ================= هندلر دریافت متن =================
@app.on_message(filters.text & ~filters.command("start"))
async def handle_music(_, message):
    query = message.text.strip()
    if not query:
        return

    t_req_start = time.perf_counter()
    safe_query = html.escape(query)
    status_msg = await message.reply_text(f"🔍 در حال جستجو و دانلود: <b>{safe_query}</b> ...")
    file_path = None

    try:
        result, meta = await asyncio.to_thread(download_audio, query)
        t_dl_done = time.perf_counter()

        if result is None:
            await status_msg.edit_text(f"❌ {html.escape(str(meta))}")
            return

        file_path = result
        title = meta.get('title', 'Unknown')
        artist = meta.get('artist', 'Unknown')
        duration = meta.get('duration', 0)

        safe_title = html.escape(title)
        safe_artist = html.escape(artist)

        await status_msg.edit_text(f"📤 در حال ارسال <b>{safe_title}</b> به تلگرام ...")

        t_up_start = time.perf_counter()
        await message.reply_audio(
            audio=file_path,
            title=title,
            performer=artist,
            duration=duration,
            caption=f"🎵 <b>{safe_title}</b>\n👤 {safe_artist}"
        )
        await status_msg.delete()
        t_up_end = time.perf_counter()

        logger.info(
            f"📊 [گزارش زمان‌بندی V2.6 Turbo]\n"
            f" ├ ⏱️ زمان دانلود: {t_dl_done - t_req_start:.2f} ثانیه\n"
            f" ├ 📤 زمان آپلود: {t_up_end - t_up_start:.2f} ثانیه\n"
            f" └ 🚀 زمان کل: {t_up_end - t_req_start:.2f} ثانیه"
        )

    except RPCError as e:
        logger.error(f"❌ خطای تلگرام: {e}")
        await status_msg.edit_text("❌ خطا در ارسال فایل به تلگرام.")
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        await status_msg.edit_text("❌ خطایی در پردازش رخ داد.")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

if __name__ == "__main__":
    logger.info("🚀 [VERSION 2.6 Turbo] ربات با فرمت اختصاصی m4a و دانلود فوق‌سریع راه‌اندازی شد...")
    app.run()
