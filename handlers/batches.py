import asyncio
import json
import re
import time
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import app
from auth import is_admin, is_authorized, is_auth
from config import BOT_USERNAME, ADMIN_ID, DELETE_AFTER, STORAGE_CHANNEL
from database import cursor, db
from utils import generate_code, delete_messages_later
from state import pending_deletes, staged_batches


@app.on_message(group=0)
async def debug_all_messages(client, message):
    user = message.from_user
    chat = message.chat
    text = message.text or message.caption or '<non-text>'
    print(
        f"DEBUG MSG chat={chat.type}:{chat.id} user={user.id if user else None} "
        f"username={user.username if user else None} cmd={message.command if message.text else None} text={text}"
    )


_AUTH_COMMANDS = [
    "search", "anime", "trending", "upcoming", "top", "random",
    "anime_genres", "watch", "watchlist", "remind", "reminders",
    "myfiles", "clear"
]


@app.on_message(filters.command(_AUTH_COMMANDS) & ~is_auth, group=1)
async def unauthorized_cmd_handler(client, message):
    await message.reply_text(
        "🔒 **Access Denied**\n\n"
        "This command requires an **SL Animebay Premium** plan.\n\n"
        "💎 **Get Premium Access:**\n"
        "Contact **@NexusExon** to purchase a plan and unlock:\n"
        "• Unlimited anime file access\n"
        "• Files saved permanently (no auto-delete)\n"
        "• Anime search, watchlist & reminders\n"
        "• Early access to new batches\n\n"
        "_Already a member? Ask an admin to activate your account._"
    )


def _extract_media_filename(message):
    if message.document:
        return message.document.file_name or message.document.mime_type or ""
    if message.video:
        return message.video.file_name or message.video.mime_type or ""
    if message.audio:
        return message.audio.file_name or message.audio.title or ""
    if message.animation:
        return message.animation.file_name or "animation"
    if message.photo:
        return message.caption or "photo"
    return message.caption or ""


def _parse_file_metadata(file_name):
    original = file_name or ""
    base = re.sub(r"\.(mkv|mp4|avi|webm|mov|mp3|m4a|mk3d|zip)$", "", original, flags=re.I)
    clean = re.sub(r"[_.]+", " ", base).strip()

    quality_match = re.search(
        r"\b(2160p|1080p|720p|480p|360p|4k|8k|BD|WEB[- ]DL|WEB|HEVC|x264|x265)\b",
        clean,
        re.I,
    )
    quality = quality_match.group(1).upper() if quality_match else None

    season = None
    episode = None
    special = False

    full_se_match = re.search(r"\b[Ss](\d{1,2})[^\w\d]{0,2}[Ee](\d{1,3})\b", clean)
    if full_se_match:
        season = int(full_se_match.group(1))
        episode = int(full_se_match.group(2))
    else:
        season_match = re.search(r"\bSeason\s*0*([1-9]\d?)\b", clean, re.I)
        episode_match = re.search(r"\b(?:Episode|EP|E)\s*0*([1-9]\d?)\b", clean, re.I)
        if season_match:
            season = int(season_match.group(1))
        if episode_match:
            episode = int(episode_match.group(1))

    if re.search(r"\b(?:SP|Special|OVA|Movie|Bonus|Extra)\b", clean, re.I):
        special = True

    title = clean
    removal_patterns = [
        r"\b[Ss](\d{1,2})[^\w\d]{0,2}[Ee](\d{1,3})\b",
        r"\bSeason\s*0*[1-9]\d?\b",
        r"\b(?:Episode|EP|E)\s*0*[1-9]\d?\b",
        r"\b(?:SP|Special|OVA|Movie|Bonus|Extra)\b",
        r"\b(?:2160p|1080p|720p|480p|360p|4k|8k|BD|WEB[- ]DL|WEB|HEVC|x264|x265)\b",
    ]
    for pattern in removal_patterns:
        title = re.sub(pattern, "", title, flags=re.I)

    title = re.sub(r"[\[\]\(\)\{\}]", "", title).strip()
    title = re.sub(r"\s{2,}", " ", title)
    if not title:
        title = original

    return {
        "file_name": original,
        "title": title,
        "season": season,
        "episode": episode,
        "quality": quality,
        "special": special,
    }


