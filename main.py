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

@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply_text("👋 سلام!\nنام آهنگ مورد نظرت را بنویس تا دانلود کنم.")


app.run()
