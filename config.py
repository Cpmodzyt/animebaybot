"""
Project configuration for the animebaybot.

Edit the placeholders below (`BOT_TOKEN`, `ADMIN_ID`, `STORAGE_CHANNEL`,
`API_ID` and `API_HASH`) before starting the bot on your VPS.
"""

import pytz

# Telegram API credentials (from my.telegram.org)
API_ID = 23023343
API_HASH = "2b79fd2d2c83173807a039325e7e166f"

# Bot token from @BotFather
# Replace the placeholder with your real token before running on the VPS
BOT_TOKEN = "<PUT_YOUR_BOT_TOKEN_HERE>"
BOT_USERNAME = "Test2cpbot"

# Storage channel (use a numeric id, like -1001234567890)
STORAGE_CHANNEL = -1003915426136

# Admin user id (replace with your Telegram user id)
ADMIN_ID = 123456789

# Behavior
DELETE_AFTER = 10 * 60

# Optional stickers used by the bot
RANDOM_STICKER_IDS = [
    "CAACAgIAAxkBAAERc_lqPrHjkYKmBYKYpj1pBhcTaJcP3AAC0hMAAtN88EvLRd2kOgb2sjwE",
    "CAACAgIAAxkBAAERc_dqPrHca1dnGYKlMhoHfaCwvYHbtAACHBQAAr8C-Eu4VGifF2XDXTwE",
]

ANILIST_URL = "https://graphql.anilist.co"
GENRES = [
    "Action", "Adventure", "Comedy", "Drama", "Ecchi", "Fantasy",
    "Horror", "Mahou Shoujo", "Mecha", "Music", "Mystery", "Psychological",
    "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller"
]

SL_TZ = pytz.timezone("Asia/Colombo")
SYNC_STATUS_FILE = ".sync_status"
