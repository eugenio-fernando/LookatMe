"""
Data-access layer — todos, streak, and learning items.
Uses Prisma Client Python (sync) backed by SQLite.
"""

import json
import os
from datetime import datetime, timedelta

from prisma import Prisma

# Project root (two levels up from app/models/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Internal helpers ───────────────────────────────────────────────────

def _urgency_key(item: dict) -> tuple:
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    p = priority_rank.get(item.get("priority", "medium"), 1)
    due = item.get("due_date", "")
    if due:
        try:
            due_dt = datetime.strptime(due, "%Y-%m-%d").date()
            days = (due_dt - datetime.now().date()).days
        except Exception:
            days = 9999
    else:
        days = 9999
    return (days, p)


def _todo_to_dict(row) -> dict:
    return {
        "id":           row.id,
        "workspace_id": row.workspace_id,
        "created_by":   row.created_by,
        "user_id":      row.user_id,   # kept for backward-compat
        "timestamp":    row.timestamp,
        "text":         row.text,
        "priority":     row.priority,
        "due_date":     row.due_date,
        "completed":    row.completed,
    }


# ── Todos ──────────────────────────────────────────────────────────────

def get_todos(workspace_id: int) -> list[dict]:
    """Return all active todos for a workspace sorted by urgency."""
    with Prisma() as client:
        rows = client.todo.find_many(
            where={"workspace_id": workspace_id, "completed": False}
        )
    todos = [_todo_to_dict(r) for r in rows]
    return sorted(todos, key=_urgency_key)


def get_todos_today(workspace_id: int) -> list[dict]:
    """Return active todos due today or with no due date for a workspace."""
    today = datetime.now().date().isoformat()
    todos = get_todos(workspace_id)
    return [t for t in todos if not t["due_date"] or t["due_date"] <= today]


def get_todos_upcoming(workspace_id: int) -> list[dict]:
    """Return active todos with future due dates for a workspace."""
    today = datetime.now().date().isoformat()
    todos = get_todos(workspace_id)
    upcoming = [t for t in todos if t["due_date"] and t["due_date"] > today]
    return sorted(upcoming, key=lambda t: t["due_date"])


def create_todo(
    text: str,
    priority: str,
    due_date: str,
    timestamp: str,
    workspace_id: int,
    created_by: int,
) -> dict:
    with Prisma() as client:
        row = client.todo.create(data={
            "workspace_id": workspace_id,
            "created_by":   created_by,
            "user_id":      created_by,   # kept for backward-compat
            "text":         text,
            "priority":     priority,
            "due_date":     due_date,
            "timestamp":    timestamp,
        })
    return _todo_to_dict(row)


def get_todo_by_id(todo_id: int) -> dict | None:
    with Prisma() as client:
        row = client.todo.find_unique(where={"id": todo_id})
    return _todo_to_dict(row) if row else None


def delete_todo(todo_id: int) -> None:
    with Prisma() as client:
        client.todo.delete(where={"id": todo_id})


def complete_todo(todo_id: int) -> dict:
    """Mark a todo as completed and increment the daily streak. Returns updated streak."""
    with Prisma() as client:
        client.todo.update(where={"id": todo_id}, data={"completed": True})
    streak = get_streak()
    today = datetime.now().date().isoformat()
    if streak["last_completed_date"] == today:
        return streak
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    current = streak["current_streak"] + 1 if streak["last_completed_date"] == yesterday else 1
    longest = max(streak["longest_streak"], current)
    update_streak(current, today, longest)
    return get_streak()


# ── Streak ─────────────────────────────────────────────────────────────

def get_streak() -> dict:
    with Prisma() as client:
        row = client.streak.find_unique(where={"id": 1})
        if row is None:
            row = client.streak.create(data={"id": 1})
    return {
        "current_streak":      row.current_streak,
        "last_completed_date": row.last_completed_date,
        "longest_streak":      row.longest_streak,
    }


def update_streak(
    current_streak: int,
    last_completed_date: str,
    longest_streak: int,
) -> None:
    with Prisma() as client:
        client.streak.upsert(
            where={"id": 1},
            data={
                "create": {
                    "id":                   1,
                    "current_streak":       current_streak,
                    "last_completed_date":  last_completed_date,
                    "longest_streak":       longest_streak,
                },
                "update": {
                    "current_streak":       current_streak,
                    "last_completed_date":  last_completed_date,
                    "longest_streak":       longest_streak,
                },
            },
        )


