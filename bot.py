import os
import asyncio
import yt_dlp
import requests

from pyrogram import Client, filters
from pyrogram.enums import ParseMode

# ================= تنظیمات (قابلیت دریافت از Environment Variables برای امنیت بیشتر) =================

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
BOT_ID = os.getenv("BOT_ID", "@YOUR_BOT_ID")
API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "API_HASH")


app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ================= جستجوی آهنگ (iTunes API) =================

async def search_song(query):
    def _search():
        try:
            data = requests.get(
                "https://itunes.apple.com/search",
                params={
                    "term": query,
                    "media": "music",
                    "limit": 1
                },
                timeout=5
            ).json()

            if data.get("resultCount"):
                item = data["results"][0]
                return (
                    item.get("trackName", "")
                    + " - "
                    + item.get("artistName", "")
                )
        except Exception:
            pass
        return query

    return await asyncio.to_thread(_search)


# ================= دانلود هوشمند و ضد بلاک یوتیوب =================

async def download_music(query, user_id):
    output_filename = f"music_{user_id}.m4a"

    def _download():
        try:
            if os.path.exists(output_filename):
                os.remove(output_filename)

            # تنظیمات پیشرفته برای فریب دادن سیستم ضدبات یوتیوب
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'music_{user_id}.%(ext)s',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                # تبدیل و استخراج خودکار صدا به فرمت m4a با کمک ffmpeg داخلی سیستم
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }],
                # ارسال هدرها و کلاینت‌های شبیه‌ساز موبایل/اندروید برای دور زدن ارور Sign-in
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web', 'mweb', 'android']
                    }
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # جستجو و دانلود اولین موزیک یافت شده
                ydl.extract_info(f"ytsearch1:{query}", download=True)

            # بررسی نهایی برای اطمینان از ساخته شدن فایل صوتی m4a
            if os.path.exists(output_filename):
                return output_filename

        except Exception as e:
            print(f"❌ Error during download: {e}")

        return None

    return await asyncio.to_thread(_download)


# ================= START =================

@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
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
        disable_web_page_preview=True
    )
    
    # متوقف کردن انتشار هندلرها برای جلوگیری از تداخل با هندلر دریافت آهنگ
    message.stop_propagation()


# ================= دریافت آهنگ =================

@app.on_message(filters.private & filters.text)
async def music(client, message):
    query = message.text.strip()
    user_id = message.from_user.id

    if query.startswith("/") or query.lower() in ["start", "سلام", "hi", "hello"]:
        return

    status = await message.reply(
        "🔎 در حال پیدا کردن آهنگ..."
    )

    song = await search_song(query)

    await status.edit(
        "⏳ در حال دانلود..."
    )

    file = await download_music(song, user_id)

    if file:
        # ارسال فایل صوتی و ست کردن تگ‌ها به صورت آنی توسط خود تلگرام
        await message.reply_audio(
            audio=file,
            performer="IR_BOTZ™", # نمایش قطعی و بدون پردازش اضافی نام خواننده
            title=song,           # نام آهنگ
            caption=f"""
🎵 {song}

✅ {BOT_ID}
"""
        )

        # پاکسازی و حذف فایل از روی سرور جهت جلوگیری از پر شدن فضا
        try:
            os.remove(file)
        except Exception:
            pass

        await status.delete()

    else:
        await status.edit(
            "❌ متاسفانه خطایی در دانلود پیش آمد. لطفاً دوباره تلاش کنید."
        )


# ================= اجرای پروژه =================

if __name__ == "__main__":
    print("✅ Music Bot is running successfully!")
    app.run()
