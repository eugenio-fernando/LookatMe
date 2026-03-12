"""
Centralized activity event service.
"""

import logging

from ..extensions import socketio
from ..models import db

logger = logging.getLogger(__name__)


def _notify_handlers(event: dict) -> None:
    """
    Hook point for notification side-effects.
    Kept lightweight for now.
    """
    logger.info(
        "EVENT_NOTIFICATION_HOOK event_type=%s user_id=%s event_id=%s",
        event.get("event_type"), event.get("user_id"), event.get("id"),
    )


def record_event(user_id: int, event_type: str, description: str, metadata: dict | None = None) -> dict:
    """
    Store ActivityEvent and emit realtime update.
    """
    event = db.create_activity_event(
        user_id=user_id,
        event_type=event_type,
        description=description,
        metadata=metadata or {},
    )

    user = db.get_users_public_by_ids([user_id]).get(user_id, {})
    payload = {
        "event": {
            **event,
            "user_display_name": user.get("display_name") or "User",
            "user_avatar_url": user.get("avatar_url") or "",
        },
        "reactions": {"like": 0, "love": 0, "fire": 0, "clap": 0},
    }
    socketio.emit("activity:new", payload, to=f"user_{user_id}")
    _notify_handlers(event)
    return event
