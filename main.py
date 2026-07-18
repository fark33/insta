import os
import time
import asyncio
import yt_dlp
import requests
from pyrogram import Client, filters
from pyrogram.enums import ParseMode

API_ID = 3335796 
API_HASH = "138b992a0e672e8346d8439c3f42ea78"
BOT_TOKEN = "5098580833:AAEzriKZYpbJOljEwP-8KrOsYlGY-hRyDXA"
BOT_ID = "@YOUR_BOT_ID"

app = Client(
    "MyBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= جستجوی آهنگ =================
async def search_song(query):
    def _search():
        try:
            data = requests.get(
                "https://itunes.apple.com/search",
                params={"term": query, "media": "music", "limit": 1},
                timeout=5
            ).json()
            if data.get("resultCount"):
                item = data["results"][0]
                return item.get("trackName", "") + " - " + item.get("artistName", "")
        except Exception:
            pass
        return query
    return await asyncio.to_thread(_search)

# ================= دانلود آهنگ =================
async def download_music(query, user_id):
    output_filename = f"music_{user_id}.m4a"
    def _download():
        try:
            if os.path.exists(output_filename):
                os.remove(output_filename)

            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio/best',
                'outtmpl': f'music_{user_id}.%(ext)s',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'cookiefile': 'cookies.txt', # فایل کوکی حتما باید در کنار کد باشد
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '0',
                }],
                'extractor_args': {
                    'youtube': {'player_client': ['android']},
                },
                'concurrent_fragment_downloads': 4,
                'http_chunk_size': 10485760,
                'retries': 3,
                'socket_timeout': 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(f"ytsearch1:{query}", download=True)

            if os.path.exists(output_filename):
                return output_filename
        except Exception as e:
            print(f"❌ Error during download: {e}")
        return None
    return await asyncio.to_thread(_download)

# ================= هندلرها =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("👋 سلام! ربات دانلود آهنگ فعال است. نام آهنگ را بفرست.")

@app.on_message(filters.private & filters.text)
async def music(client, message):
    query = message.text.strip()
    if query.startswith("/"): return

    status = await message.reply("🔎 در حال پیدا کردن و دانلود...")
    song = await search_song(query)
    file = await download_music(song, message.from_user.id)

    if file:
        await message.reply_audio(audio=file, performer="IR_BOTZ™", title=song, caption=f"🎵 {song}\n\n✅ {BOT_ID}")
        try: os.remove(file)
        except: pass
        await status.delete()
    else:
        await status.edit("❌ خطا در دانلود! لطفاً دوباره تلاش کنید.")

# اجرای ربات
app.run()
