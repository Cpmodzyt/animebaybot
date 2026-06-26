import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from bot import app
from auth import is_admin
from config import ADMIN_ID
from database import cursor, db


@app.on_message(filters.command("addauth"))
async def addauth(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    if len(message.command) < 2:
        await message.reply_text("Usage:\n`/addauth user_id`")
        return
    try:
        target_id = int(message.command[1])
    except Exception:
        await message.reply_text("Invalid user ID.")
        return

    cursor.execute("INSERT OR IGNORE INTO auth_users VALUES (?)", (target_id,))
    db.commit()
    await message.reply_text(f"✅ User `{target_id}` authorized.")


@app.on_message(filters.command("removeauth"))
async def removeauth(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    if len(message.command) < 2:
        await message.reply_text("Usage:\n`/removeauth user_id`")
        return
    try:
        target_id = int(message.command[1])
    except Exception:
        await message.reply_text("Invalid user ID.")
        return

    cursor.execute("DELETE FROM auth_users WHERE user_id=?", (target_id,))
    db.commit()
    await message.reply_text(f"✅ User `{target_id}` removed from authorized list.")


@app.on_message(filters.command("authlist"))
async def authlist(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT user_id FROM auth_users")
    rows = cursor.fetchall()
    if not rows:
        await message.reply_text("No authorized users yet.")
        return
    ids = "\n".join(f"• `{r[0]}`" for r in rows)
    await message.reply_text(f"**Authorized users:**\n{ids}")


@app.on_message(filters.command("addadmin"))
async def addadmin(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    if len(message.command) < 2:
        await message.reply_text("Usage:\n`/addadmin user_id`")
        return
    try:
        target_id = int(message.command[1])
    except Exception:
        await message.reply_text("Invalid user ID.")
        return
    cursor.execute("INSERT OR IGNORE INTO admins VALUES (?)", (target_id,))
    db.commit()
    await message.reply_text(f"✅ User `{target_id}` is now an admin.")


@app.on_message(filters.command("removeadmin"))
async def removeadmin(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    if len(message.command) < 2:
        await message.reply_text("Usage:\n`/removeadmin user_id`")
        return
    try:
        target_id = int(message.command[1])
    except Exception:
        await message.reply_text("Invalid user ID.")
        return
    if target_id == ADMIN_ID:
        await message.reply_text("❌ Cannot remove the super admin.")
        return
    cursor.execute("DELETE FROM admins WHERE user_id=?", (target_id,))
    db.commit()
    await message.reply_text(f"✅ User `{target_id}` removed from admins.")


@app.on_message(filters.command("adminlist"))
async def adminlist(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    lines = [f"• `{ADMIN_ID}` _(super admin)_"]
    lines += [f"• `{r[0]}`" for r in rows]
    await message.reply_text(f"**Admins ({len(lines)} total):**\n" + "\n".join(lines))


@app.on_message(filters.command("broadcast"))
async def broadcast(client, message):
    if message.from_user.id != ADMIN_ID:
        return

    reply = message.reply_to_message
    if not reply and len(message.command) < 2:
        await message.reply_text(
            "Usage:\n"
            "• Reply to any message with `/broadcast` to forward it\n"
            "• Or: `/broadcast Your announcement text here`"
        )
        return

    cursor.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]
    if not user_ids:
        await message.reply_text("📭 No users to broadcast to yet.")
        return

    status_msg = await message.reply_text(f"📡 Broadcasting to {len(user_ids)} users...")
    sent = 0
    failed = 0

    for uid in user_ids:
        try:
            if reply:
                await reply.copy(uid)
            else:
                text = " ".join(message.command[1:])
                await client.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                if reply:
                    await reply.copy(uid)
                else:
                    await client.send_message(uid, " ".join(message.command[1:]))
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ Broadcast complete!\n\n"
        f"• Delivered: **{sent}**\n"
        f"• Failed: **{failed}**"
    )


@app.on_message(filters.command("stats"))
async def stats(client, message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM batches")
    total_batches = cursor.fetchone()[0]

    cursor.execute("SELECT name FROM batches ORDER BY rowid DESC LIMIT 1")
    newest = cursor.fetchone()
    newest_name = newest[0] if newest and newest[0] else "_(unnamed)_"

    cursor.execute("SELECT name, fetch_count FROM batches ORDER BY fetch_count DESC LIMIT 1")
    top_row = cursor.fetchone()
    top_batch = f"**{top_row[0] or '_(unnamed)_'}** ({top_row[1]} fetches)" if top_row and top_row[1] else "_No fetches recorded yet_"

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM auth_users")
    total_auth = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM requests")
    total_requests = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM requests WHERE status='pending'")
    pending_requests = cursor.fetchone()[0]

    await message.reply_text(
        "📊 **Bot Stats**\n\n"
        f"📦 Total batches: **{total_batches}**\n"
        f"🆕 Newest batch: **{newest_name}**\n"
        f"🔥 Most fetched: {top_batch}\n\n"
        f"👥 Total users: **{total_users}**\n"
        f"🔑 Authorized users: **{total_auth}**\n\n"
        f"📥 Total requests: **{total_requests}**\n"
        f"⏳ Pending requests: **{pending_requests}**"
    )