def _group_stage_files(staged):
    entries = []
    for idx, (message, metadata) in enumerate(zip(staged["messages"], staged["metadata"])):
        entries.append({
            "message": message,
            "title": metadata.get("title"),
            "season": metadata.get("season"),
            "episode": metadata.get("episode"),
            "quality": metadata.get("quality"),
            "special": metadata.get("special"),
            "index": idx,
        })

    entries.sort(
        key=lambda item: (
            0 if item["special"] else 1,
            item["season"] if item["season"] is not None else 999,
            item["episode"] if item["episode"] is not None else 999,
            item["quality"] or "",
            item["index"],
        )
    )

    has_seasons = any(item["season"] is not None for item in entries)
    groups = {}

    if has_seasons:
        for item in entries:
            if item["special"]:
                group_key = ("special", item["quality"] or "any")
                group_label = "Special"
            elif item["season"] is not None:
                group_key = ("season", item["season"], item["quality"] or "any")
                group_label = f"Season {item['season']}"
            else:
                group_key = ("unsorted", item["quality"] or "any")
                group_label = "Unsorted"

            group = groups.setdefault(group_key, {
                "label": group_label,
                "quality": item["quality"],
                "season": item["season"],
                "special": item["special"],
                "entries": [],
            })
            group["entries"].append(item)
    else:
        groups[("all", None)] = {
            "label": "All files",
            "quality": None,
            "season": None,
            "special": False,
            "entries": entries,
        }

    return groups


@app.on_message(filters.private & is_admin & (filters.document | filters.video | filters.audio | filters.animation | filters.photo))
async def stage_batch_files(client, message):
    stage = staged_batches.setdefault(message.from_user.id, {"messages": [], "metadata": []})
    file_name = _extract_media_filename(message)
    metadata = _parse_file_metadata(file_name)
    stage["messages"].append(message)
    stage["metadata"].append(metadata)

    count = len(stage["messages"])
    await message.reply_text(
        f"📥 Added file {count}.\n"
        f"`{metadata['file_name']}`\n"
        f"Episode: {metadata['episode'] or 'unknown'} | Quality: {metadata['quality'] or 'unknown'}\n\n"
        "When ready, send `/batchsave <English name>` to save all staged files to storage."
    )


