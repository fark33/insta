import os
import re
import glob
import traceback
import threading
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from fastapi import FastAPI
import uvicorn

# ---------------------------------------------------------------------------
# تنظیمات محیطی
# ---------------------------------------------------------------------------
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.environ["BOT_USERNAME"]

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

INSTAGRAM_URL_RE = re.compile(r"(instagram\.com|instagr\.am)/", re.IGNORECASE)
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# وب‌سرور سلامت (برای هاست‌هایی مثل Railway/Render)
# ---------------------------------------------------------------------------
app_web = FastAPI()


@app_web.get("/")
def home():
    return {"status": "Bot is running"}


def run_web():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app_web, host="0.0.0.0", port=port)


bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# ---------------------------------------------------------------------------
# دانلود (تک‌مدیا یا آلبوم)
# ---------------------------------------------------------------------------
def download_media(url):
    """
    برمی‌گرداند: (files: list[str], error: str | None)
    files لیستی از مسیر فایل‌های واقعیِ دانلودشده روی دیسک است
    (برای پست تکی یک آیتم، برای آلبوم چند آیتم).
    """
    ydl_opts = {
        "format": "best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s_%(autonumber)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,   # اجازه بده آلبوم‌ها (carousel) هم پردازش شوند
        "http_headers": {"User-Agent": USER_AGENT},
    }
    if os.path.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        err = str(e).lower()
        if "login" in err or "private" in err:
            return [], "🔒 این اکانت خصوصی است یا برای دیدن این پست نیاز به کوکی لاگین دارید."
        if "rate-limit" in err or "429" in err:
            return [], "⏳ اینستاگرام موقتاً محدودمان کرده. چند دقیقه دیگر دوباره امتحان کنید."
        if "unsupported url" in err:
            return [], "❌ این لینک پشتیبانی نمی‌شود."
        print("DownloadError:", e)
        return [], f"⚠️ خطای دانلود از اینستاگرام (احتمالاً نیاز به بروزرسانی yt-dlp یا کوکی جدید دارید)."
    except Exception:
        traceback.print_exc()
        return [], "⚠️ خطای غیرمنتظره در دانلود رخ داد."

    if not info:
        return [], "❌ محتوایی یافت نشد."

    entries = info["entries"] if info.get("_type") == "playlist" else [info]

    files = []
    for entry in entries:
        if not entry:
            continue
        fp = None
        # روش قابل‌اعتماد: مسیر واقعی را از خروجی yt-dlp بگیر
        rd = entry.get("requested_downloads")
        if rd:
            fp = rd[0].get("filepath") or rd[0].get("_filename")
        # روش پشتیبان: prepare_filename
        if not fp or not os.path.exists(fp):
            try:
                fp = ydl.prepare_filename(entry)
            except Exception:
                fp = None
        if fp and os.path.exists(fp):
            files.append(fp)

    if not files:
        return [], "❌ فایلی برای دانلود پیدا نشد (شاید پست حذف شده یا خصوصی است)."

    return files, None


# ---------------------------------------------------------------------------
# هندلرها
# ---------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
def start(client, message):
    message.reply_text("✅ ربات آماده است. لینک اینستاگرام یا آیدی (مثلاً @username) را بفرستید.")


@bot.on_message(filters.text & ~filters.command("start"))
def downloader(client, message):
    text = message.text.strip()

    if text.startswith("@"):
        url = f"https://www.instagram.com/{text.replace('@', '')}/"
    elif INSTAGRAM_URL_RE.search(text):
        url = text
    else:
        message.reply_text("❌ لطفاً لینک یا آیدی معتبر اینستاگرام بفرستید.")
        return

    msg = message.reply_text("⏳ در حال پردازش و دانلود...")

    files, error = download_media(url)

    if error:
        msg.edit_text(error)
        return

    caption = f"📥 دانلود شده توسط ربات\n\n✅ {BOT_USERNAME}"

    try:
        if len(files) == 1:
            fp = files[0]
            if fp.lower().endswith(VIDEO_EXTS):
                client.send_video(message.chat.id, video=fp, caption=caption)
            else:
                client.send_photo(message.chat.id, photo=fp, caption=caption)
        else:
            # تلگرام حداقل ۲ آیتم برای media group لازم دارد؛ اینجا چون
            # len(files) > 1 است این شرط همیشه برقرار است.
            media_group = []
            for i, fp in enumerate(files[:10]):  # سقف تلگرام: ۱۰ آیتم در هر گروه
                cap = caption if i == 0 else None
                if fp.lower().endswith(VIDEO_EXTS):
                    media_group.append(InputMediaVideo(fp, caption=cap))
                else:
                    media_group.append(InputMediaPhoto(fp, caption=cap))
            client.send_media_group(message.chat.id, media=media_group)

        msg.delete()
    except Exception as e:
        traceback.print_exc()
        msg.edit_text(f"⚠️ خطایی در ارسال فایل رخ داد: {str(e)}")
    finally:
        for fp in files:
            try:
                os.remove(fp)
            except OSError:
                pass


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.run()
