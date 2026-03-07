"""
Background tasks for Write it Down.

All tasks are registered on the Celery app created in app/celery_app.py.
Each task runs inside a Flask app context (via FlaskTask base class) so
Prisma and other Flask extensions are available.

Redis cache keys
----------------
news:<category>       — JSON list of news items, TTL 10 min
daily_verse           — JSON verse dict, TTL 24 h
reminder_sent:<uid>:<date> — idempotency guard, TTL until midnight
"""

import json
import os
import random
from datetime import datetime, timezone

import feedparser
import redis
import requests

from app.celery_app import celery

# ── Redis client (shared, thread-safe) ─────────────────────────────────────

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_redis: redis.Redis = redis.from_url(_redis_url, decode_responses=True)

# ── Feed URLs ───────────────────────────────────────────────────────────────

FEEDS: dict[str, list[tuple[str, str]]] = {
    "all": [
        ("BBC",        "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("CNN",        "http://rss.cnn.com/rss/edition_world.rss"),
        ("Guardian",   "https://www.theguardian.com/world/rss"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("NPR",        "https://feeds.npr.org/1004/rss.xml"),
    ],
    "world": [
        ("BBC",        "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Guardian",   "https://www.theguardian.com/world/rss"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ],
    "tech": [
        ("TechCrunch",  "https://techcrunch.com/feed/"),
        ("The Verge",   "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica","https://feeds.arstechnica.com/arstechnica/index"),
    ],
    "science": [
        ("BBC",           "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("NPR",           "https://feeds.npr.org/1007/rss.xml"),
        ("New Scientist", "https://www.newscientist.com/feed/home/"),
    ],
    "health": [
        ("BBC", "http://feeds.bbci.co.uk/news/health/rss.xml"),
        ("NPR", "https://feeds.npr.org/1128/rss.xml"),
    ],
    "business": [
        ("BBC",     "http://feeds.bbci.co.uk/news/business/rss.xml"),
        ("NPR",     "https://feeds.npr.org/1006/rss.xml"),
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
    ],
}

NEWS_CACHE_TTL  = 600    # 10 minutes
VERSE_CACHE_TTL = 86400  # 24 hours


# ── Task 1: Refresh news feed ───────────────────────────────────────────────

@celery.task(name="app.tasks.refresh_news_feed", bind=True, max_retries=3)
def refresh_news_feed(self, category: str = "all") -> dict:
    """
    Fetch RSS headlines for *category* and store the result in Redis under
    the key ``news:<category>`` with a 10-minute TTL.

    Retries up to 3 times with a 60-second back-off if all feeds fail.
    Returns a summary dict with the number of items cached.
    """
    feeds = FEEDS.get(category, FEEDS["all"])
    items = []

    for source, url in feeds:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:5]:
                items.append({
                    "source":      source,
                    "title":       entry.title,
                    "link":        entry.get("link", "#"),
                    "description": entry.get("summary", ""),
                    "category":    category,
                })
        except Exception:
            continue

    if not items:
        raise self.retry(countdown=60 * (self.request.retries + 1))

    random.shuffle(items)
    payload = items[:20]
    _redis.setex(f"news:{category}", NEWS_CACHE_TTL, json.dumps(payload))

    return {
        "category":     category,
        "cached":       len(payload),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Task 2: Generate and cache daily Bible verse ────────────────────────────

@celery.task(name="app.tasks.generate_daily_verse", bind=True, max_retries=3)
def generate_daily_verse(self) -> dict:
    """
    Fetch a random Bible verse from labs.bible.org and cache it in Redis
    under the key ``daily_verse`` with a 24-hour TTL.

    Falls back to a hard-coded verse when the API is unreachable after all
    retries so the cache always holds a valid entry.
    """
    verse: dict | None = None

    try:
        resp = requests.get(
            "https://labs.bible.org/api/?passage=random&type=json",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()[0]
            verse = {
                "text":      data["text"],
                "reference": f"{data['bookname']} {data['chapter']}:{data['verse']}",
            }
    except Exception:
        pass

    if verse is None:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)
        verse = {
            "text":      "The Lord is my shepherd; I shall not want.",
            "reference": "Psalm 23:1",
        }

    _redis.setex("daily_verse", VERSE_CACHE_TTL, json.dumps(verse))
    return {"cached": True, "reference": verse["reference"]}


# ── Task 3: Send notification reminders ────────────────────────────────────

@celery.task(name="app.tasks.send_notification_reminders")
def send_notification_reminders() -> dict:
    """
    For every user who has tasks with a due date of *today*, create an
    internal inbox message summarising what is outstanding.

    Uses sender_id=0 (system). The Message model has no FK constraint on
    sender_id so this is safe with the current SQLite/Prisma schema.

    An idempotency guard (Redis key ``reminder_sent:<uid>:<date>``) ensures
    each user receives at most one reminder per calendar day even if the task
    is triggered multiple times.
    """
    from app.models import db  # import inside task to stay within app context

    today = datetime.now(timezone.utc).date().isoformat()
    now_ts = datetime.now(timezone.utc).isoformat()
    sent = 0
    skipped = 0

    for user in db.get_all_users():
        user_id = user["id"]

        # One reminder per user per day.
        guard_key = f"reminder_sent:{user_id}:{today}"
        if _redis.exists(guard_key):
            skipped += 1
            continue

        # Only tasks explicitly due today (exclude "no due date" tasks).
        due_today: list[dict] = []
        for ws in db.get_user_workspaces(user_id):
            todos = db.get_todos_today(ws["id"])
            due_today.extend(t for t in todos if t.get("due_date") == today)

        if not due_today:
            continue

        task_lines = "\n".join(f"• {t['text']}" for t in due_today[:5])
        body = f"You have {len(due_today)} task(s) due today:\n\n{task_lines}"
        if len(due_today) > 5:
            body += f"\n…and {len(due_today) - 5} more."

        db.create_message(
            sender_id=0,
            recipient_id=user_id,
            subject=f"Reminder: {len(due_today)} task(s) due today",
            content=body,
            created_at=now_ts,
        )

        # Guard expires at end of UTC day.
        now_utc = datetime.now(timezone.utc)
        midnight = now_utc.replace(hour=23, minute=59, second=59, microsecond=0)
        ttl = max(1, int((midnight - now_utc).total_seconds()) + 1)
        _redis.setex(guard_key, ttl, "1")
        sent += 1

    return {"reminders_sent": sent, "skipped": skipped, "date": today}
