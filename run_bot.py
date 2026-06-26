import asyncio

asyncio.set_event_loop(asyncio.new_event_loop())

from bot import app, main

if __name__ == "__main__":
    asyncio.run(main())
