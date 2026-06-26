import asyncio
import time
from datetime import datetime
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import app
from auth import is_auth
from config import SL_TZ
from database import cursor, db


async def fire_reminder(client, reminder_id, chat_id, user_id, text, delay):
    await asyncio.sleep(delay)
    try:
        await client.send_message(chat_id, f"⏰ **Reminder!**\n\n{text}")
    except Exception as e:
        print(f"Reminder send error: {e}")
    cursor.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    db.commit()


@app.on_message(filters.command("remind") & is_auth)
async def remind_cmd(client, message):
    if len(message.command) < 4:
        await message.reply_text(
            "Usage: `/remind DD-MM-YYYY HH:MM Your message`\n"
            "Example: `/remind 25-12-2025 20:00 Watch Demon Slayer S4!`"
        )
        return

    date_str = message.command[1]
    time_str = message.command[2]
    text = " ".join(message.command[3:])

    try:
        naive_dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
        remind_dt = SL_TZ.localize(naive_dt)
    except Exception:
        await message.reply_text(
            "❌ Invalid format. Use:\n`/remind DD-MM-YYYY HH:MM Your message`\n"
            "Example: `/remind 25-12-2025 20:00 Watch Demon Slayer S4!`"
        )
        return

    remind_ts = int(remind_dt.timestamp())
    now_ts = int(time.time())
    delay = remind_ts - now_ts
    if delay <= 0:
        await message.reply_text("❌ That date/time is already in the past!")
        return

    cursor.execute(
        "INSERT INTO reminders(user_id, chat_id, text, remind_at) VALUES(?,?,?,?)",
        (message.from_user.id, message.chat.id, text, remind_ts)
    )
    db.commit()
    rid = cursor.lastrowid
    asyncio.create_task(fire_reminder(client, rid, message.chat.id, message.from_user.id, text, delay))

    friendly = remind_dt.strftime("%d %b %Y at %H:%M")
    await message.reply_text(
        f"✅ **Reminder set!**\n\n"
        f"📅 {friendly}\n"
        f"📝 {text}"
    )


@app.on_message(filters.command("reminders") & is_auth)
async def list_reminders(client, message):
    user_id = message.from_user.id
    now_ts = int(time.time())
    cursor.execute(
        "SELECT id, text, remind_at FROM reminders WHERE user_id=? AND remind_at>? ORDER BY remind_at",
        (user_id, now_ts)
    )
    rows = cursor.fetchall()
    if not rows:
        await message.reply_text("📭 You have no upcoming reminders.")
        return

    buttons = []
    for rid, text, remind_at in rows:
        dt = datetime.fromtimestamp(remind_at, tz=SL_TZ)
        label = dt.strftime("%d %b %H:%M") + " — " + (text[:25] + "…" if len(text) > 25 else text)
        buttons.append([InlineKeyboardButton(f"🗑 {label}", callback_data=f"rmcancel_{rid}")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_menu")])

    await message.reply_text(
        f"⏰ **Your Reminders** ({len(rows)} upcoming)\nTap one to cancel it:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query(filters.regex(r"^rmcancel_(\d+)$") & is_auth)
async def reminder_cancel(client, callback_query):
    rid = int(callback_query.matches[0].group(1))
    user_id = callback_query.from_user.id
    cursor.execute("SELECT user_id, text FROM reminders WHERE id=?", (rid,))
    row = cursor.fetchone()
    if not row or row[0] != user_id:
        await callback_query.answer("Reminder not found.", show_alert=True)
        return

    cursor.execute("DELETE FROM reminders WHERE id=?", (rid,))
    db.commit()
    await callback_query.answer("🗑 Reminder cancelled!")

    now_ts = int(time.time())
    cursor.execute(
        "SELECT id, text, remind_at FROM reminders WHERE user_id=? AND remind_at>? ORDER BY remind_at",
        (user_id, now_ts)
    )
    rows = cursor.fetchall()
    if not rows:
        await callback_query.edit_message_text("📭 You have no upcoming reminders.")
        return

    buttons = []
    for r_id, text, remind_at in rows:
        dt = datetime.fromtimestamp(remind_at, tz=SL_TZ)
        label = dt.strftime("%d %b %H:%M") + " — " + (text[:25] + "…" if len(text) > 25 else text)
        buttons.append([InlineKeyboardButton(f"🗑 {label}", callback_data=f"rmcancel_{r_id}")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_menu")])
    await callback_query.edit_message_text(
        f"⏰ **Your Reminders** ({len(rows)} upcoming)\nTap one to cancel it:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