# ── Learning Items ─────────────────────────────────────────────────────

def _learning_to_dict(row) -> dict:
    return {
        "id":            row.id,
        "title":         row.title,
        "category":      row.category,
        "progress":      row.progress,
        "hours_studied": row.hours_studied,
        "notes":         row.notes,
        "created_at":    row.created_at,
    }


def get_learning_items() -> list[dict]:
    with Prisma() as client:
        rows = client.learningitem.find_many(order={"created_at": "asc"})
    return [_learning_to_dict(r) for r in rows]


def create_learning_item(
    title: str,
    category: str,
    progress: int,
    hours_studied: float,
    notes: str,
    created_at: str,
) -> dict:
    with Prisma() as client:
        row = client.learningitem.create(data={
            "title":         title,
            "category":      category,
            "progress":      progress,
            "hours_studied": hours_studied,
            "notes":         notes,
            "created_at":    created_at,
        })
    return _learning_to_dict(row)


def update_learning_item(
    item_id: int,
    progress: int,
    hours_studied: float,
    notes: str,
) -> dict:
    with Prisma() as client:
        row = client.learningitem.update(
            where={"id": item_id},
            data={
                "progress":      progress,
                "hours_studied": hours_studied,
                "notes":         notes,
            },
        )
    return _learning_to_dict(row)


def delete_learning_item(item_id: int) -> None:
    with Prisma() as client:
        client.learningitem.delete(where={"id": item_id})


# ── Activity Feed ──────────────────────────────────────────────────────

def _activity_to_dict(row) -> dict:
    return {
        "id":         row.id,
        "user_id":    row.user_id,
        "type":       row.type,
        "content":    row.content,
        "created_at": row.created_at,
    }


def log_activity(user_id: int, type: str, content: str) -> dict:
    with Prisma() as client:
        row = client.activity.create(data={
            "user_id":    user_id,
            "type":       type,
            "content":    content,
            "created_at": datetime.now().isoformat(),
        })
    return _activity_to_dict(row)


def get_activity_feed(user_id: int, limit: int = 20) -> list[dict]:
    with Prisma() as client:
        rows = client.activity.find_many(
            where={"user_id": user_id},
            order={"id": "desc"},
            take=limit,
        )
    return [_activity_to_dict(r) for r in rows]


# ── Users ──────────────────────────────────────────────────────────────

def _user_to_dict(row) -> dict:
    """Public representation — never includes password_hash."""
    return {
        "id":           row.id,
        "email":        row.email,
        "verified":     row.verified,
        "created_at":   row.created_at,
        "display_name": row.display_name,
        "avatar_url":   row.avatar_url,
        "bio":          row.bio,
        "company":      row.company,
        "address":      row.address,
        "city":         row.city,
        "zip_code":     row.zip_code,
        "phone":        row.phone,
        "hobbies":      row.hobbies,
        "interests":    row.interests,
        "has_seen_onboarding":  row.has_seen_onboarding,
        "last_onboarding_seen": row.last_onboarding_seen,
    }


def create_user(email: str, password_hash: str, created_at: str) -> dict:
    with Prisma() as client:
        row = client.user.create(data={
            "email":         email,
            "password_hash": password_hash,
            "created_at":    created_at,
        })
    return _user_to_dict(row)


def get_user_by_email(email: str) -> dict | None:
    """Returns the full row including password_hash (needed for login)."""
    with Prisma() as client:
        row = client.user.find_unique(where={"email": email})
    if row is None:
        return None
    return {
        "id":            row.id,
        "email":         row.email,
        "password_hash": row.password_hash,
        "verified":      row.verified,
        "created_at":    row.created_at,
    }


def get_user_by_id(user_id: int) -> dict | None:
    """Returns public user dict without password_hash."""
    with Prisma() as client:
        row = client.user.find_unique(where={"id": user_id})
    if row is None:
        return None
    return _user_to_dict(row)


_PROFILE_FIELDS = {
    "display_name", "avatar_url", "bio", "company",
    "address", "city", "zip_code", "phone", "hobbies", "interests",
}


def update_profile(user_id: int, **fields) -> dict:
    """Update allowed profile fields for a user. Returns updated public dict."""
    data = {k: v for k, v in fields.items() if k in _PROFILE_FIELDS}
    with Prisma() as client:
        row = client.user.update(where={"id": user_id}, data=data)
    return _user_to_dict(row)


