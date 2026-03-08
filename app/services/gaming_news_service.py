"""Gaming news service with 15-minute in-memory caching."""

from __future__ import annotations

import time
from typing import Any

import feedparser
import requests

CACHE_TTL_SECONDS = 15 * 60
_STEAM_APP_ID = 730  # Counter-Strike 2 as an always-active Steam news source

_GAMING_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}

RSS_SOURCES: list[tuple[str, str]] = [
    ("IGN", "https://feeds.feedburner.com/ign/games-all"),
    ("GameSpot", "https://www.gamespot.com/feeds/mashup/"),
    ("Polygon", "https://www.polygon.com/rss/index.xml"),
]


def _cache_get(key: str) -> list[dict[str, Any]] | None:
    hit = _GAMING_CACHE.get(key)
    if not hit:
        return None
    ts, payload = hit
    if time.time() - ts > CACHE_TTL_SECONDS:
        _GAMING_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: list[dict[str, Any]]) -> None:
    _GAMING_CACHE[key] = (time.time(), payload)


def fetch_gaming_news(limit: int = 10) -> list[dict[str, Any]]:
    """Aggregate Steam + major gaming RSS headlines into a normalized payload."""
    cache_key = f"gaming:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items: list[dict[str, Any]] = []

    # Steam API source.
    try:
        res = requests.get(
            "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/",
            params={"appid": _STEAM_APP_ID, "count": 5, "maxlength": 0},
            timeout=8,
        )
        data = res.json() if res.ok else {}
        for entry in data.get("appnews", {}).get("newsitems", [])[:5]:
            items.append(
                {
                    "game_title": "Steam",
                    "headline": entry.get("title", "Untitled"),
                    "thumbnail": "",
                    "source": "Steam",
                    "link": entry.get("url", "#"),
                }
            )
    except Exception:
        pass

    # RSS fallback/extra sources.
    for source, url in RSS_SOURCES:
        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": "LookAtMe/1.0"})
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:3]:
                thumb = ""
                if entry.get("media_content"):
                    thumb = entry.media_content[0].get("url", "")
                items.append(
                    {
                        "game_title": source,
                        "headline": entry.get("title", "Untitled"),
                        "thumbnail": thumb,
                        "source": source,
                        "link": entry.get("link", "#"),
                    }
                )
        except Exception:
            continue
        if len(items) >= limit:
            break

    payload = items[:limit]
    _cache_set(cache_key, payload)
    return payload
