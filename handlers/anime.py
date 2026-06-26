import random
import re
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import app
from auth import is_auth
from anilist import anilist_query, genre_to_cb, cb_to_genre
from config import GENRES
from state import user_selections
from utils import get_random_sticker_id


def build_genre_keyboard(user_id):
    selected = user_selections.get(user_id, [])
    keyboard = []
    row = []
    for name in GENRES:
        text = f"✅ {name}" if name in selected else name
        row.append(InlineKeyboardButton(text, callback_data=f"genre_{genre_to_cb(name)}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔍 Find Top Anime", callback_data="search_anime")])
    keyboard.append([
        InlineKeyboardButton("🗑️ Clear Checkmarks", callback_data="clear_genres"),
        InlineKeyboardButton("❌ Close Menu", callback_data="close_menu")
    ])
    return InlineKeyboardMarkup(keyboard)


def build_random_genre_keyboard():
    keyboard = []
    row = []
    for name in GENRES:
        row.append(InlineKeyboardButton(name, callback_data=f"rndgenre_{genre_to_cb(name)}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_menu")])
    return InlineKeyboardMarkup(keyboard)


def build_top_genre_keyboard():
    keyboard = []
    row = []
    for name in GENRES:
        row.append(InlineKeyboardButton(name, callback_data=f"topgenre_{genre_to_cb(name)}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_menu")])
    return InlineKeyboardMarkup(keyboard)


@app.on_message(filters.command("clear") & is_auth)
async def clear_message(client, message):
    if not message.reply_to_message:
        await message.reply_text("❌ Reply to the bot's message you want to delete with `/clear`")
        return
    try:
        await client.delete_messages(
            chat_id=message.chat.id,
            message_ids=[message.reply_to_message.id, message.id]
        )
    except Exception as e:
        print(f"Error in clear command: {e}")


@app.on_message(filters.command("anime") & is_auth)
async def anime_search(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: `/anime <title>`\nExample: `/anime Attack on Titan`")
        return

    query = " ".join(message.command[1:]).strip()
    await message.reply_sticker(get_random_sticker_id())
    await message.reply_text(f"🔍 Searching for **{query}**...")

    gql = """
    query ($search: String) {
      Page(page: 1, perPage: 5) {
        media(type: ANIME, search: $search, sort: [SEARCH_MATCH]) {
          title { romaji english native }
          format
          status
          episodes
          averageScore
          season
          seasonYear
          genres
          description(asHtml: false)
          siteUrl
        }
      }
    }
    """

    result = await anilist_query(gql, {"search": query})
    if not result:
        await message.reply_text("⚠️ AniList API is unavailable, try again later.")
        return

    results = result.get("Page", {}).get("media", [])
    if not results:
        await message.reply_text(f"❌ No results found for **{query}**.")
        return

    for anime in results[:3]:
        title_en = anime["title"].get("english") or ""
        title_rom = anime["title"].get("romaji") or ""
        title_nat = anime["title"].get("native") or ""
        display = title_en or title_rom
        alt = f" / {title_rom}" if title_en and title_rom != title_en else ""
        score = f'{anime["averageScore"] / 10:.1f}' if anime.get("averageScore") else "N/A"
        episodes = anime.get("episodes") or "?"
        fmt = anime.get("format") or "?"
        status = (anime.get("status") or "").replace("_", " ").title()
        season = (anime.get("season") or "").title()
        year = anime.get("seasonYear") or ""
        airing = f"{season} {year}".strip() if (season or year) else "TBA"
        genres = ", ".join(anime.get("genres", [])[:4])
        raw_desc = anime.get("description") or "No synopsis available."
        synopsis = re.sub(r"<[^>]+>", "", raw_desc)[:250]
        if len(raw_desc) > 250:
            synopsis += "…"
        link = anime.get("siteUrl", "")

        text = (
            f"**[{display}{alt}]({link})**"
            + (f"\n🇯🇵 {title_nat}" if title_nat else "")
            + f"\n\n⭐ **{score}** · {fmt} · 🎬 {episodes} eps"
            + f"\n📅 {airing} · {status}"
            + f"\n🏷 {genres}"
            + f"\n\n{synopsis}"
        )
        await message.reply_text(text, disable_web_page_preview=True)


@app.on_message(filters.command("trending") & is_auth)
async def trending(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 TV", callback_data="trending_tv"), InlineKeyboardButton("🎬 Movie", callback_data="trending_movie")],
        [InlineKeyboardButton("📼 OVA", callback_data="trending_ova"), InlineKeyboardButton("✨ Special", callback_data="trending_special")],
        [InlineKeyboardButton("🌐 All Types", callback_data="trending_all")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")],
    ])
    await message.reply_text(
        "🔥 **What's Trending Now?**\n\nPick a type to see the top currently-airing anime:",
        reply_markup=keyboard
    )


@app.on_callback_query(filters.regex(r"^trending_(\w+)$") & is_auth)
async def trending_results(client, callback_query):
    anime_type = callback_query.matches[0].group(1)
    label = {"tv": "TV", "movie": "Movie", "ova": "OVA", "special": "Special", "all": "All Types"}.get(anime_type, anime_type.title())
    await callback_query.answer(f"Fetching top {label} anime...", show_alert=False)

    format_filter = f', format: {label}' if anime_type != "all" else ""
    gql = f"""
    query {{
      Page(page: 1, perPage: 8) {{
        media(type: ANIME, status: RELEASING{format_filter}, sort: [TRENDING_DESC], isAdult: false) {{
          title {{ romaji english }}
          episodes
          averageScore
          siteUrl
          format
        }}
      }}
    }}
    """

    result = await anilist_query(gql)
    if not result:
        await callback_query.message.reply_text("⚠️ AniList API is unavailable, try again later.")
        return

    results = result.get("Page", {}).get("media", [])
    if not results:
        await callback_query.message.reply_text(f"No currently-airing {label} anime found.")
        return

    lines = [f"🔥 **Top Airing — {label}**\n"]
    for i, anime in enumerate(results, 1):
        title = anime["title"].get("english") or anime["title"].get("romaji", "Unknown")
        score = f'{anime.get("averageScore") / 10:.1f}' if anime.get("averageScore") else "N/A"
        episodes = anime.get("episodes") or "?"
        link = anime.get("siteUrl", "")
        lines.append(f"{i}. [{title}]({link})\n   ⭐ **{score}** · 🎬 {episodes} eps")

    close_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Search Again", callback_data="trending_reopen")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")],
    ])
    await callback_query.message.reply_text("\n".join(lines), disable_web_page_preview=True, reply_markup=close_markup)


