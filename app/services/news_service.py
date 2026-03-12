"""Personalized news service with 15-minute in-memory caching."""

from __future__ import annotations

import os
import time
from typing import Any

import feedparser
import requests

CACHE_TTL_SECONDS = 15 * 60

# In-memory cache: key -> (timestamp, payload)
_NEWS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}

TOPIC_FEEDS: dict[str, list[tuple[str, str]]] = {
    "technology": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ],
    "politics": [
        ("BBC", "http://feeds.bbci.co.uk/news/politics/rss.xml"),
        ("NPR", "https://feeds.npr.org/1014/rss.xml"),
    ],
    "sports": [
        ("BBC Sport", "http://feeds.bbci.co.uk/sport/rss.xml"),
        ("ESPN", "https://www.espn.com/espn/rss/news"),
    ],
    "gaming": [
        ("IGN", "https://feeds.feedburner.com/ign/games-all"),
        ("Polygon", "https://www.polygon.com/rss/index.xml"),
    ],
    "business": [
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
        ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ],
}

TEAM_QUERIES: dict[str, str] = {
    "fc barcelona": "Barcelona football",
    "real madrid": "Real Madrid football",
    "manchester united": "Manchester United football",
}


def _cache_get(key: str) -> list[dict[str, Any]] | None:
    hit = _NEWS_CACHE.get(key)
    if not hit:
        return None
    ts, payload = hit
    if time.time() - ts > CACHE_TTL_SECONDS:
        _NEWS_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: list[dict[str, Any]]) -> None:
    _NEWS_CACHE[key] = (time.time(), payload)


def _normalize_item(source: str, title: str, link: str, image: str = "") -> dict[str, Any]:
    return {
        "headline": title,
        "image": image,
        "source": source,
        "link": link,
    }


def _parse_feeds(feeds: list[tuple[str, str]], limit: int = 12) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source, url in feeds:
        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": "LookAtMe/1.0"})
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:5]:
                media = ""
                if entry.get("media_content"):
                    media = entry.media_content[0].get("url", "")
                items.append(
                    _normalize_item(
                        source=source,
                        title=entry.get("title", "Untitled"),
                        link=entry.get("link", "#"),
                        image=media,
                    )
                )
        except Exception:
            continue
        if len(items) >= limit:
            break
    return items[:limit]


def fetch_news_by_topic(topic: str, limit: int = 12) -> list[dict[str, Any]]:
    """Fetch topic news, preferring NewsAPI when available, with RSS fallback."""
    norm_topic = (topic or "technology").strip().lower()
    cache_key = f"topic:{norm_topic}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    api_key = os.environ.get("NEWS_API_KEY", "").strip()
    payload: list[dict[str, Any]] = []

    # Prefer free NewsAPI key when configured.
    if api_key:
        try:
            res = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": norm_topic,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": min(limit, 20),
                    "apiKey": api_key,
                },
                timeout=8,
            )
            data = res.json() if res.ok else {}
            for article in data.get("articles", [])[:limit]:
                payload.append(
                    _normalize_item(
                        source=(article.get("source") or {}).get("name", "News"),
                        title=article.get("title", "Untitled"),
                        link=article.get("url", "#"),
                        image=article.get("urlToImage", "") or "",
                    )
                )
        except Exception:
            payload = []

    if not payload:
        feeds = TOPIC_FEEDS.get(norm_topic) or TOPIC_FEEDS["technology"]
        payload = _parse_feeds(feeds, limit=limit)

    _cache_set(cache_key, payload)
    return payload


def fetch_sports_news_by_team(team: str, limit: int = 8) -> list[dict[str, Any]]:
    """Fetch sports stories for a preferred team (RSS fallback by query mapping)."""
    norm_team = (team or "").strip().lower()
    cache_key = f"team:{norm_team}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    query = TEAM_QUERIES.get(norm_team, norm_team)
    api_key = os.environ.get("NEWS_API_KEY", "").strip()
    payload: list[dict[str, Any]] = []

    if api_key and query:
        try:
            res = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": min(limit, 20),
                    "apiKey": api_key,
                },
                timeout=8,
            )
            data = res.json() if res.ok else {}
            for article in data.get("articles", [])[:limit]:
                payload.append(
                    _normalize_item(
                        source=(article.get("source") or {}).get("name", "Sports"),
                        title=article.get("title", "Untitled"),
                        link=article.get("url", "#"),
                        image=article.get("urlToImage", "") or "",
                    )
                )
        except Exception:
            payload = []

    if not payload:
        payload = _parse_feeds(TOPIC_FEEDS["sports"], limit=limit)

    _cache_set(cache_key, payload)
    return payload
