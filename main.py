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
BOT_USERNAME = os.environ["BOT_USERNAME"] # اضافه شد

# ایجاد پوشه downloads اگر وجود ندارد
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
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            files = glob.glob(f"downloads/{info['id']}.*")
            return files[0] if files else None
        except Exception:
            return None

@bot.on_message(filters.command("start"))
def start(client, message):
    message.reply_text("✅ ربات آماده است. لینک اینستاگرام یا آیدی (مثلاً @username) را بفرستید.")

@bot.on_message(filters.text & ~filters.command("start"))
def downloader(client, message):
    text = message.text.strip()
    
    if text.startswith("@"):
        url = f"https://www.instagram.com/{text.replace('@', '')}/"
    elif "instagram.com" in text:
        url = text
    else:
        message.reply_text("❌ لطفاً لینک یا آیدی معتبر اینستاگرام بفرستید.")
        return

    msg = message.reply_text("⏳ در حال پردازش و دانلود...")
    
    file_path = download_media(url)
    
    if file_path:
        try:
            # استفاده از BOT_USERNAME در کپشن
            caption = f"📥 دانلود شده توسط ربات\n\n✅ {BOT_USERNAME}"
            
            if file_path.endswith(('.mp4', '.mov')):
                client.send_video(message.chat.id, video=file_path, caption=caption)
            else:
                client.send_photo(message.chat.id, photo=file_path, caption=caption)
            
            os.remove(file_path)
            msg.delete()
        except Exception as e:
            msg.edit_text(f"⚠️ خطایی در ارسال فایل رخ داد: {str(e)}")
    else:
        msg.edit_text("❌ متأسفانه نتوانستم محتوا را دانلود کنم.")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.run()
