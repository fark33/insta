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
async def download_media(url, user_id):
    # مسیر ذخیره فایل برای هر کاربر مجزا
    output_path = f"downloads/media_{user_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_path}.%(ext)s',
        'cookiefile': 'cookies.txt',
        'noplaylist': True,
        'quiet': False, # برای دیدن جزئیات در لاگ
        'ignoreerrors': False,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        # تنظیمات برای پشتیبانی از تمام سایت‌ها (مثل اینستا، یوتیوب، توییتر و غیره)
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        },
    }

    try:
        # پاک کردن فایل قدیمی قبل از دانلود جدید
        for ext in ['m4a', 'mp3', 'webm']:
            if os.path.exists(f"{output_path}.{ext}"):
                os.remove(f"{output_path}.{ext}")

        # اجرای دانلود
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # تبدیل به m4a اگر فرمت دیگری بود
            base, ext = os.path.splitext(filename)
            final_file = f"{base}.m4a"
            return final_file if os.path.exists(final_file) else None

    except Exception:
        print(f"❌ خطای کامل: {traceback.format_exc()}")
        return None

# ================= هندلرها =================
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("👋 سلام!\nلینک هر آهنگی (یوتیوب، اینستاگرام و...) را بفرستید تا دانلود کنم.")

@app.on_message(filters.text & ~filters.command("start"))
async def handle_message(client, message):
    url = message.text.strip()
    status = await message.reply("⏳ در حال دریافت اطلاعات...")

    file_path = await download_media(url, message.from_user.id)

    if file_path:
        await message.reply_audio(audio=file_path, caption="✅ فایل آماده شد")
        os.remove(file_path) # پاکسازی بعد از ارسال
    else:
        await message.reply("❌ دانلود ناموفق بود. لاگ‌های Render را چک کنید.")
    
    await status.delete()

# ایجاد پوشه دانلود در صورت نبودن
if not os.path.exists('downloads'):
    os.makedirs('downloads')

app.run()