@app.on_message(filters.command("batchsave") & is_admin)
async def batchsave(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/batchsave <English name>`")
        return

    staged = staged_batches.pop(message.from_user.id, None)
    if not staged or not staged["messages"]:
        await message.reply_text(
            "❌ No staged files found.\n"
            "Forward the anime files to me first, then send `/batchsave <English name>`."
        )
        return

    english_name = " ".join(message.command[1:]).strip()
    original_name = staged["metadata"][0]["title"] or english_name
    qualities = sorted({m["quality"] for m in staged["metadata"] if m["quality"]})
    episode_numbers = [int(m["episode"]) for m in staged["metadata"] if m["episode"] and m["episode"].isdigit()]
    quality_text = ", ".join(qualities) if qualities else ""
    if episode_numbers:
        episode_range = f"{min(episode_numbers)}–{max(episode_numbers)}"
    else:
        episode_range = f"{len(staged['messages'])} files"

    status_msg = await message.reply_text(
        f"📦 Saving {len(staged['messages'])} files to storage as **{english_name}**..."
    )

    saved_ids = []
    for media_message in staged["messages"]:
        try:
            stored = await media_message.copy(STORAGE_CHANNEL)
            saved_ids.append(stored.id)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Storage copy error: {e}")
            await message.reply_text(f"⚠️ Could not copy a file to storage: {e}")

    if not saved_ids:
        await status_msg.edit_text("❌ Failed to save any files to the storage channel.")
        return

    batch_code = generate_code()
    cursor.execute(
        "INSERT INTO batches (code, name, original_name, start_id, end_id, message_ids, quality, episode_range, file_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            batch_code,
            english_name,
            original_name,
            saved_ids[0],
            saved_ids[-1],
            json.dumps(saved_ids),
            quality_text,
            episode_range,
            len(saved_ids)
        )
    )
    db.commit()

    await status_msg.edit_text(
        f"✅ Saved {len(saved_ids)} files.\n"
        f"**English name:** {english_name}\n"
        f"**Original file title:** {original_name}\n"
        f"**Episode range:** {episode_range}\n"
        f"**Quality:** {quality_text or 'detected automatically'}\n"
        f"**Batch link:** https://t.me/{BOT_USERNAME}?start=batch_{batch_code}"
    )


@app.on_message(filters.command("batchlinks") & is_admin)
async def batchlinks(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/batchlinks <English name>`")
        return

    staged = staged_batches.pop(message.from_user.id, None)
    if not staged or not staged["messages"]:
        await message.reply_text(
            "❌ No staged files found.\n"
            "Forward the anime files to me first, then send `/batchlinks <English name>`."
        )
        return

    english_name = " ".join(message.command[1:]).strip()
    original_name = staged["metadata"][0].get("title") or english_name
    groups = _group_stage_files(staged)

    if not groups:
        await message.reply_text("❌ Could not group files for batch links.")
        return

    batch_links = []
    for group_key, group in groups.items():
        group_label = group["label"]
        quality_text = group["quality"] or ""
        if quality_text and group_label not in {"All files", "Special", "Unsorted"}:
            group_label = f"{group_label} {quality_text}"
        elif quality_text and group_label in {"Special", "Unsorted"}:
            group_label = f"{group_label} {quality_text}"

        batch_name = english_name if group_key == ("all", None) else f"{english_name} — {group_label}"
        episode_numbers = [entry["episode"] for entry in group["entries"] if entry["episode"] is not None]
        if episode_numbers:
            episode_range = f"{min(episode_numbers)}–{max(episode_numbers)}"
        else:
            episode_range = f"{len(group['entries'])} files"

        saved_ids = []
        for entry in group["entries"]:
            try:
                stored = await entry["message"].copy(STORAGE_CHANNEL)
                saved_ids.append(stored.id)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Storage copy error: {e}")
                await message.reply_text(f"⚠️ Could not copy a file to storage: {e}")

        if not saved_ids:
            continue

        batch_code = generate_code()
        cursor.execute(
            "INSERT INTO batches (code, name, original_name, start_id, end_id, message_ids, quality, episode_range, file_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                batch_code,
                batch_name,
                original_name,
                saved_ids[0],
                saved_ids[-1],
                json.dumps(saved_ids),
                quality_text,
                episode_range,
                len(saved_ids),
            )
        )
        db.commit()

        batch_links.append((batch_name, batch_code, len(saved_ids), quality_text))

    if not batch_links:
        await message.reply_text("❌ No batch links could be created.")
        return

    buttons = []
    text_lines = [f"✅ Created {len(batch_links)} batch link(s) for **{english_name}**:"]
    for label, code, count, quality in batch_links:
        text_lines.append(f"• {label} — {count} files")
        buttons.append([InlineKeyboardButton(label, url=f"https://t.me/{BOT_USERNAME}?start=batch_{code}")])

    await message.reply_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_message(filters.command("batchcancel") & is_admin)
async def batchcancel(client, message):
    if staged_batches.pop(message.from_user.id, None):
        await message.reply_text("✅ Staged upload canceled.")
    else:
        await message.reply_text("❌ No staged upload to cancel.")


