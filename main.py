import os
import threading
from pyrogram import Client, filters
from fastapi import FastAPI
import uvicorn

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app_web = FastAPI()

@app_web.get("/")
def home():
    return {"status": "Bot is running"}

def run_web():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app_web, host="0.0.0.0", port=port)

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.command("start"))
def start(client, message):
    message.reply_text("✅ ربات فعال است")

@bot.on_message(filters.text)
def echo(client, message):
    message.reply_text(f"گفتی: {message.text}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.run()
