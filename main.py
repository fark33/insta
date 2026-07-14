import os
import glob
import threading
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from fastapi import FastAPI
import uvicorn

# --- تنظیمات ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.environ.get("BOT_USERNAME", "@YourBot")

# ایجاد پوشه downloads
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
        'outtmpl': 'downloads/%(id)s_%(index)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            entries = info.get('entries', [info])
            downloaded_files = []
            for entry in entries:
                files = glob.glob(f"downloads/{entry['id']}*")
                downloaded_files.extend(files)
            return downloaded_files
    except Exception as e:
        print(f"Error: {e}")
        return []

def chunked_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

@bot.on_message(filters.command("start"))
def start(client, message):
    user_name = message.from_user.first_name
    text = (
        f"**👋 سلام {user_name} عزیز خوش آمدید❤️**\n\n"
        "**🔮 من ربات کاربردی اینستاگرام دانلودر هستم.**\n\n"
        "**هم اکنون یک لینک برایم ارسال کنید.** \n"
        "**تا براتون فایلشو بفرستم💗😍**\n\n"
        "**🖍️ سازنده ربات : [FﾑRSみɨの-BﾑŊの](https://t.me/farshidband)**"
    )
    message.reply_text(text, disable_web_page_preview=True)

@bot.on_message(filters.text & ~filters.command("start"))
def downloader(client, message):
    text = message.text.strip()
    
    # تشخیص نوع ورودی
    if text.startswith("@"):
        url = f"https://www.instagram.com/{text.replace('@', '')}/"
    elif "instagram.com" in text:
        url = text
    # بررسی اینکه آیا کاربر لینک فرستاده ولی اینستاگرامی نیست؟
    elif text.startswith("http") or "www." in text:
        message.reply_text("❌ من این لینک ها را پشتیبانی نمیکنم !!")
        return
    else:
        message.reply_text("❌ لینک یا آیدی معتبر نیست.")
        return

    msg = message.reply_text("⏳ در حال پردازش و دانلود...")
    file_paths = download_media(url)
    
    if not file_paths:
        msg.edit_text("❌ متأسفانه محتوا یافت نشد (یا اکانت خصوصی است).")
        return

    try:
        media_objects = []
        for path in file_paths:
            if path.endswith(('.mp4', '.mov')):
                media_objects.append(InputMediaVideo(path))
            else:
                media_objects.append(InputMediaPhoto(path))
        
        # ارسال تکی
        if len(media_objects) == 1:
            caption = f"📥 دانلود شد\n\n✅ {BOT_USERNAME}"
            if isinstance(media_objects[0], InputMediaVideo):
                client.send_video(message.chat.id, video=file_paths[0], caption=caption)
            else:
                client.send_photo(message.chat.id, photo=file_paths[0], caption=caption)
        
        # ارسال آلبومی
        else:
            for i, batch in enumerate(chunked_list(media_objects, 10)):
                caption = f"📥 دانلود شد (بخش {i+1})\n\n✅ {BOT_USERNAME}" if i == 0 else f"📥 ادامه دانلود (بخش {i+1})"
                client.send_media_group(message.chat.id, media=batch, caption=caption)
        
        # پاکسازی
        for path in file_paths:
            if os.path.exists(path):
                os.remove(path)
        msg.delete()
        
    except Exception as e:
        msg.edit_text(f"⚠️ خطایی در ارسال رخ داد: {str(e)}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.run()
