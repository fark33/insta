import os
import time
import asyncio
import threading
import logging
import yt_dlp
import requests

from http.server import BaseHTTPRequestHandler, HTTPServer

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode

# ================= تنظیمات و پیکربندی لاگ‌ها =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("MusicBot")

# تنظیم سطح لاگ برای پایروگرام جهت نمایش جزئیات اتصال
logging.getLogger("pyrogram").setLevel(logging.INFO)


# ================= سرور HTTP فیک فقط برای Render Web Service =================

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot health check OK")

    def log_message(self, format, *args):
        pass


def _run_health_server():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting health check server on port {port}...")
    try:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        server.serve_forever()
    except Exception as e:
        logger.error(f"Error starting health check server: {e}")


threading.Thread(target=_run_health_server, daemon=True).start()


# =========================================================================
# تنظیمات ربات
# =========================================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
BOT_ID = os.environ.get("BOT_ID", "@YOUR_BOT_ID")

try:
    API_ID = int(os.environ.get("API_ID", "YOUR_API_ID_HERE"))
except ValueError:
    API_ID = 0

API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH_HERE")


# ایجاد کلاینت تلگرام
app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ================= سیستم آنتی‌اسپم (Cooldown) =================

user_cooldowns = {}
COOLDOWN_SECONDS = 3


# ================= جستجوی آهنگ (iTunes API) =================

async def search_song(query):
    def _search():
        try:
            logger.info(f"Searching iTunes for query: {query}")
            data = requests.get(
                "https://itunes.apple.com/search",
                params={"term": query, "media": "music", "limit": 1},
                timeout=5
            ).json()

            if data.get("resultCount"):
                item = data["results"][0]
                track = item.get("trackName", "")
                artist = item.get("artistName", "")
                logger.info(f"iTunes found track: {track} - {artist}")
                return f"{track} - {artist}"
        except Exception as e:
            logger.warning(f"iTunes search failed: {e}")
        return query

    return await asyncio.to_thread(_search)


# ================= دانلود از یوتیوب =================

async def download_music(query, user_id):
    output_filename = f"music_{user_id}.m4a"

    def _download():
        try:
            logger.info(f"Preparing download for user {user_id} - Query: {query}")
            for ext in ("m4a", "webm", "opus", "part"):
                path = f"music_{user_id}.{ext}"
                if os.path.exists(path):
                    os.remove(path)

            ydl_opts = {
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
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android']
                    }
                },
                'concurrent_fragment_downloads': 8,
                'http_chunk_size': 10 * 1024 * 1024,
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
                logger.info(f"Download successful: {output_filename}")
                return output_filename

        except Exception as e:
            logger.error(f"Error during standard download: {e}")
            try:
                logger.info("Attempting fallback download without aria2c...")
                ydl_opts.pop('external_downloader', None)
                ydl_opts.pop('external_downloader_args', None)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(f"ytsearch1:{query}", download=True)
                if os.path.exists(output_filename):
                    logger.info(f"Fallback download successful: {output_filename}")
                    return output_filename
            except Exception as e2:
                logger.error(f"Fallback download also failed: {e2}")

        return None

    return await asyncio.to_thread(_download)


# ================= اجرای هم‌زمان جست‌وجو + دانلود =================

async def process_request(query, user_id):
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
    logger.info(f"User {user_id} ({name}) sent /start")

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
    logger.info(f"User {user_id} requested: {query}")

    status = await message.reply("🔎 در حال جست‌وجو و دانلود...")
    song, file = await process_request(query, user_id)

    if file:
        logger.info(f"Uploading audio file {file} to Telegram for user {user_id}")
        await message.reply_audio(
            audio=file,
            performer="IR_BOTZ™",
            title=song,
            caption=f"🎵 {song}\n\n✅ {BOT_ID}"
        )
        try:
            os.remove(file)
            logger.info(f"Cleaned up temporary file: {file}")
        except Exception as e:
            logger.warning(f"Could not remove temp file: {e}")

        await status.delete()
    else:
        logger.warning(f"Could not find or download music for query: {query}")
        await status.edit(
            "❌ متاسفانه خطایی در دانلود پیش آمد. لطفاً دوباره تلاش کنید."
        )


# ================= اجرای پروژه =================

async def main():
    logger.info("Starting bot initialization...")
    
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or API_ID == 0:
        logger.error("❌ Critical: Credentials are not configured! Please check your environment variables.")
        return

    try:
        logger.info("Attempting to connect to Telegram...")
        await app.start()
        logger.info("✅ Music Bot is running successfully!")
        await idle()
    except Exception as e:
        logger.exception("❌ A critical error occurred while starting the bot:")
    finally:
        logger.info("Stopping Pyrogram client...")
        await app.stop()
        logger.info("Pyrogram client stopped.")


if __name__ == "__main__":
    asyncio.run(main())
