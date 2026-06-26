import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import inspect
from pyrogram import Client

print('Client.run source:')
print(inspect.getsource(Client.run))
print('---')
print('Client.start source:')
print(inspect.getsource(Client.start))
print('---')
print('Client.stop source:')
print(inspect.getsource(Client.stop))
