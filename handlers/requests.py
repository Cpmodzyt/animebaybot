from datetime import datetime
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import app
from auth import is_admin
from config import ADMIN_ID, SL_TZ
from database import cursor, db

PAGE_SIZE = 8


def _requests_text_and_buttons(status_filter, offset):
    if status_filter == "all":
        cursor.execute(
            "SELECT id, title, requester_id, status, acted_name, created_at "
            "FROM requests ORDER BY id DESC LIMIT ? OFFSET ?",
            (PAGE_SIZE + 1, offset)
        )
    else:
        cursor.execute(
            "SELECT id, title, requester_id, status, acted_name, created_at "
            "FROM requests WHERE status=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (status_filter, PAGE_SIZE + 1, offset)
        )
    rows = cursor.fetchall()
    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]

    if not rows:
        text = "📭 No requests found."
    else:
        icons = {"pending": "⏳", "noted": "✅", "na": "❌"}
        lines = []
        for req_id, title, req_uid, sts, acted, created_at in rows:
            icon = icons.get(sts, "❓")
            ts = datetime.fromtimestamp(created_at, tz=SL_TZ).strftime("%d %b %H:%M") if created_at else "?"
            actor = f" · by {acted}" if acted else ""
            lines.append(f"{icon} `#{req_id}` **{title}**\n    👤 `{req_uid}` · {ts}{actor}")
        label = status_filter.upper() if status_filter != "all" else "ALL"
        text = f"📥 **Requests — {label}** (page {offset // PAGE_SIZE + 1})\n\n" + "\n\n".join(lines)

    filters_row = [
        InlineKeyboardButton("📋 All",     callback_data="reqlist_all_0"),
        InlineKeyboardButton("⏳ Pending", callback_data="reqlist_pending_0"),
        InlineKeyboardButton("✅ Noted",   callback_data="reqlist_noted_0"),
        InlineKeyboardButton("❌ N/A",     callback_data="reqlist_na_0"),
    ]
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"reqlist_{status_filter}_{offset - PAGE_SIZE}"))
    if has_next:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"reqlist_{status_filter}_{offset + PAGE_SIZE}"))

    buttons = [filters_row]
    if nav_row:
        buttons.append(nav_row)
    return text, InlineKeyboardMarkup(buttons)


@app.on_message(filters.command("requests"))
async def requests_list(client, message):
    if not is_admin(message.from_user.id):
        return
    text, markup = _requests_text_and_buttons("pending", 0)
    await message.reply_text(text, reply_markup=markup)


@app.on_callback_query(filters.regex(r"^reqlist_(all|pending|noted|na)_(\d+)$"))
async def requests_list_callback(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Admins only.", show_alert=True)
        return
    sf = callback_query.matches[0].group(1)
    offset = int(callback_query.matches[0].group(2))
    text, markup = _requests_text_and_buttons(sf, offset)
    await callback_query.message.edit_text(text, reply_markup=markup)
    await callback_query.answer()


@app.on_message(filters.command("request"))
async def request_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text(
            "Usage: `/request <anime title>`\n"
            "Example: `/request Demon Slayer Season 4`"
        )
        return

    title = " ".join(message.command[1:]).strip()
    user = message.from_user
    name_display = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
    username_part = f" (@{user.username})" if user.username else ""
    chat_name = getattr(message.chat, "title", None) or "Private DM"

    cursor.execute(
        "INSERT INTO requests(requester_id, title, status, created_at) VALUES(?,?,?,?)",
        (user.id, title, "pending", int(__import__("time").time()))
    )
    db.commit()
    req_id = cursor.lastrowid

    notif_text = (
        f"📥 **New Anime Request** `#{req_id}`\n\n"
        f"🎬 **Title:** {title}\n"
        f"👤 **From:** {name_display}{username_part}\n"
        f"🆔 **User ID:** `{user.id}`\n"
        f"💬 **Chat:** {chat_name}"
    )
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Noted", callback_data=f"reqack_noted_{req_id}"),
        InlineKeyboardButton("❌ Not Available", callback_data=f"reqack_na_{req_id}"),
    ]])

    cursor.execute("SELECT user_id FROM admins")
    all_admin_ids = list({ADMIN_ID} | {r[0] for r in cursor.fetchall()})
    for aid in all_admin_ids:
        try:
            sent = await client.send_message(aid, notif_text, reply_markup=buttons)
            cursor.execute(
                "INSERT OR IGNORE INTO request_msgs(request_id, admin_id, message_id) VALUES(?,?,?)",
                (req_id, aid, sent.id)
            )
            db.commit()
        except Exception as e:
            print(f"Could not notify admin {aid}: {e}")

    await message.reply_sticker(get_random_sticker_id())
    await message.reply_text(
        f"✅ Your request for **{title}** has been submitted!\n"
        "We'll try to add it soon. 🙏"
    )


@app.on_callback_query(filters.regex(r"^reqack_(noted|na)_(\d+)$"))
async def request_ack_callback(client, callback_query):
    action = callback_query.matches[0].group(1)
    req_id = int(callback_query.matches[0].group(2))

    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Admins only.", show_alert=True)
        return

    cursor.execute("SELECT status, acted_name, requester_id, title FROM requests WHERE id=?", (req_id,))
    row = cursor.fetchone()
    if not row:
        await callback_query.answer("Request not found.", show_alert=True)
        return

    status, acted_name, requester_id, title = row
    if status != "pending":
        verdict = "✅ Noted" if status == "noted" else "❌ Not Available"
        await callback_query.answer(f"Already handled by {acted_name} — {verdict}", show_alert=True)
        return

    admin_name = callback_query.from_user.first_name
    cursor.execute(
        "UPDATE requests SET status=?, acted_by=?, acted_name=? WHERE id=?",
        (action, callback_query.from_user.id, admin_name, req_id)
    )
    db.commit()

    if action == "noted":
        label = "✅ Noted"
        user_msg = f"✅ Your request for **{title}** has been **noted**! We'll add it soon. 🙏"
    else:
        label = "❌ Not Available"
        user_msg = f"❌ Sorry, **{title}** is **not available** at this time."

    await callback_query.answer(f"{label} — marked!", show_alert=False)

    cursor.execute("SELECT admin_id, message_id FROM request_msgs WHERE request_id=?", (req_id,))
    all_copies = cursor.fetchall()
    updated_text = (
        f"📥 **Anime Request** `#{req_id}` — {label}\n\n"
        f"🎬 **Title:** {title}\n"
        f"👤 **Requester ID:** `{requester_id}`\n\n"
        f"_Handled by {admin_name}_"
    )
    for admin_id, msg_id in all_copies:
        try:
            await client.edit_message_text(chat_id=admin_id, message_id=msg_id, text=updated_text, reply_markup=None)
        except Exception:
            pass

    try:
        await client.send_message(requester_id, user_msg)
    except Exception:
        pass
