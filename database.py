import sqlite3

# SQLite database connection shared across the bot
# check_same_thread=False is required for async usage from multiple tasks.
db = sqlite3.connect("batch.db", check_same_thread=False)
cursor = db.cursor()

# Create required tables and migrate safely when needed.
def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batches(
        code TEXT PRIMARY KEY,
        name TEXT DEFAULT '',
        original_name TEXT DEFAULT '',
        start_id INTEGER,
        end_id INTEGER,
        message_ids TEXT DEFAULT '',
        quality TEXT DEFAULT '',
        episode_range TEXT DEFAULT '',
        file_count INTEGER DEFAULT 0,
        fetch_count INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auth_users(
        user_id INTEGER PRIMARY KEY
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        first_name TEXT DEFAULT '',
        last_seen INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        done INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        chat_id INTEGER,
        text TEXT,
        remind_at INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        user_id INTEGER PRIMARY KEY
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS requests(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_id INTEGER,
        title       TEXT,
        status      TEXT DEFAULT 'pending',
        acted_by    INTEGER,
        acted_name  TEXT,
        created_at  INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS request_msgs(
        request_id  INTEGER,
        admin_id    INTEGER,
        message_id  INTEGER,
        PRIMARY KEY (request_id, admin_id)
    )
    """)

    db.commit()

    # Migrate: add columns if they do not exist yet.
    try:
        cursor.execute("ALTER TABLE batches ADD COLUMN original_name TEXT DEFAULT ''")
        db.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE batches ADD COLUMN message_ids TEXT DEFAULT ''")
        db.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE batches ADD COLUMN quality TEXT DEFAULT ''")
        db.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE batches ADD COLUMN episode_range TEXT DEFAULT ''")
        db.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE batches ADD COLUMN file_count INTEGER DEFAULT 0")
        db.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE batches ADD COLUMN fetch_count INTEGER DEFAULT 0")
        db.commit()
    except Exception:
        pass


init_db()
