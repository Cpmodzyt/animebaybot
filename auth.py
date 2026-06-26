from pyrogram import filters
from database import cursor
from config import ADMIN_ID


def is_admin(user_id):
    if user_id == ADMIN_ID:
        return True
    cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None


def is_authorized(user_id):
    if is_admin(user_id):
        return True
    cursor.execute("SELECT 1 FROM auth_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None


async def check_auth_filter(_, __, update):
    if not getattr(update, "from_user", None):
        return False
    return is_authorized(update.from_user.id)


is_auth = filters.create(check_auth_filter)
