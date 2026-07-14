import os
import glob
import threading
import yt_dlp
from pyrogram import Client, filters
from fastapi import FastAPI
import uvicorn

# تنظیمات محیطی
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# ایجاد پوشه دانلود برای جلوگیری از شلوغی
if not os.path.exists("downloads"):
    os.makedirs("downloads")

app_web = FastAPI()

@app_web.get("/")
def home():
    return {"status": "Bot is running"}

def run_web():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app_web, host="0.0.0.0", port=port)

bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def download_media(url):
    """تابع دانلود با استفاده از yt-dlp و تنظیمات کوکی"""
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    # استفاده از فایل کوکی در صورت وجود
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # پیدا کردن فایلی که دانلود شده است
        files = glob.glob(f"downloads/{info['id']}.*")
        return files[0] if files else None

@bot.on_message(filters.command("start"))
def start(client, message):
    message.reply_text("✅ ربات دانلودر اینستاگرام فعال است.\n\nلینک پست، ریلز، استوری یا آیدی (مانند @username) را بفرستید.")

@bot.on_message(filters.text & ~filters.command("start"))
def downloader(client, message):
    text = message.text.strip()
    
    # تشخیص لینک یا آیدی
    if text.startswith("@"):
        url = f"https://www.instagram.com/{text.replace('@', '')}/"
    elif "instagram.com" in text:
        url = text
    else:
        message.reply_text("❌ فرمت ورودی اشتباه است. لطفاً لینک یا آیدی معتبر بفرستید.")
        return

    msg = message.reply_text("⏳ در حال پردازش و دانلود...")
    
    try:
        file_path = download_media(url)
        
        if file_path:
            # تشخیص نوع فایل و ارسال
            if file_path.endswith(('.mp4', '.mov')):
                client.send_video(message.chat.id, video=file_path, caption="📥 دانلود شده توسط ربات")
            else:
                client.send_photo(message.chat.id, photo=file_path, caption="📥 دانلود شده توسط ربات")
            
            # پاکسازی فایل از سرور
            os.remove(file_path)
            msg.delete()
        else:
            msg.edit_text("❌ محتوا یافت نشد. ممکن است اکانت خصوصی باشد یا لینک معتبر نباشد.")
            
    except Exception as e:
        msg.edit_text(f"⚠️ خطایی رخ داد: {str(e)}")

if __name__ == "__main__":
    # اجرای همزمان وب‌سرور و ربات
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.run()