def update_password(user_id: int, password_hash: str) -> None:
    with Prisma() as client:
        client.user.update(where={"id": user_id}, data={"password_hash": password_hash})


# ── Token helpers (verification / magic login / password reset) ─────────

def set_verification_token(user_id: int, token: str, expiry: str) -> None:
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"verification_token": token, "verification_expiry": expiry},
        )


def get_user_by_verification_token(token: str) -> dict | None:
    with Prisma() as client:
        row = client.user.find_first(where={"verification_token": token})
    if row is None:
        return None
    d = _user_to_dict(row)
    d["verification_expiry"] = row.verification_expiry
    d["verified"] = row.verified
    return d


def mark_user_verified(user_id: int) -> None:
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"verified": True, "verification_token": None, "verification_expiry": None},
        )


def set_magic_login_token(user_id: int, token: str, expiry: str) -> None:
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"magic_login_token": token, "magic_login_expiry": expiry},
        )


def get_user_by_magic_token(token: str) -> dict | None:
    with Prisma() as client:
        row = client.user.find_first(where={"magic_login_token": token})
    if row is None:
        return None
    d = _user_to_dict(row)
    d["magic_login_expiry"] = row.magic_login_expiry
    return d


def clear_magic_token(user_id: int) -> None:
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"magic_login_token": None, "magic_login_expiry": None},
        )


def set_reset_token(user_id: int, token: str, expiry: str) -> None:
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"reset_token": token, "reset_expiry": expiry},
        )


def get_user_by_reset_token(token: str) -> dict | None:
    with Prisma() as client:
        row = client.user.find_first(where={"reset_token": token})
    if row is None:
        return None
    d = _user_to_dict(row)
    d["reset_expiry"] = row.reset_expiry
    return d


def clear_reset_token(user_id: int) -> None:
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"reset_token": None, "reset_expiry": None},
        )


def mark_onboarding_seen(user_id: int) -> None:
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"has_seen_onboarding": True},
        )


def update_onboarding_seen(user_id: int) -> None:
    """Record UTC timestamp when onboarding was last dismissed."""
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"last_onboarding_seen": datetime.utcnow().isoformat()},
        )


# ── Workspaces ─────────────────────────────────────────────────────────

def _workspace_to_dict(row) -> dict:
    return {"id": row.id, "name": row.name, "created_at": row.created_at}


def _member_to_dict(row, user: dict | None = None) -> dict:
    d = {"id": row.id, "workspace_id": row.workspace_id, "user_id": row.user_id, "role": row.role}
    if user:
        d["email"] = user.get("email", "")
        d["display_name"] = user.get("display_name", "")
    return d


def create_workspace(name: str, created_at: str) -> dict:
    with Prisma() as client:
        row = client.workspace.create(data={"name": name, "created_at": created_at})
    return _workspace_to_dict(row)


def get_workspace_by_id(workspace_id: int) -> dict | None:
    with Prisma() as client:
        row = client.workspace.find_unique(where={"id": workspace_id})
    return _workspace_to_dict(row) if row else None


def add_workspace_member(workspace_id: int, user_id: int, role: str = "member") -> None:
    with Prisma() as client:
        # Avoid duplicates
        existing = client.workspacemember.find_first(
            where={"workspace_id": workspace_id, "user_id": user_id}
        )
        if not existing:
            client.workspacemember.create(
                data={"workspace_id": workspace_id, "user_id": user_id, "role": role}
            )


def get_user_workspaces(user_id: int) -> list[dict]:
    """Return all workspaces a user belongs to."""
    with Prisma() as client:
        memberships = client.workspacemember.find_many(where={"user_id": user_id})
        ws_ids = [m.workspace_id for m in memberships]
        rows = client.workspace.find_many(where={"id": {"in": ws_ids}})
    return [_workspace_to_dict(r) for r in rows]


def get_workspace_members(workspace_id: int) -> list[dict]:
    """Return members of a workspace, enriched with user email/display_name."""
    with Prisma() as client:
        memberships = client.workspacemember.find_many(where={"workspace_id": workspace_id})
        user_ids = [m.user_id for m in memberships]
        users = {u.id: u for u in client.user.find_many(where={"id": {"in": user_ids}})}
    result = []
    for m in memberships:
        u = users.get(m.user_id)
        user_dict = {"email": u.email, "display_name": u.display_name} if u else None
        result.append(_member_to_dict(m, user_dict))
    return result