@app.on_message(filters.command("start"))
async def start_batch(client, message):
    if len(message.command) < 2 or not message.command[1].startswith("batch_"):
        await message.reply_text(
            "👋 Welcome! Use a batch link to get files.\n"
            "Example: /start batch_xrTbNWF77w"
        )
        return

    code = message.command[1].split("_", 1)[1]
    cursor.execute(
        "SELECT code, name, original_name, start_id, end_id FROM batches WHERE code=?",
        (code,)
    )
    data = cursor.fetchone()
    if not data:
        await message.reply_text("❌ Batch not found.")
        return

    _, name, original_name, start_id, end_id = data
    display_name = name or original_name or code
    user_id = message.from_user.id
    authorized = is_authorized(user_id)

    cursor.execute(
        "INSERT OR REPLACE INTO users(user_id, username, first_name, last_seen) VALUES(?,?,?,?)",
        (
            user_id,
            message.from_user.username or "",
            message.from_user.first_name or "",
            int(time.time()),
        )
    )
    cursor.execute("UPDATE batches SET fetch_count = fetch_count + 1 WHERE code=?", (code,))
    db.commit()

    title_line = f"**{display_name}**\n\n"
    if authorized:
        notice_text = f"{title_line}Sending episodes... Please wait."
    else:
        notice_text = (
            f"{title_line}"
            "⚠️ These files will be **automatically deleted in 10 minutes**.\n"
            "Please save them before then!\n\n"
            "Sending episodes... Please wait."
        )

    notice = await message.reply_text(notice_text)
    sent_ids = [notice.id]

    cursor.execute("SELECT message_ids FROM batches WHERE code=?", (code,))
    row = cursor.fetchone()
    message_ids = None
    if row and row[0]:
        try:
            message_ids = json.loads(row[0])
        except Exception:
            message_ids = None

    if message_ids:
        ids_to_send = message_ids
    else:
        ids_to_send = list(range(start_id, end_id + 1))

    for msg_id in ids_to_send:
        while True:
            try:
                sent = await client.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=STORAGE_CHANNEL,
                    message_id=msg_id
                )
                sent_ids.append(sent.id)
                await asyncio.sleep(0.5)
                break
            except Exception as e:
                if hasattr(e, 'value'):
                    await asyncio.sleep(e.value)
                    continue
                print(f"Error sending msg {msg_id}: {e}")
                break

    await message.reply_sticker(get_random_sticker_id())
    if authorized:
        del_key = generate_code(12)
        done_msg = await message.reply_text(
            "✅ Done! Enjoy watching.\n\n"
            "🗑 Use the button below when you want to delete these files.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Delete Files", callback_data=f"manualdelete_{del_key}")]
            ])
        )
        pending_deletes[del_key] = (message.chat.id, user_id, display_name, sent_ids + [done_msg.id])
    else:
        done_msg = await message.reply_text(
            "✅ Done! Enjoy watching.\n\n"
            "🗑 Files will be deleted in **10 minutes**. Save them now!"
        )
        sent_ids.append(done_msg.id)
        asyncio.create_task(
            delete_messages_later(client, message.chat.id, sent_ids, DELETE_AFTER)
        )


@app.on_message(filters.private, group=0)
async def debug_private_message(client, message):
    user = message.from_user
    text = message.text or message.caption or "<non-text>"
    print(f"DEBUG PRIVATE from {user.id} ({user.username}) -> {text}")


