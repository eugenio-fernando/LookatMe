"""
Activity feed service.
"""

import logging

from ..models import db
from .event_service import record_event as record_activity_event

logger = logging.getLogger(__name__)

_ALLOWED_EVENTS = {
    "focus_completed",
    "reminder_added",
    "challenge_started",
    "friend_joined",
    "message_sent",
}


def record_event(user_id: int, event_type: str, description: str, metadata: dict | None = None) -> dict | None:
    """
    Record a normalized activity event for the social feed.
    Falls back to legacy activity storage when ActivityEvent is unavailable.
    """
    if event_type not in _ALLOWED_EVENTS:
        logger.warning("ACTIVITY_EVENT_IGNORED type=%s user_id=%s", event_type, user_id)
        return None

    try:
        return record_activity_event(
            user_id=user_id,
            event_type=event_type,
            description=description,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning("ACTIVITY_EVENT_FALLBACK type=%s user_id=%s err=%s", event_type, user_id, exc)
        legacy = db.log_activity(user_id, event_type, description)
        return {
            "id": legacy["id"],
            "user_id": legacy["user_id"],
            "event_type": legacy["type"],
            "description": legacy["content"],
            "created_at": legacy["created_at"],
            "metadata": metadata or {},
        }


def get_feed_for_user(user_id: int, limit: int = 20) -> list[dict]:
    """
    Return feed events enriched with user display_name + avatar.
    """
    limit = max(1, min(limit, 50))
    try:
        events = db.get_activity_event_feed_for_user(user_id, limit=limit)
    except Exception as exc:
        logger.warning("ACTIVITY_FEED_FALLBACK user_id=%s err=%s", user_id, exc)
        rows = db.get_activity_feed(user_id, limit=limit)
        events = [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "event_type": r["type"],
                "description": r["content"],
                "created_at": r["created_at"],
                "metadata": {},
            }
            for r in rows
        ]

    users = db.get_users_public_by_ids(list({e["user_id"] for e in events}))
    reaction_counts = db.get_reaction_counts_for_event_ids([e["id"] for e in events])
    result = []
    for item in events:
        u = users.get(item["user_id"]) or {}
        event = {
            **item,
            "user_display_name": u.get("display_name") or "User",
            "user_avatar_url": u.get("avatar_url") or "",
        }
        result.append({
            "event": event,
            "reactions": reaction_counts.get(
                item["id"], {"like": 0, "love": 0, "fire": 0, "clap": 0}
            ),
        })
    return result
