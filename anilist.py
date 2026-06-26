import aiohttp
from config import ANILIST_URL, GENRES


async def anilist_query(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ANILIST_URL, json=payload) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("data")
    except Exception:
        return None


def genre_to_cb(genre):
    return genre.replace(" ", "_")


def cb_to_genre(cb):
    return cb.replace("_", " ")


__all__ = [
    "anilist_query",
    "GENRES",
    "genre_to_cb",
    "cb_to_genre",
]
