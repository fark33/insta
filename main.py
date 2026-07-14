import os
import glob
import threading
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from fastapi import FastAPI
import uvicorn

# --- تنظیمات محیطی ---
# در سرور/سیستم خود، این مقادیر را تنظیم کنید
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.environ.get("BOT_USERNAME", "@YourBot")

# ایجاد پوشه دانلود
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# وب‌سرور برای زنده نگه داشتن بات در سرورهای ابری
app_web = FastAPI()

@app_web.get("/")
def home():
    return {"status": "Bot is running"}

def run_web():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app_web, host="0.0.0.0", port=port)

# اتصال ربات
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# تابع دانلود
def download_media(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            entries = info.get('entries', [info])
            
            valid_files = []
            for entry in entries:
                # جستجوی فایل‌های دانلود شده مرتبط با این آیدی
                potential_files = glob.glob(f"downloads/{entry['id']}.*")
                for f in potential_files:
                    # فیلتر برای اطمینان از اینکه فایل مدیا است
                    if f.endswith(('.mp4', '.mov', '.jpg', '.jpeg', '.png', '.webp')):
                        valid_files.append(os.path.abspath(f))
            return valid_files
    except Exception as e:
        print(f"Download Error: {e}")
        return []

# تابع تقسیم لیست به دسته‌های ۱۰ تایی
def chunked_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# کامند استارت
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

# پردازش لینک‌ها
@bot.on_message(filters.text & ~filters.command("start"))
def downloader(client, message):
    text = message.text.strip()
    
    # تشخیص لینک و فیلتر کردن
    if text.startswith("@"):
        url = f"https://www.instagram.com/{text.replace('@', '')}/"
    elif "instagram.com" in text:
        url = text
    elif text.startswith("http") or "www." in text:
        message.reply_text("❌ من این لینک ها را پشتیبانی نمیکنم !!")
        return
    else:
        message.reply_text("❌ لینک یا آیدی معتبر نیست.")
        return

    msg = message.reply_text("⏳ در حال پردازش و دانلود...")
    
    # دانلود و دریافت لیست فایل‌ها
    file_paths = download_media(url)
    
    # بررسی نهایی سلامت فایل‌ها
    final_files = [f for f in file_paths if os.path.exists(f) and os.path.getsize(f) > 0]
    
    if not final_files:
        msg.edit_text("❌ متأسفانه محتوا یافت نشد (یا اکانت خصوصی است).")
        return

    try:
        media_objects = []
        for path in final_files:
            if path.endswith(('.mp4', '.mov')):
                media_objects.append(InputMediaVideo(path))
            else:
                media_objects.append(InputMediaPhoto(path))
        
        caption = f"📥 دانلود شد\n\n✅ {BOT_USERNAME}"

        # ارسال تکی
        if len(media_objects) == 1:
            if isinstance(media_objects[0], InputMediaVideo):
                client.send_video(message.chat.id, video=final_files[0], caption=caption)
            else:
                client.send_photo(message.chat.id, photo=final_files[0], caption=caption)
        
        # ارسال آلبومی (چندتایی)
        else:
            for i, batch in enumerate(chunked_list(media_objects, 10)):
                # تنظیم کپشن روی اولین آیتم هر دسته
                batch[0].caption = f"{caption} (بخش {i+1})" if len(media_objects) > 10 else caption
                client.send_media_group(message.chat.id, media=batch)
        
        # پاکسازی
        for path in final_files:
            if os.path.exists(path):
                os.remove(path)
        msg.delete()
        
    except Exception as e:
        msg.edit_text(f"⚠️ خطایی در ارسال رخ داد: {str(e)}")

if __name__ == "__main__":
    # اجرای همزمان وب‌سرور و ربات
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.run()
