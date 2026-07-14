import os
from pyrogram import Client, filters

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start"))
def start(client, message):
    message.reply_text("✅ ربات با موفقیت روی Render اجرا شده است!")

@app.on_message(filters.text)
def echo(client, message):
    message.reply_text(f"شما گفتید:\n{message.text}")

print("Bot Started...")
app.run()