def is_workspace_member(workspace_id: int, user_id: int) -> bool:
    with Prisma() as client:
        row = client.workspacemember.find_first(
            where={"workspace_id": workspace_id, "user_id": user_id}
        )
    return row is not None


def get_workspace_role(workspace_id: int, user_id: int) -> str | None:
    with Prisma() as client:
        row = client.workspacemember.find_first(
            where={"workspace_id": workspace_id, "user_id": user_id}
        )
    return row.role if row else None


def invite_to_workspace(workspace_id: int, email: str) -> dict | None:
    """Find user by email and add them to the workspace as a member.
    Returns the new membership dict, or None if user not found."""
    user = get_user_by_email(email)
    if not user:
        return None
    add_workspace_member(workspace_id, user["id"], role="member")
    with Prisma() as client:
        row = client.workspacemember.find_first(
            where={"workspace_id": workspace_id, "user_id": user["id"]}
        )
    return _member_to_dict(row, {"email": user["email"], "display_name": user.get("display_name", "")})


# ── Messages ───────────────────────────────────────────────────────────

def _message_to_dict(row) -> dict:
    return {
        "id":           row.id,
        "sender_id":    row.sender_id,
        "recipient_id": row.recipient_id,
        "subject":      row.subject,
        "content":      row.content,
        "created_at":   row.created_at,
        "read":         row.read,
    }


def get_inbox(user_id: int) -> list[dict]:
    """Return messages received by user, newest first."""
    with Prisma() as client:
        rows = client.message.find_many(
            where={"recipient_id": user_id},
            order={"id": "desc"},
        )
    return [_message_to_dict(r) for r in rows]


def get_sent(user_id: int) -> list[dict]:
    """Return messages sent by user, newest first."""
    with Prisma() as client:
        rows = client.message.find_many(
            where={"sender_id": user_id},
            order={"id": "desc"},
        )
    return [_message_to_dict(r) for r in rows]


def create_message(
    sender_id: int,
    recipient_id: int,
    subject: str,
    content: str,
    created_at: str,
) -> dict:
    with Prisma() as client:
        row = client.message.create(data={
            "sender_id":    sender_id,
            "recipient_id": recipient_id,
            "subject":      subject,
            "content":      content,
            "created_at":   created_at,
        })
    return _message_to_dict(row)


def mark_message_read(message_id: int, user_id: int) -> dict | None:
    """Mark a message as read only if the caller is the recipient."""
    with Prisma() as client:
        row = client.message.find_unique(where={"id": message_id})
        if row is None or row.recipient_id != user_id:
            return None
        row = client.message.update(
            where={"id": message_id},
            data={"read": True},
        )
    return _message_to_dict(row)


def count_unread(user_id: int) -> int:
    with Prisma() as client:
        return client.message.count(where={"recipient_id": user_id, "read": False})


def get_all_users() -> list[dict]:
    """Return all users (id + email + display_name) for compose recipient list."""
    with Prisma() as client:
        rows = client.user.find_many(order={"email": "asc"})
    return [{"id": r.id, "email": r.email, "display_name": r.display_name} for r in rows]


# ── One-time JSON migration ────────────────────────────────────────────

def migrate_from_json_if_needed() -> None:
    with Prisma() as client:
        if client.todo.count() == 0:
            todos_path = os.path.join(BASE_DIR, "todos.json")
            if os.path.exists(todos_path):
                with open(todos_path, encoding="utf-8") as f:
                    legacy = json.load(f)
                for item in legacy:
                    client.todo.create(data={
                        "text":      item.get("text", ""),
                        "priority":  item.get("priority", "medium"),
                        "due_date":  item.get("due_date", ""),
                        "timestamp": item.get("timestamp", ""),
                    })

        if client.streak.find_unique(where={"id": 1}) is None:
            streak_path = os.path.join(BASE_DIR, "streak.json")
            data: dict = {}
            if os.path.exists(streak_path):
                with open(streak_path, encoding="utf-8") as f:
                    data = json.load(f)
            client.streak.create(data={
                "id":                   1,
                "current_streak":       data.get("current_streak", 0),
                "last_completed_date":  data.get("last_completed_date", ""),
                "longest_streak":       data.get("longest_streak", 0),
            })
