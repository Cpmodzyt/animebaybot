from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import app
from auth import is_auth
from database import cursor, db


def watchlist_keyboard(user_id):
    cursor.execute("SELECT id, title, done FROM watchlist WHERE user_id=? ORDER BY done, id", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return None, rows

    buttons = []
    for wid, title, done in rows:
        status = "✅" if done else "⬜"
        short = title[:28] + "…" if len(title) > 28 else title
        buttons.append([
            InlineKeyboardButton(f"{status} {short}", callback_data=f"wl_toggle_{wid}"),
            InlineKeyboardButton("🗑", callback_data=f"wl_del_{wid}"),
        ])
    buttons.append([
        InlineKeyboardButton("🗑 Clear Completed", callback_data="wl_clear_done"),
        InlineKeyboardButton("❌ Close", callback_data="close_menu"),
    ])
    return InlineKeyboardMarkup(buttons), rows


@app.on_message(filters.command("watch") & is_auth)
async def watch_add(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/watch <anime title>`\nExample: `/watch Attack on Titan`")
        return
    title = " ".join(message.command[1:]).strip()
    cursor.execute("INSERT INTO watchlist(user_id, title) VALUES(?,?)", (message.from_user.id, title))
    db.commit()
    await message.reply_text(f"➕ **{title}** added to your watchlist!")


@app.on_message(filters.command("watchlist") & is_auth)
async def show_watchlist(client, message):
    markup, rows = watchlist_keyboard(message.from_user.id)
    if not rows:
        await message.reply_text("📭 Your watchlist is empty. Add titles with `/watch <name>`.")
        return
    total = len(rows)
    done = sum(1 for _, _, d in rows if d)
    await message.reply_text(
        f"📋 **Your Watchlist** — {done}/{total} watched:",
        reply_markup=markup
    )


@app.on_callback_query(filters.regex(r"^wl_toggle_(\d+)$") & is_auth)
async def wl_toggle(client, callback_query):
    wid = int(callback_query.matches[0].group(1))
    cursor.execute("SELECT done, user_id FROM watchlist WHERE id=?", (wid,))
    row = cursor.fetchone()
    if not row or row[1] != callback_query.from_user.id:
        await callback_query.answer("Not found.", show_alert=True)
        return
    new_done = 0 if row[0] else 1
    cursor.execute("UPDATE watchlist SET done=? WHERE id=?", (new_done, wid))
    db.commit()
    markup, rows = watchlist_keyboard(callback_query.from_user.id)
    total = len(rows)
    done = sum(1 for _, _, d in rows if d)
    await callback_query.edit_message_text(
        f"📋 **Your Watchlist** — {done}/{total} watched:",
        reply_markup=markup
    )
    await callback_query.answer("✅ Marked!" if new_done else "↩️ Unmarked!")


@app.on_callback_query(filters.regex(r"^wl_del_(\d+)$") & is_auth)
async def wl_delete(client, callback_query):
    wid = int(callback_query.matches[0].group(1))
    cursor.execute("SELECT user_id FROM watchlist WHERE id=?", (wid,))
    row = cursor.fetchone()
    if not row or row[0] != callback_query.from_user.id:
        await callback_query.answer("Not found.", show_alert=True)
        return
    cursor.execute("DELETE FROM watchlist WHERE id=?", (wid,))
    db.commit()
    markup, rows = watchlist_keyboard(callback_query.from_user.id)
    await callback_query.answer("🗑 Removed!")
    if not rows:
        await callback_query.edit_message_text("📭 Your watchlist is empty. Add titles with `/watch <name>`.")
        return
    total = len(rows)
    done = sum(1 for _, _, d in rows if d)
    await callback_query.edit_message_text(
        f"📋 **Your Watchlist** — {done}/{total} watched:",
        reply_markup=markup
    )


@app.on_callback_query(filters.regex(r"^wl_clear_done$") & is_auth)
async def wl_clear_done(client, callback_query):
    user_id = callback_query.from_user.id
    cursor.execute("DELETE FROM watchlist WHERE user_id=? AND done=1", (user_id,))
    db.commit()
    await callback_query.answer("🗑 Completed entries cleared!")
    markup, rows = watchlist_keyboard(user_id)
    if not rows:
        await callback_query.edit_message_text("📭 Your watchlist is empty. Add titles with `/watch <name>`.")
        return
    total = len(rows)
    done = sum(1 for _, _, d in rows if d)
    await callback_query.edit_message_text(
        f"📋 **Your Watchlist** — {done}/{total} watched:",
        reply_markup=markup
    )