@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    user_id = message.from_user.id
    authorized = is_authorized(user_id)

    general = (
        "📖 **Help — Available Commands**\n\n"
        "**📦 Batches**\n"
        "• `/search <name>` — Search for a batch by name\n"
        "• `/myfiles` — View & delete your pending file deliveries\n\n"
        "**🔍 Anime Discovery**\n"
        "• `/anime <title>` — Search for any anime by name\n"
        "• `/trending` — Top currently-airing anime by type\n"
        "• `/upcoming` — Next season's lineup by type\n"
        "• `/top` — All-time highest-rated anime by genre\n"
        "• `/random` — Surprise pick from a genre\n"
        "• `/anime_genres` — Filter top anime by multiple genres\n\n"
        "**📋 Watchlist**\n"
        "• `/watch <title>` — Add an anime to your watchlist\n"
        "• `/watchlist` — View, tick off & manage your list\n\n"
        "**⏰ Reminders**\n"
        "• `/remind DD-MM-YYYY HH:MM <message>` — Set a reminder\n"
        "• `/reminders` — View & cancel upcoming reminders\n\n"
        "• `/clear` — Reply to any bot message to delete it\n\n"
        "**📥 Requests**\n"
        "• `/request <title>` — Request an anime to be added"
    )

    batch_extra = (
        "\n\n━━━━━━━━━━━━━━━\n"
        "🔧 **Batch Admin Commands**\n"
        "• `/batch <start> <end> <name>` — Create a new batch\n"
        "• `/batchlinks <English name>` — Save staged files into season/quality batch links\n"
        "• `/delete <code>` — Delete a batch by code\n"
        "• `/listbatches` — Browse & delete all batches\n"
        "• `/addauth <id>` — Authorize a user\n"
        "• `/removeauth <id>` — Remove authorization\n"
        "• `/authlist` — List all authorized users\n"
        "• `/requests` — Browse all anime requests by status"
    )

    super_extra = (
        "\n\n━━━━━━━━━━━━━━━\n"
        "👑 **Super Admin Commands**\n"
        "• `/addadmin <id>` — Add a new admin\n"
        "• `/removeadmin <id>` — Remove an admin\n"
        "• `/adminlist` — List all admins\n"
        "• `/broadcast` — Send announcement to all users\n"
        "• `/stats` — Bot usage dashboard\n"
        "• `/status` — Last GitHub sync result"
    )

    text = general
    if is_admin(user_id):
        text += batch_extra
    if user_id == ADMIN_ID:
        text += super_extra
    await message.reply_text(text)


@app.on_message(filters.command("ping"))
async def ping(client, message):
    await message.reply_text("pong 🟢")


@app.on_message(filters.command("batch"))
async def batch(client, message):
    if not is_admin(message.from_user.id):
        return

    try:
        start_id = int(message.command[1])
        end_id = int(message.command[2])
        name = " ".join(message.command[3:]) if len(message.command) > 3 else ""
    except Exception:
        await message.reply_text(
            "Usage:\n`/batch start_id end_id Anime Name Quality`\n\n"
            "Example:\n`/batch 10 22 Naruto 720p`"
        )
        return

    code = generate_code()
    cursor.execute(
        "INSERT INTO batches (code, name, start_id, end_id) VALUES (?, ?, ?, ?)",
        (code, name, start_id, end_id)
    )
    db.commit()

    link = f"https://t.me/{BOT_USERNAME}?start=batch_{code}"
    label = f"📦 {name}" if name else "📦 Open Batch"
    await message.reply_text(
        f"✅ Batch Created!\n\n**Name:** {name or '_(no name)_'}\n**Link:** {link}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(label, url=link)]]
        )
    )


@app.on_message(filters.command("delete"))
async def delete_batch(client, message):
    if not is_admin(message.from_user.id):
        return
    if len(message.command) < 2:
        await message.reply_text(
            "Usage:\n`/delete <code>`\n\n"
            "Get the code from the batch link — it's the part after `batch_`\n"
            "Example: `https://t.me/AnimebayFS_Bot?start=batch_xrTbNWF77w` → code is `xrTbNWF77w`\n\n"
            "Or use `/search` to find a batch and its code."
        )
        return

    code = message.command[1].strip()
    cursor.execute("SELECT name FROM batches WHERE code=?", (code,))
    row = cursor.fetchone()
    if not row:
        await message.reply_text(f"❌ No batch found with code `{code}`.")
        return

    name = row[0] or code
    cursor.execute("DELETE FROM batches WHERE code=?", (code,))
    db.commit()
    await message.reply_text(f"🗑 Batch **{name}** (`{code}`) has been deleted.")


