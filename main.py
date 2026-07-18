import os
import asyncio
import yt_dlp
from pyrogram import Client, filters
import traceback

# ================= تنظیمات =================
API_ID = 3335796
API_HASH = "138b992a0e672e8346d8439c3f42ea78"
BOT_TOKEN = "5098580833:AAEzriKZYpbJOljEwP-8KrOsYlGY-hRyDXA"

app = Client("MyBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= تابع دانلود هوشمند =================
async def download_media(query, user_id):
    # استفاده از ytsearch1 برای جستجوی نام آهنگ
    search_query = f"ytsearch1:{query}"
    output_filename = f"music_{user_id}.m4a"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_filename,
        'cookiefile': 'cookies.txt',
        'noplaylist': True,
        'quiet': False,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        'extractor_args': {
            'youtube': {'player_client': ['android']}
        }
    }

    try:
        # پاکسازی فایل قبلی
        if os.path.exists(output_filename):
            os.remove(output_filename)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])
            
        return output_filename if os.path.exists(output_filename) else None
    except Exception:
        print(f"❌ خطای کامل: {traceback.format_exc()}")
        return None

# ================= هندلرها =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("👋 سلام!\nنام آهنگ مورد نظرت را بنویس تا دانلود کنم.")

@app.on_message(filters.text & ~filters.command("start"))
async def process_text(client, message):
    query = message.text.strip()
    status = await message.reply("🔎 در حال جستجو و دانلود...")

    file_path = await download_media(query, message.from_user.id)

    if file_path:
        try:
            await message.reply_audio(
                audio=file_path,
                title=query,
                caption="✅ دانلود با موفقیت انجام شد."
            )
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            await status.delete()
    else:
        await status.edit("❌ خطا در جستجو یا دانلود. لطفاً دوباره تلاش کنید.")

app.run()
