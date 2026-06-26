import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import inspect
from pyrogram import Client
print('client', Client)
print('start', Client.start)
print('stop', Client.stop)
print('start is coroutine', inspect.iscoroutinefunction(Client.start))
print('stop is coroutine', inspect.iscoroutinefunction(Client.stop))
print('start sig', inspect.signature(Client.start))
print('stop sig', inspect.signature(Client.stop))
print('run sig', inspect.signature(Client.run))
