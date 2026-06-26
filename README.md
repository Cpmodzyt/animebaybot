# AnimebayBot

AnimebayBot is a Pyrogram-based Telegram bot for managing anime storage and delivery.
It supports admin staging, batch creation, automated season/quality grouping, searchable batch links, and premium user access.

## Features

- Admin staging of forwarded anime files
- Auto metadata parsing from filenames (`S01E01`, `Season 1`, `E01`, `1080p`, etc.)
- Admin-only `/batchlinks <English name>` command to generate separate batch links per season/quality/special group
- Smart search across English and original batch names
- Batch delivery with optional timed cleanup for non-authorized users
- Admin batch browsing with delete controls
- SQLite persistence for batch metadata, users, auth, watchlists, reminders, and requests

## Installation

1. Install Python 3.14 or newer.
2. Create a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```

## Configuration

Edit `config.py` and set:

- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `BOT_USERNAME`
- `ADMIN_ID`
- `STORAGE_CHANNEL`
- `DELETE_AFTER`
- `RANDOM_STICKER_IDS`

## Run the Bot

Start the bot with:

```bash
python run_bot.py
```

## Admin Commands

- `/batch <start> <end> <name>` — Create a batch from message IDs
- `/batchlinks <English name>` — Save staged admin-uploaded files and generate separate links per season/quality/special group
- `/batchsave <English name>` — Save all staged files as one batch
- `/batchcancel` — Cancel staged file upload
- `/listbatches` — Browse saved batches
- `/delete <code>` — Delete a saved batch by code

## User Commands

- `/search <name>` — Search batch by English or original name
- `/myfiles` — View/delete delivered files
- `/help` — Show available commands

## Notes

- Admin-only features require the sender to be authorized as an admin in `config.py`.
- Forward files to the bot first; use `/batchlinks <English name>` to create grouped batch links.
- If no season data is detected, files are grouped into a single batch.

## Files

- `run_bot.py` — Entrypoint for starting the bot
- `bot.py` — Bot initialization and client setup
- `handlers/batches.py` — Batch workflows, staging, search, delivery
- `config.py` — Bot credentials and constants
- `database.py` — SQLite schema and migrations
- `utils.py` — Shared helper functions
- `state.py` — Runtime staging and delete state
- `requirements.txt` — Python package dependencies
