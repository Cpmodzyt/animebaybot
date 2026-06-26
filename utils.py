import asyncio
import json
import os
import random
import string
import time
from pyrogram.raw import functions, types as raw_types
from config import STORAGE_CHANNEL, RANDOM_STICKER_IDS


def generate_code(length=10):
    return "".join(
        random.choices(
            string.ascii_letters + string.digits,
            k=length
        )
    )


async def delete_messages_later(client, chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
    except Exception as e:
        print(f"Auto-delete error: {e}")


async def resolve_storage_channel(app):
    raw_channel_id = abs(STORAGE_CHANNEL) - 1000000000000
    try:
        result = await app.invoke(
            functions.channels.GetChannels(
                id=[raw_types.InputChannel(
                    channel_id=raw_channel_id,
                    access_hash=0
                )]
            )
        )
        print(f"Storage channel resolved: {result.chats[0].title}")
    except Exception as e:
        print(f"Could not auto-resolve storage channel: {e}")
        print("Waiting for a channel post to cache the peer automatically...")

def get_random_sticker_id():
    return random.choice(RANDOM_STICKER_IDS)

async def load_pending_reminders(app, cursor, fire_reminder):
    now_ts = int(time.time())
    cursor.execute("SELECT id, user_id, chat_id, text, remind_at FROM reminders WHERE remind_at>?", (now_ts,))
    rows = cursor.fetchall()
    for rid, user_id, chat_id, text, remind_at in rows:
        delay = remind_at - now_ts
        asyncio.create_task(fire_reminder(app, rid, chat_id, user_id, text, delay))
    if rows:
        print(f"Loaded {len(rows)} pending reminder(s).")
