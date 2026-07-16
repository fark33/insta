import os
import time
import asyncio
import threading
import yt_dlp
import requests

from http.server import BaseHTTPRequestHandler, HTTPServer

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode


# ================= سرور HTTP فیک فقط برای Render Web Service =================
# Render برای Web Service انتظار داره پورتی باز باشه، وگرنه
# فکر می‌کنه سرویس بالا نیومده. این سرور فقط همین پورت رو باز نگه می‌داره
# و هیچ ربطی به منطق ربات نداره.

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # جلوگیری از شلوغی لاگ‌ها با درخواست‌های health-check


def _run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


threading.Thread(target=_run_health_server, daemon=True).start()


# =========================================================================
# تنظیمات ربات
# تو می‌توانی مقادیر را مستقیماً داخل کوتیشن‌های دوم بنویسی (به عنوان زاپاس)
# یا آن‌ها را در بخش Environment Variables پنل رندر ست کنی.
# =========================================================================

# توکن ربات تلگرام شما
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# آیدی ربات شما (حتماً با @ شروع شود)
BOT_ID = os.environ.get("BOT_ID", "@YOUR_BOT_ID")

# کد عددی API_ID (اگر دستی می‌نویسی، کوتیشن‌ها را پاک کن و عدد بگذار، مثل: 123456)
try:
    API_ID = int(os.environ.get("API_ID", "YOUR_API_ID_HERE"))
except ValueError:
    API_ID = 0

# کد هش API_HASH شما
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH_HERE")


app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ================= سیستم آنتی‌اسپم (Cooldown) =================

user_cooldowns = {}
COOLDOWN_SECONDS = 3  # مقدار ثانیه برای محدودیت ارسال پیام رگباری


# ================= جستجوی آهنگ (iTunes API) =================

async def search_song(query):

    def _search():
        try:
            data = requests.get(
                "https://itunes.apple.com/search",
                params={
                    "term": query,
                    "media": "music",
                    "limit": 1
                },
                timeout=5
            ).json()

            if data.get("resultCount"):
                item = data["results"][0]
                return (
                    item.get("trackName", "")
                    + " - "
                    + item.get("artistName", "")
                )
        except Exception:
            pass
        return query

    return await asyncio.to_thread(_search)


# ================= دانلود هوشمند و سریع از یوتیوب =================

async def download_music(query, user_id):

    output_filename = f"music_{user_id}.m4a"

    def _download():
        try:
            # حذف فایل‌های قدیمی احتمالی (هر پسوندی)
            for ext in ("m4a", "webm", "opus", "part"):
                path = f"music_{user_id}.{ext}"
                if os.path.exists(path):
                    os.remove(path)

            ydl_opts = {
                # اولویت با فرمت m4a آماده تا نیازی به ترنسکد سنگین نباشه
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': f'music_{user_id}.%(ext)s',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,

                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }],

                # فقط کلاینت اندروید: سریع‌تر از تست پشت‌سرهم چند کلاینت
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android']
                    }
                },

                # دانلود موازی فرگمنت‌ها برای فرمت‌های DASH/HLS
                'concurrent_fragment_downloads': 8,

                # اجازه‌ی درخواست‌های range موازی برای فایل http مستقیم
                'http_chunk_size': 10 * 1024 * 1024,

                # اگر aria2c نصب باشه از دانلودر چندکانکشنه استفاده کن
                'external_downloader': 'aria2c',
                'external_downloader_args': {
                    'aria2c': ['-x', '16', '-s', '16', '-k', '1M']
                },

                'retries': 3,
                'socket_timeout': 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(f"ytsearch1:{query}", download=True)

            if os.path.exists(output_filename):
                return output_filename

        except Exception as e:
            print(f"❌ Error during download: {e}")

            # تلاش دوباره بدون aria2c اگر نصب نبود یا خطا داد
            try:
                ydl_opts.pop('external_downloader', None)
                ydl_opts.pop('external_downloader_args', None)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(f"ytsearch1:{query}", download=True)
                if os.path.exists(output_filename):
                    return output_filename
            except Exception as e2:
                print(f"❌ Retry error: {e2}")

        return None

    return await asyncio.to_thread(_download)


# ================= اجرای هم‌زمان جست‌وجو + دانلود =================

async def process_request(query, user_id):
    # اجرای موازی تسک‌ها برای به حداقل رساندن زمان پاسخ‌دهی
    song_task = asyncio.create_task(search_song(query))
    file_task = asyncio.create_task(download_music(query, user_id))

    song, file = await asyncio.gather(song_task, file_task)
    return song, file


# ================= START =================

@app.on_message(filters.command("start") & filters.private)
async def start(client, message):

    user_id = message.from_user.id
    current_time = time.time()

    if current_time - user_cooldowns.get(user_id, 0) < COOLDOWN_SECONDS:
        return

    user_cooldowns[user_id] = current_time

    name = message.from_user.first_name

    text = f"""
<b>👋 سلام {name} عزیز خوش آمدید❤️

🔮 من ربات کاربردی دانلود آهنگ هستم.

هم اکنون نام آهنگ موردنظرتو برام بفرست.
تا برات فایلشو بفرستم💗😍

🖍️ سازنده ربات :
<a href="https://telegram.me/farshidband">FﾑRSみɨo-BﾑŊo</a></b>
"""

    await message.reply(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


# ================= دریافت آهنگ =================

@app.on_message(filters.private & filters.text)
async def music(client, message):

    query = message.text.strip()
    user_id = message.from_user.id

    if query.startswith("/"):
        return

    current_time = time.time()

    if current_time - user_cooldowns.get(user_id, 0) < COOLDOWN_SECONDS:
        return

    user_cooldowns[user_id] = current_time

    status = await message.reply("🔎 در حال جست‌وجو و دانلود...")

    song, file = await process_request(query, user_id)

    if file:

        await message.reply_audio(
            audio=file,
            performer="IR_BOTZ™",
            title=song,
            caption=f"""
🎵 {song}

✅ {BOT_ID}
"""
        )

        try:
            os.remove(file)
        except Exception:
            pass

        await status.delete()

    else:

        await status.edit(
            "❌ متاسفانه خطایی در دانلود پیش آمد. لطفاً دوباره تلاش کنید."
        )


# ================= اجرای پروژه =================

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or API_ID == 0:
        print("❌ خطا: لطفاً توکن، API_ID و API_HASH خود را در کدهای بالا یا در بخش Environment Variables رندر تنظیم کنید!")
        return

    await app.start()
    print("✅ Music Bot is running successfully!")
    
    # متد idle کمک می‌کند سشن به صورت کاملاً امن با خاموش شدن سرور بسته شود
    await idle()
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
