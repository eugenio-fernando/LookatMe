"""
Centralized activity event service.
"""

import logging

from ..extensions import socketio
from ..models import db

logger = logging.getLogger(__name__)

EVENT_MESSAGES = {
    "session_started": "{username} started a new session",
    "task_added": "{username} added a task",
    "focus_completed": "{username} completed a focus session",
    "note_added": "{username} added a note",
    "challenge_started": "{username} started a challenge",
    "challenge_progress": "{username} updated challenge progress",
    "challenge_completed": "{username} completed a challenge",
    "message_sent": "{username} sent a message",
    "friend_joined": "{username} joined a friend circle",
    "space_created": "{username} created a new space",
    "space_joined": "{username} joined a space",
}


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
    user_obj = db.get_user_by_id(user_id) or {}
    username = (user_obj.get("display_name") or user_obj.get("email", "User").split("@")[0]).strip() or "User"
    template = EVENT_MESSAGES.get(event_type, "{username} " + (description or "did something"))
    message = template.format(username=username)
    payload_meta = metadata or {}
    visibility = str(payload_meta.get("visibility") or "space")
    space_id = payload_meta.get("space_id")
    if visibility == "space" and not isinstance(space_id, int):
        spaces = db.get_user_spaces(user_id)
        if spaces:
            space_id = spaces[0]["id"]

    event = db.create_activity_event(
        user_id=user_id,
        event_type=event_type,
        description=description or message,
        message=message,
        visibility=visibility,
        space_id=space_id if isinstance(space_id, int) else None,
        metadata=payload_meta,
    )

    user = db.get_users_public_by_ids([user_id]).get(user_id, {})
    payload = {
        "event": {
            **event,
            "user_display_name": user.get("display_name") or "User",
            "user_avatar_url": user.get("avatar_url") or "",
        },
        "reactions": {"like": 0, "love": 0, "fire": 0, "clap": 0},
        "reaction_users": {"like": [], "love": [], "fire": [], "clap": []},
    }
    if visibility == "public":
        socketio.emit("activity:new", payload)
    elif visibility == "space" and isinstance(space_id, int):
        members = db.get_space_members(space_id)
        recipient_ids = {m["user_id"] for m in members}
        recipient_ids.add(user_id)
        for recipient_id in recipient_ids:
            socketio.emit("activity:new", payload, to=f"user_{recipient_id}")
    else:
        socketio.emit("activity:new", payload, to=f"user_{user_id}")
    _notify_handlers(event)
    return event