@app.on_callback_query(filters.regex(r"^trending_reopen$") & is_auth)
async def trending_reopen(client, callback_query):
    await trending(client, callback_query.message)
    await callback_query.answer()


@app.on_message(filters.command("upcoming") & is_auth)
async def upcoming(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 TV", callback_data="upcoming_tv"), InlineKeyboardButton("🎬 Movie", callback_data="upcoming_movie")],
        [InlineKeyboardButton("📼 OVA", callback_data="upcoming_ova"), InlineKeyboardButton("✨ Special", callback_data="upcoming_special")],
        [InlineKeyboardButton("🌐 All Types", callback_data="upcoming_all")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")],
    ])
    await message.reply_text(
        "🗓 **Upcoming Anime**\n\nPick a type to see what's arriving next season:",
        reply_markup=keyboard
    )


@app.on_callback_query(filters.regex(r"^upcoming_(\w+)$") & is_auth)
async def upcoming_results(client, callback_query):
    anime_type = callback_query.matches[0].group(1)
    fmt_map = {"tv": "TV", "movie": "MOVIE", "ova": "OVA", "special": "SPECIAL"}
    label_map = {"tv": "TV", "movie": "Movie", "ova": "OVA", "special": "Special", "all": "All Types"}
    label = label_map.get(anime_type, anime_type.title())
    await callback_query.answer(f"Fetching upcoming {label}...", show_alert=False)

    format_filter = f', format: {fmt_map[anime_type]}' if anime_type in fmt_map else ""
    gql = f"""
    query {{
      Page(page: 1, perPage: 10) {{
        media(type: ANIME, status: NOT_YET_RELEASED{format_filter}, sort: [POPULARITY_DESC], isAdult: false) {{
          title {{ romaji english }}
          format
          episodes
          averageScore
          season
          seasonYear
          siteUrl
        }}
      }}
    }}
    """

    result = await anilist_query(gql)
    if not result:
        await callback_query.message.reply_text("⚠️ AniList API is unavailable, try again later.")
        return

    results = result.get("Page", {}).get("media", [])
    if not results:
        await callback_query.message.reply_text(
            f"No upcoming {label} anime found yet — check back closer to the season start!"
        )
        return

    lines = [f"🗓 **Upcoming — {label}**\n"]
    for i, anime in enumerate(results, 1):
        title = anime["title"].get("english") or anime["title"].get("romaji", "Unknown")
        score = f'{anime.get("averageScore") / 10:.1f}' if anime.get("averageScore") else "TBA"
        season = (anime.get("season") or "").title()
        year = anime.get("seasonYear") or ""
        airing = f"{season} {year}".strip() if (season or year) else "TBA"
        link = anime.get("siteUrl", "")
        lines.append(f"{i}. [{title}]({link})\n   📅 {airing} · ⭐ {score}")

    close_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Search Again", callback_data="upcoming_reopen")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")],
    ])
    await callback_query.message.reply_text("\n".join(lines), disable_web_page_preview=True, reply_markup=close_markup)