@app.on_message(filters.command("listbatches"))
async def listbatches(client, message):
    if not is_admin(message.from_user.id):
        return

    offset = 0
    if len(message.command) == 2:
        try:
            offset = int(message.command[1])
        except ValueError:
            pass

    PAGE = 10
    cursor.execute("SELECT code, name, original_name FROM batches ORDER BY rowid DESC LIMIT ? OFFSET ?", (PAGE + 1, offset))
    rows = cursor.fetchall()
    if not rows:
        await message.reply_text("📭 No batches found." if offset == 0 else "No more batches.")
        return

    has_more = len(rows) > PAGE
    rows = rows[:PAGE]
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"lbpage_{offset - PAGE}"))
    if has_more:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lbpage_{offset + PAGE}"))

    buttons = []
    for code, name, original_name in rows:
        label = name or original_name or code
        link = f"https://t.me/{BOT_USERNAME}?start=batch_{code}"
        buttons.append([
            InlineKeyboardButton(f"📦 {label}", url=link),
            InlineKeyboardButton("🗑", callback_data=f"delbatch_{code}")
        ])
    if nav_buttons:
        buttons.append(nav_buttons)

    cursor.execute("SELECT COUNT(*) FROM batches")
    total = cursor.fetchone()[0]
    await message.reply_text(
        f"📋 **Batch Library** — {total} total (showing {offset + 1}–{offset + len(rows)}):",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query(filters.regex(r"^delbatch_(.+)$"))
async def delbatch_callback(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Admins only.", show_alert=True)
        return

    code = callback_query.matches[0].group(1)
    cursor.execute("SELECT name FROM batches WHERE code=?", (code,))
    row = cursor.fetchone()
    if not row:
        await callback_query.answer("Batch already deleted.", show_alert=True)
        return

    name = row[0] or code
    cursor.execute("DELETE FROM batches WHERE code=?", (code,))
    db.commit()
    await callback_query.answer(f"🗑 \"{name}\" deleted.", show_alert=False)

    orig_text = callback_query.message.text or ""
    offset_match = re.search(r"showing (\d+)–", orig_text)
    offset = (int(offset_match.group(1)) - 1) if offset_match else 0

    PAGE = 10
    cursor.execute("SELECT code, name, original_name FROM batches ORDER BY rowid DESC LIMIT ? OFFSET ?", (PAGE + 1, offset))
    rows = cursor.fetchall()
    if not rows:
        try:
            await callback_query.message.edit_text("📭 No more batches in the library.")
        except Exception:
            pass
        return

    has_more = len(rows) > PAGE
    rows = rows[:PAGE]
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"lbpage_{offset - PAGE}"))
    if has_more:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lbpage_{offset + PAGE}"))

    buttons = []
    for c, n, original_name in rows:
        label = n or original_name or c
        link = f"https://t.me/{BOT_USERNAME}?start=batch_{c}"
        buttons.append([
            InlineKeyboardButton(f"📦 {label}", url=link),
            InlineKeyboardButton("🗑", callback_data=f"delbatch_{c}")
        ])
    if nav_buttons:
        buttons.append(nav_buttons)

    cursor.execute("SELECT COUNT(*) FROM batches")
    total = cursor.fetchone()[0]
    try:
        await callback_query.message.edit_text(
            f"📋 **Batch Library** — {total} total (showing {offset + 1}–{offset + len(rows)}):",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^lbpage_(\d+)$"))
async def lbpage_callback(client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Admins only.", show_alert=True)
        return

    offset = int(callback_query.matches[0].group(1))
    PAGE = 10
    cursor.execute("SELECT code, name, original_name FROM batches ORDER BY rowid DESC LIMIT ? OFFSET ?", (PAGE + 1, offset))
    rows = cursor.fetchall()
    if not rows:
        await callback_query.answer("No more batches.", show_alert=True)
        return

    has_more = len(rows) > PAGE
    rows = rows[:PAGE]
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"lbpage_{offset - PAGE}"))
    if has_more:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"lbpage_{offset + PAGE}"))

    buttons = []
    for code, name, original_name in rows:
        label = name or original_name or code
        link = f"https://t.me/{BOT_USERNAME}?start=batch_{code}"
        buttons.append([
            InlineKeyboardButton(f"📦 {label}", url=link),
            InlineKeyboardButton("🗑", callback_data=f"delbatch_{code}")
        ])
    if nav_buttons:
        buttons.append(nav_buttons)

    cursor.execute("SELECT COUNT(*) FROM batches")
    total = cursor.fetchone()[0]
    await callback_query.answer()
    try:
        await callback_query.message.edit_text(
            f"📋 **Batch Library** — {total} total (showing {offset + 1}–{offset + len(rows)}):",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass


@app.on_message(filters.command("search") & is_auth)
async def search(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage:\n`/search Naruto 720p`")
        return

    query = " ".join(message.command[1:]).strip()
    terms = query.split()
    conditions = " AND ".join(["LOWER(name) LIKE ?" for _ in terms])
    values = [f"%{t.lower()}%" for t in terms]

    search_conditions = " AND ".join(["(LOWER(name) LIKE ? OR LOWER(original_name) LIKE ?)" for _ in terms])
    search_values = []
    for t in terms:
        search_values += [f"%{t.lower()}%", f"%{t.lower()}%"]

    cursor.execute(
        f"SELECT code, name, original_name FROM batches WHERE {search_conditions} ORDER BY name",
        search_values
    )
    results = cursor.fetchall()

    if not results and len(terms) > 1:
        cursor.execute(
            "SELECT code, name, original_name FROM batches WHERE LOWER(name) LIKE ? OR LOWER(original_name) LIKE ? ORDER BY name",
            (f"%{terms[0].lower()}%", f"%{terms[0].lower()}%")
        )
        results = cursor.fetchall()

    if not results:
        await message.reply_text(f"❌ No results found for: **{query}**")
        return

    results = results[:10]
    buttons = []
    for code, name, original_name in results:
        label = name or original_name or code
        buttons.append([InlineKeyboardButton(label, url=f"https://t.me/{BOT_USERNAME}?start=batch_{code}")])

    await message.reply_text(
        f"🔍 Results for **{query}** ({len(results)} found):",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_message(filters.command("myfiles") & is_auth)
async def myfiles(client, message):
    user_id = message.from_user.id
    user_entries = [
        (key, entry)
        for key, entry in pending_deletes.items()
        if entry[1] == user_id
    ]
    if not user_entries:
        await message.reply_text("📭 You have no pending files to delete.")
        return

    buttons = []
    for key, (chat_id, uid, batch_name, msg_ids) in user_entries:
        label = f"🗑️ {batch_name}" if batch_name else f"🗑️ Batch ({len(msg_ids) - 1} files)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"manualdelete_{key}")])
    if len(user_entries) > 1:
        buttons.append([InlineKeyboardButton("🗑️ Delete All", callback_data=f"deleteall_{user_id}")])

    await message.reply_text(
        f"📂 **Your pending files** ({len(user_entries)} batch{'es' if len(user_entries) > 1 else ''}):\n\n"
        "Tap a batch to delete it, or use **Delete All** to wipe everything at once.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query(filters.regex(r"^manualdelete_(.+)$"))
async def manual_delete_files(client, callback_query):
    del_key = callback_query.matches[0].group(1)
    entry = pending_deletes.pop(del_key, None)
    if not entry:
        await callback_query.answer("Files already deleted.", show_alert=True)
        return

    chat_id, _uid, _name, msg_ids = entry
    await callback_query.answer("Deleting files...", show_alert=False)
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=msg_ids)
    except Exception as e:
        print(f"Manual delete error: {e}")


@app.on_callback_query(filters.regex(r"^deleteall_(\d+)$"))
async def delete_all_files(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("This button isn't for you.", show_alert=True)
        return

    user_keys = [k for k, v in pending_deletes.items() if v[1] == user_id]
    if not user_keys:
        await callback_query.answer("Nothing left to delete.", show_alert=True)
        return

    await callback_query.answer("Deleting all files...", show_alert=False)
    for key in user_keys:
        entry = pending_deletes.pop(key, None)
        if entry:
            chat_id, _uid, _name, msg_ids = entry
            try:
                await client.delete_messages(chat_id=chat_id, message_ids=msg_ids)
            except Exception as e:
                print(f"Delete all error: {e}")
    try:
        await callback_query.message.delete()
    except Exception:
        pass
