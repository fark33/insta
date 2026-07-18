import os
import time
import asyncio
import logging

import requests
import yt_dlp

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode

# ================= لاگ =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("MusicBot")


# ================= تنظیمات =================
# طبق درخواست، مقادیر مستقیم اینجا هاردکد شدن (به‌جای .env).
# توجه: چون این مقادیر داخل کد هستن، اگه این فایل رو در جایی عمومی (گیت‌هاب و ...) آپلود کنی
# لو میرن. برای یک ربات شخصی/خصوصی روی سرور خودت مشکلی نداره.

BOT_TOKEN = "5098580833:AAEzriKZYpbJOljEwP-8KrOsYlGY-hRyDXA"
API_ID = 3335796
API_HASH = "138b992a0e672e8346d8439c3f42ea78"
BOT_ID = "@YOUR_BOT_ID"

COOLDOWN_SECONDS = 3

# مسیر ذخیره‌سازی session (برای persistent volume در Docker)
WORKDIR = "/app/data"
os.makedirs(WORKDIR, exist_ok=True)

app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8,
    workdir=WORKDIR,
)

# ================= آنتی‌اسپم (Cooldown) =================
user_cooldowns: dict[int, float] = {}


def on_cooldown(user_id: int) -> bool:
    now = time.time()
    if now - user_cooldowns.get(user_id, 0) < COOLDOWN_SECONDS:
        return True
    user_cooldowns[user_id] = now
    return False


# ================= جستجوی آهنگ (iTunes API) =================
async def search_song(query: str) -> str:
    def _search():
        try:
            data = requests.get(
                "https://itunes.apple.com/search",
                params={"term": query, "media": "music", "limit": 1},
                timeout=5,
            ).json()

            if data.get("resultCount"):
                item = data["results"][0]
                return f"{item.get('trackName', '')} - {item.get('artistName', '')}"
        except Exception as e:
            log.warning("search_song failed: %s", e)
        return query

    return await asyncio.to_thread(_search)


# ================= دانلود موزیک =================
async def download_music(query: str, user_id: int) -> str | None:
    output_filename = os.path.join(WORKDIR, f"music_{user_id}.m4a")

    def _download():
        t0 = time.time()
        try:
            if os.path.exists(output_filename):
                os.remove(output_filename)

            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio/best",
                "outtmpl": os.path.join(WORKDIR, f"music_{user_id}.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "0",
                }],
                "extractor_args": {
                    "youtube": {"player_client": ["android"]},
                },
                "concurrent_fragment_downloads": 4,
                "http_chunk_size": 10485760,
                "retries": 3,
                "socket_timeout": 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(f"ytsearch1:{query}", download=True)

            if os.path.exists(output_filename):
                log.info("دانلود در %.2f ثانیه انجام شد", time.time() - t0)
                return output_filename

        except Exception as e:
            log.error("خطا در دانلود: %s", e)

        return None

    return await asyncio.to_thread(_download)


# ================= START =================
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    if on_cooldown(message.from_user.id):
        return

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
        disable_web_page_preview=True,
    )


# ================= دریافت آهنگ =================
@app.on_message(filters.private & filters.text)
async def music(client, message):
    query = message.text.strip()
    user_id = message.from_user.id

    if query.startswith("/"):
        return

    if on_cooldown(user_id):
        return

    status = await message.reply("🔎 در حال پیدا کردن آهنگ...")
    song = await search_song(query)

    await status.edit("⏳ در حال دانلود...")
    file = await download_music(song, user_id)

    if file:
        await message.reply_audio(
            audio=file,
            performer="IR_BOTZ™",
            title=song,
            caption=f"🎵 {song}\n\n✅ {BOT_ID}",
        )

        try:
            os.remove(file)
        except Exception:
            pass

        await status.delete()
    else:
        await status.edit("❌ متاسفانه خطایی در دانلود پیش آمد. لطفاً دوباره تلاش کنید.")


# ================= اجرای پروژه =================
async def main():
    await app.start()
    log.info("✅ Music Bot is running successfully!")
    await idle()
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