@app.on_callback_query(filters.regex(r"^upcoming_reopen$") & is_auth)
async def upcoming_reopen(client, callback_query):
    await upcoming(client, callback_query.message)
    await callback_query.answer()


@app.on_message(filters.command("random") & is_auth)
async def random_cmd(client, message):
    await message.reply_text(
        "🎲 **Random Anime Pick**\n\nChoose a genre and I'll surprise you:",
        reply_markup=build_random_genre_keyboard()
    )


@app.on_callback_query(filters.regex(r"^rndgenre_(.+)$") & is_auth)
async def random_genre_pick(client, callback_query):
    genre_cb = callback_query.matches[0].group(1)
    genre_name = cb_to_genre(genre_cb)
    await callback_query.answer("Rolling the dice...", show_alert=False)

    page = random.randint(1, 5)
    gql = """
    query ($genre: String, $page: Int) {
      Page(page: $page, perPage: 25) {
        media(type: ANIME, genre: $genre, sort: [SCORE_DESC], averageScore_greater: 65, isAdult: false) {
          title { romaji english }
          episodes
          averageScore
          genres
          description(asHtml: false)
          siteUrl
        }
      }
    }
    """

    result = await anilist_query(gql, {"genre": genre_name, "page": page})
    media = (result or {}).get("Page", {}).get("media", [])
    if not media:
        result = await anilist_query(gql, {"genre": genre_name, "page": 1})
        media = (result or {}).get("Page", {}).get("media", [])

    if not media:
        await callback_query.message.reply_text("Couldn't find anything for that genre. Try another!")
        return

    anime = random.choice(media)
    title = anime["title"].get("english") or anime["title"].get("romaji", "Unknown")
    score = f'{anime.get("averageScore") / 10:.1f}' if anime.get("averageScore") else "N/A"
    episodes = anime.get("episodes") or "?"
    raw_desc = anime.get("description") or "No synopsis available."
    synopsis = re.sub(r"<[^>]+>", "", raw_desc)[:300]
    if len(raw_desc) > 300:
        synopsis += "…"
    link = anime.get("siteUrl", "")
    genres = ", ".join(anime.get("genres", [])[:4])

    text = (
        "🎲 **Your Random Pick!**\n\n"
        f"**[{title}]({link})**\n"
        f"⭐ Score: **{score}** · 🎬 Episodes: **{episodes}**\n"
        f"🏷 {genres}\n\n"
        f"{synopsis}"
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Try Another", callback_data=f"rndgenre_{genre_cb}")],
        [InlineKeyboardButton("🔀 Pick New Genre", callback_data="rnd_reopen")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")],
    ])
    await callback_query.message.reply_text(text, disable_web_page_preview=True, reply_markup=markup)


@app.on_callback_query(filters.regex(r"^rnd_reopen$") & is_auth)
async def rnd_reopen(client, callback_query):
    await callback_query.message.reply_text(
        "🎲 **Random Anime Pick**\n\nChoose a genre and I'll surprise you:",
        reply_markup=build_random_genre_keyboard()
    )
    await callback_query.answer()


@app.on_message(filters.command("top") & is_auth)
async def top_cmd(client, message):
    await message.reply_text(
        "🏆 **All-Time Top Anime**\n\nPick a genre to see the highest-rated titles ever made in it:",
        reply_markup=build_top_genre_keyboard()
    )


