import os
import asyncio
import yt_dlp
import requests
from pyrogram import Client, filters

# ================= تنظیمات اصلی =================
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

# ================= توابع جانبی =================
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
                return f"{item.get('trackName')} - {item.get('artistName')}"
        except Exception:
            pass
        return query
    return await asyncio.to_thread(_search)

async def download_music(query, user_id):
    output_filename = f"music_{user_id}.m4a"
    
    def _download():
        if os.path.exists(output_filename):
            os.remove(output_filename)

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'music_{user_id}.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'cookiefile': 'cookies.txt',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192',
            }],
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36'
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"ytsearch1:{query}"])
            return output_filename if os.path.exists(output_filename) else None
        except Exception as e:
            print(f"❌ Error in download_music: {e}")
            return None

    return await asyncio.to_thread(_download)

# ================= هندلرها =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("👋 سلام!\nبه ربات دانلود موزیک خوش آمدید.\nنام آهنگ یا لینک را بفرستید.")

@app.on_message(filters.private & filters.text)
async def music_handler(client, message):
    if message.text.startswith("/"):
        return

    status = await message.reply("🔎 در حال جستجو و دانلود...")

    query = message.text.strip()
    song_title = await search_song(query)
    file_path = await download_music(song_title, message.from_user.id)

    if file_path:
        try:
            await message.reply_audio(
                audio=file_path,
                performer="IR_BOTZ™",
                title=song_title,
                caption=f"🎵 {song_title}\n\n✅ {BOT_ID}"
            )
        except Exception as e:
            print(f"⚠️ خطای ارسال به تلگرام: {e}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            await status.delete()
    else:
        await status.edit("❌ خطا در دریافت فایل. لطفاً دوباره تلاش کنید.")

# ================= اجرای ربات =================
app.run()
