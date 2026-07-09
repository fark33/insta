"""
ربات تلگرام دانلودر اینستاگرام (Pyrogram) - نسخه‌ی Webhook
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

import os
import re
import glob
import logging
import tempfile
from pathlib import Path

import instaloader
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.webhook import Webhook

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ تنظیمات ============
API_ID = int(os.environ.get("API_ID", "3335796"))
API_HASH = os.environ.get("API_HASH", "138b992a0e672e8346d8439c3f42ea78")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7136875110:AAGr1EREy_qPMgxVbuE4B0cHGVcwWudOrus")
IG_USERNAME = os.environ.get("IG_USERNAME", "")
IG_PASSWORD = os.environ.get("IG_PASSWORD", "")
HEALTH_PORT = int(os.environ.get("PORT", "8000"))

# URL سرویس خود را اینجا تنظیم کنید (مطابق با Render)
RENDER_URL = os.environ.get("RENDER_URL", "https://insta-m37r.onrender.com")
# ==================================

INSTA_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/"
    r"(?:(?P<type>p|reel|reels|tv)/(?P<shortcode>[\w-]+)"
    r"|stories/(?P<story_user>[\w.]+))"
)

loader = instaloader.Instaloader(
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    post_metadata_txt_pattern="",
    quiet=True,
)

_logged_in = False

def ensure_login():
    global _logged_in
    if IG_USERNAME and IG_PASSWORD and not _logged_in:
        try:
            loader.login(IG_USERNAME, IG_PASSWORD)
            _logged_in = True
            logger.info("لاگین اینستاگرام موفق بود.")
        except Exception as e:
            logger.warning(f"لاگین ناموفق: {e}")

def download_post(shortcode: str, target_dir: str):
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    loader.download_post(post, target=target_dir)
    return collect_media_files(target_dir)

def download_stories(username: str, target_dir: str):
    profile = instaloader.Profile.from_username(loader.context, username)
    for story in loader.get_stories(userids=[profile.userid]):
        for item in story.get_items():
            loader.download_storyitem(item, target=target_dir)
    return collect_media_files(target_dir)

def collect_media_files(target_dir: str):
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.mp4"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(target_dir, p)))
    return sorted(files)

app = Client(
    "ig_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    logger.info(f"دریافت پیام /start از {message.from_user.id}")
    await message.reply_text(
        "سلام 👋\n"
        "لینک پست، ریلز، عکس یا استوری اینستاگرام رو برام بفرست تا دانلودش کنم و برات بفرستم."
    )

@app.on_message(filters.text & ~filters.command(["start"]))
async def link_handler(client: Client, message: Message):
    logger.info(f"دریافت پیام متنی از {message.from_user.id}")
    text = message.text or ""
    match = INSTA_URL_RE.search(text)
    if not match:
        await message.reply_text("لینک معتبر اینستاگرام پیدا نشد.")
        return

    status_msg = await message.reply_text("در حال دانلود، لطفاً صبر کن... ⏳")
    me = await client.get_me()
    caption = f"@{me.username}"

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            loop = asyncio.get_event_loop()
            if match.group("shortcode"):
                files = await loop.run_in_executor(
                    None, download_post, match.group("shortcode"), tmpdir
                )
            else:
                ensure_login()
                files = await loop.run_in_executor(
                    None, download_stories, match.group("story_user"), tmpdir
                )

            if not files:
                await status_msg.edit_text("چیزی برای دانلود پیدا نشد.")
                return

            for f in files:
                await send_media(client, message, f, caption)
            await status_msg.delete()

        except instaloader.exceptions.LoginRequiredException:
            await status_msg.edit_text("نیاز به لاگین دارد.")
        except Exception as e:
            logger.exception("خطا در دانلود")
            await status_msg.edit_text(f"خطا: {e}")

async def send_media(client: Client, message: Message, filepath: str, caption: str):
    ext = Path(filepath).suffix.lower()
    if ext == ".mp4":
        await client.send_video(message.chat.id, filepath, caption=caption)
    else:
        await client.send_photo(message.chat.id, filepath, caption=caption)

# ============ وب‌سرور health check و Webhook ============
async def health(request):
    return web.Response(text="OK")

async def webhook_handler(request):
    """دریافت آپدیت از تلگرام و ارسال به Pyrogram"""
    data = await request.json()
    await app.process_update(data)
    return web.Response(text="OK")

async def start_web_server():
    webapp = web.Application()
    webapp.router.add_get("/", health)
    webapp.router.add_get("/health", health)
    webapp.router.add_post("/webhook", webhook_handler)  # مسیر دریافت آپدیت‌ها
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
    await site.start()
    logger.info(f"وب‌سرور روی پورت {HEALTH_PORT} بالا اومد.")

async def main():
    if not (API_ID and API_HASH and BOT_TOKEN):
        raise SystemExit("لطفاً API_ID، API_HASH و BOT_TOKEN رو تنظیم کن.")

    await app.start()
    logger.info("ربات تلگرام استارت شد.")

    # تنظیم Webhook روی URL سرویس
    webhook_url = f"{https://insta-m37r.onrender.com/}/webhook"
    await app.set_webhook(webhook_url)
    logger.info(f"وب‌هوک روی {webhook_url} تنظیم شد.")

    # اجرای وب‌سرور (که health check و webhook رو هندل کنه)
    await start_web_server()

    # منتظر می‌مانیم تا برنامه متوقف شود (در اینجا نیازی به idle نیست، چون webhook کار می‌کند)
    try:
        await asyncio.Event().wait()  # تا ابد منتظر می‌ماند
    except KeyboardInterrupt:
        pass
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