@app.on_callback_query(filters.regex(r"^topgenre_(.+)$") & is_auth)
async def top_genre_results(client, callback_query):
    genre_cb = callback_query.matches[0].group(1)
    genre_name = cb_to_genre(genre_cb)
    await callback_query.answer(f"Fetching top {genre_name}...", show_alert=False)

    gql = """
    query ($genre: String) {
      Page(page: 1, perPage: 10) {
        media(type: ANIME, genre: $genre, sort: [SCORE_DESC], isAdult: false) {
          title { romaji english }
          episodes
          averageScore
          format
          siteUrl
        }
      }
    }
    """

    result = await anilist_query(gql, {"genre": genre_name})
    if not result:
        await callback_query.message.reply_text("⚠️ AniList API is unavailable, try again later.")
        return

    results = result.get("Page", {}).get("media", [])
    if not results:
        await callback_query.message.reply_text(f"No results found for **{genre_name}**. Try another genre!")
        return

    lines = [f"🏆 **All-Time Top — {genre_name}**\n"]
    for i, anime in enumerate(results, 1):
        title = anime["title"].get("english") or anime["title"].get("romaji", "Unknown")
        score = f'{anime.get("averageScore") / 10:.1f}' if anime.get("averageScore") else "N/A"
        episodes = anime.get("episodes") or "?"
        anime_type = anime.get("format") or "?"
        link = anime.get("siteUrl", "")
        lines.append(f"{i}. [{title}]({link})\n   ⭐ **{score}** · {anime_type} · 🎬 {episodes} eps")

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔀 Pick New Genre", callback_data="top_reopen")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")],
    ])
    await callback_query.message.reply_text("\n".join(lines), disable_web_page_preview=True, reply_markup=markup)


@app.on_callback_query(filters.regex(r"^top_reopen$") & is_auth)
async def top_reopen(client, callback_query):
    await client.send_message(
        callback_query.message.chat.id,
        "🏆 **All-Time Top Anime**\n\nPick a genre to see the highest-rated titles ever made in it:",
        reply_markup=build_top_genre_keyboard()
    )
    await callback_query.answer()


@app.on_message(filters.command("anime_genres") & is_auth)
async def start_genre_selection(client, message):
    user_id = message.from_user.id
    user_selections[user_id] = []
    await message.reply_text(
        "**Select genres to find top-rated anime:**",
        reply_markup=build_genre_keyboard(user_id)
    )


@app.on_callback_query(filters.regex(r"^genre_(.+)$") & is_auth)
async def toggle_genre(client, callback_query):
    user_id = callback_query.from_user.id
    genre_name = cb_to_genre(callback_query.matches[0].group(1))
    if user_id not in user_selections:
        user_selections[user_id] = []
    if genre_name in user_selections[user_id]:
        user_selections[user_id].remove(genre_name)
    else:
        user_selections[user_id].append(genre_name)
    await callback_query.edit_message_reply_markup(reply_markup=build_genre_keyboard(user_id))


@app.on_callback_query(filters.regex(r"^clear_genres$") & is_auth)
async def clear_genres(client, callback_query):
    user_id = callback_query.from_user.id
    user_selections[user_id] = []
    await callback_query.edit_message_reply_markup(reply_markup=build_genre_keyboard(user_id))


@app.on_callback_query(filters.regex(r"^search_anime$") & is_auth)
async def search_anime(client, callback_query):
    user_id = callback_query.from_user.id
    selected = user_selections.get(user_id, [])
    if not selected:
        await callback_query.answer("Select at least one genre first!", show_alert=True)
        return
    await callback_query.answer("Fetching top-rated series...", show_alert=False)

    gql = """
    query ($genres: [String]) {
      Page(page: 1, perPage: 5) {
        media(type: ANIME, genre_in: $genres, format: TV, sort: [SCORE_DESC], isAdult: false) {
          title { romaji english }
          episodes
          averageScore
          siteUrl
        }
      }
    }
    """

    result = await anilist_query(gql, {"genres": selected})
    if not result:
        await callback_query.message.reply_text("Ah, the API hit a snag. Try again later!")
        return

    results = result.get("Page", {}).get("media", [])
    if not results:
        await callback_query.message.reply_text("No TV anime found matching all those genres together.")
        return

    text = "**Top Rated Anime Matches (TV Series):**\n\n"
    for anime in results:
        title = anime["title"].get("english") or anime["title"].get("romaji", "Unknown")
        score = f'{anime.get("averageScore") / 10:.1f}' if anime.get("averageScore") else "N/A"
        episodes = anime.get("episodes") or "?"
        link = anime.get("siteUrl", "")
        text += f"• [{title}]({link}) (⭐ **{score}** | 🎬 {episodes} eps)\n"

    await callback_query.message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close Results", callback_data="close_menu")]]))


@app.on_callback_query(filters.regex(r"^close_menu$") & is_auth)
async def close_menu_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception as e:
        print(f"Error deleting menu: {e}")
