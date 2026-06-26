import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
from pyrogram.client import Client

session_name = 'tmp_new_bot_token2'
app = Client(session_name, api_id=31413348, api_hash='be555bc98b4398a2f04ba02b6268615c', bot_token='8449623611:AAFC4_OvrVeWVrsJcHOXD-N4gD_XpzvXaBc')
try:
    app.start()
    me = app.get_me()
    print(me.id, me.username, me.first_name)
finally:
    app.stop()
