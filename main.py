import os
import time
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


# ================= جستجوی آهنگ (iTunes برای اسم/خواننده تمیز) =================
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


# ================= دانلود آهنگ از یوتیوب =================
async def download_music(query, user_id):
    output_filename = f"music_{user_id}.m4a"

    def _download():
        try:
            if os.path.exists(output_filename):
                os.remove(output_filename)

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'music_{user_id}.%(ext)s',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'cookiefile': 'cookies.txt',  # فایل باید کنار main.py باشه و با # Netscape HTTP Cookie File شروع بشه
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '192',
                }],
                'retries': 10,
                'fragment_retries': 10,
                'socket_timeout': 20,
                'geo_bypass': True,
                # کلیدی‌ترین بخش: استفاده از کلاینت اندروید/آی‌او‌اس
                # تا نیاز به PO Token (که باعث خطای format not available می‌شد) نداشته باشیم
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios', 'web'],
                        'player_skip': ['webpage'],
                    }
                },
                'http_headers': {
                    'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip'
                },
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # چند نتیجه جستجو می‌کنیم تا اگه اولی قابل دانلود نبود، بریم سراغ بعدی
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                entries = info.get('entries', []) if info else []

                for entry in entries:
                    if entry is None:
                        continue
                    try:
                        video_url = entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        ydl.download([video_url])
                        if os.path.exists(output_filename):
                            return output_filename
                    except Exception as inner_e:
                        print(f"⚠️ رد شد از ویدیو {entry.get('id')}: {inner_e}")
                        continue

        except Exception as e:
            print(f"❌ Error: {e}")
        return None

    return await asyncio.to_thread(_download)


# ================= هندلرها =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("👋 سلام! ربات آماده دریافت نام آهنگ است.")


@app.on_message(filters.private & filters.text)
async def music(client, message):
    query = message.text.strip()
    if query.startswith("/"):
        return

    status = await message.reply("🔎 در حال جستجو و دانلود...")

    song = await search_song(query)
    file = await download_music(song, message.from_user.id)

    if file:
        await message.reply_audio(
            audio=file,
            performer="IR_BOTZ™",
            title=song,
            caption=f"🎵 {song}\n\n✅ {BOT_ID}"
        )
        try:
            os.remove(file)
        except Exception:
            pass
        await status.delete()
    else:
        await status.edit("❌ خطا در دریافت فایل. لطفاً دوباره تلاش کنید.")


# ================= اجرای ربات (بدون نیاز به پورت) =================
app.run()
