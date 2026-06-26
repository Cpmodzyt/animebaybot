import asyncio
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN
from utils import resolve_storage_channel, load_pending_reminders
from database import cursor

app = Client(
    "batch_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

import handlers.batches
import handlers.admin
import handlers.requests
import handlers.anime
import handlers.watchlist
import handlers.reminders

async def main():
    from pyrogram import idle

    await app.start()
    try:
        await resolve_storage_channel(app)
        me = await app.get_me()
        print(f"Bot connected as @{me.username} ({me.id})")
        await load_pending_reminders(app, cursor, handlers.reminders.fire_reminder)
        print("Bot Running...")
        await idle()
    finally:
        await app.stop()

if __name__ == "__main__":
    app.run(main())
