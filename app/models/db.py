"""
Data-access layer — todos, streak, and learning items.
Uses Prisma Client Python (sync) backed by SQLite.
"""

import json
import os
from datetime import datetime, timedelta

from prisma import Prisma
from ..services.welcome_service import build_fun_welcome

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


def _update_user_streak(user_id: int) -> bool:
    """Increment the per-user streak fields on the User row.
    Returns True if this is the first streak update today (habit milestone)."""
    today     = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    with Prisma() as client:
        user = client.user.find_unique(where={"id": user_id})
        if not user:
            return False
        last = user.last_completed_date or ""
        if last == today:
            return False  # already incremented today
        current = (user.current_streak + 1) if last == yesterday else 1
        longest = max(user.longest_streak, current)
        client.user.update(
            where={"id": user_id},
            data={
                "current_streak":      current,
                "longest_streak":      longest,
                "last_completed_date": today,
            },
        )
    return True  # first completion of the day = habit milestone


def complete_todo(todo_id: int, user_id: int | None = None) -> dict:
    """Mark a todo as completed. Updates global streak and, if user_id given, per-user streak."""
    with Prisma() as client:
        client.todo.update(where={"id": todo_id}, data={"completed": True})
    # Global streak (existing behaviour)
    streak    = get_streak()
    today     = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    if streak["last_completed_date"] != today:
        current = streak["current_streak"] + 1 if streak["last_completed_date"] == yesterday else 1
        longest = max(streak["longest_streak"], current)
        update_streak(current, today, longest)
    # Per-user streak — also logs habit_completed on first completion of the day
    if user_id is not None:
        habit_milestone = _update_user_streak(user_id)
        if habit_milestone:
            log_activity(user_id, "habit_completed", "Kept your streak alive 🔥")
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
        "gender":       row.gender,
        "has_seen_onboarding":  row.has_seen_onboarding,
        "last_onboarding_seen": row.last_onboarding_seen,
        "current_streak":       row.current_streak,
        "longest_streak":       row.longest_streak,
        "last_completed_date":  row.last_completed_date,
        "linkedin_url":         row.linkedin_url,
        "linkedin_verified":    row.linkedin_verified,
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
    "address", "city", "zip_code", "phone", "hobbies", "interests", "gender",
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


# ── LinkedIn Verification ───────────────────────────────────────────────

def set_linkedin_verification(user_id: int, url: str, code: str) -> None:
    """Store LinkedIn URL and verification code; reset verified flag."""
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={
                "linkedin_url":               url,
                "linkedin_verification_code": code,
                "linkedin_verified":          False,
            },
        )


def get_linkedin_verification_code(user_id: int) -> str | None:
    with Prisma() as client:
        user = client.user.find_unique(where={"id": user_id})
    return user.linkedin_verification_code if user else None


def set_linkedin_verified(user_id: int) -> None:
    """Mark the user's LinkedIn as verified and clear the verification code."""
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={
                "linkedin_verified":          True,
                "linkedin_verification_code": None,
                "linkedin_verify_attempts":   0,
            },
        )


def get_linkedin_attempts(user_id: int) -> int:
    with Prisma() as client:
        user = client.user.find_unique(where={"id": user_id})
    return user.linkedin_verify_attempts if user else 0


def increment_linkedin_attempts(user_id: int) -> None:
    with Prisma() as client:
        user = client.user.find_unique(where={"id": user_id})
        if user:
            client.user.update(
                where={"id": user_id},
                data={"linkedin_verify_attempts": user.linkedin_verify_attempts + 1},
            )


# ── Daily Commitment ────────────────────────────────────────────────────

def get_commitment(user_id: int) -> dict:
    """Return today's commitment, auto-resetting if it belongs to a past day."""
    today = datetime.now().date().isoformat()
    with Prisma() as client:
        user = client.user.find_unique(where={"id": user_id})
        if not user:
            return {"text": None, "completed": False}
        if user.daily_commitment and user.daily_commitment_date != today:
            client.user.update(
                where={"id": user_id},
                data={
                    "daily_commitment":           None,
                    "daily_commitment_date":      None,
                    "daily_commitment_completed": False,
                },
            )
            return {"text": None, "completed": False}
        if user.daily_commitment_date != today:
            return {"text": None, "completed": False}
        return {
            "text":      user.daily_commitment,
            "completed": user.daily_commitment_completed,
        }


def set_commitment(user_id: int, text: str) -> dict:
    """Create or replace today's commitment."""
    today = datetime.now().date().isoformat()
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={
                "daily_commitment":           text.strip(),
                "daily_commitment_date":      today,
                "daily_commitment_completed": False,
            },
        )
    return {"text": text.strip(), "completed": False}


def complete_commitment(user_id: int) -> dict:
    """Mark the current daily commitment as completed."""
    with Prisma() as client:
        client.user.update(
            where={"id": user_id},
            data={"daily_commitment_completed": True},
        )
    return {"completed": True}


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


def get_leaderboard(workspace_id: int) -> list[dict]:
    """Return workspace members sorted by current_streak desc, tasks_today desc."""
    today = datetime.now().date().isoformat()
    with Prisma() as client:
        memberships = client.workspacemember.find_many(where={"workspace_id": workspace_id})
        user_ids    = [m.user_id for m in memberships]
        users       = {u.id: u for u in client.user.find_many(where={"id": {"in": user_ids}})}
        # Fetch today's task_completed activities for all members
        activities  = client.activity.find_many(
            where={"user_id": {"in": user_ids}, "type": "task_completed"},
        )

    tasks_today: dict[int, int] = {}
    for a in activities:
        if a.created_at.startswith(today):
            tasks_today[a.user_id] = tasks_today.get(a.user_id, 0) + 1

    result = []
    for uid in user_ids:
        u = users.get(uid)
        if not u:
            continue
        name = u.display_name.strip() or u.email.split("@")[0]
        result.append({
            "user_id":        u.id,
            "name":           name,
            "current_streak": u.current_streak or 0,
            "longest_streak": u.longest_streak or 0,
            "tasks_today":    tasks_today.get(uid, 0),
        })

    return sorted(result, key=lambda x: (-x["current_streak"], -x["tasks_today"]))


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


# ── Workspace Invites ──────────────────────────────────────────────────

def _invite_to_dict(row) -> dict:
    return {
        "id": row.id, "workspace_id": row.workspace_id,
        "email": row.email, "token": row.token,
        "created_at": row.created_at, "expires_at": row.expires_at,
        "accepted": row.accepted,
    }


def create_workspace_invite(workspace_id: int, email: str, token: str, expires_at: str) -> dict:
    with Prisma() as client:
        row = client.workspaceinvite.create(data={
            "workspace_id": workspace_id,
            "email":        email,
            "token":        token,
            "created_at":   datetime.utcnow().isoformat(),
            "expires_at":   expires_at,
        })
    return _invite_to_dict(row)


def get_workspace_invite(token: str) -> dict | None:
    with Prisma() as client:
        row = client.workspaceinvite.find_first(
            where={"token": token, "accepted": False}
        )
    return _invite_to_dict(row) if row else None


def consume_workspace_invite(token: str) -> None:
    with Prisma() as client:
        client.workspaceinvite.update(
            where={"token": token},
            data={"accepted": True},
        )


# ── Weekly Activity ────────────────────────────────────────────────────

def get_weekly_activity(user_id: int) -> dict:
    """Return task/habit/note counts for the past 7 days (today inclusive)."""
    today      = datetime.now().date()
    week_start = (today - timedelta(days=6)).isoformat()
    with Prisma() as client:
        activities = client.activity.find_many(where={"user_id": user_id})
    tasks  = sum(1 for a in activities if a.type == "task_completed"  and a.created_at[:10] >= week_start)
    habits = sum(1 for a in activities if a.type == "habit_completed" and a.created_at[:10] >= week_start)
    notes  = sum(1 for a in activities if a.type == "note_created"    and a.created_at[:10] >= week_start)
    return {
        "tasks_completed":  tasks,
        "habits_completed": habits,
        "notes_written":    notes,
        "week_start":       week_start,
        "week_end":         today.isoformat(),
    }


# ── Daily Mission ──────────────────────────────────────────────────────

def get_mission_with_progress(user_id: int) -> dict:
    """Get or create today's mission and compute live progress from Activity records."""
    today = datetime.now().date().isoformat()
    with Prisma() as client:
        row = client.dailymission.find_first(
            where={"user_id": user_id, "date": today}
        )
        if row is None:
            row = client.dailymission.create(data={
                "user_id":     user_id,
                "date":        today,
                "tasks_goal":  3,
                "habits_goal": 1,
                "notes_goal":  1,
            })
        mission_id       = row.id
        tasks_goal       = row.tasks_goal
        habits_goal      = row.habits_goal
        notes_goal       = row.notes_goal
        already_complete = row.completed
        activities = client.activity.find_many(where={"user_id": user_id})

    tasks_done  = sum(1 for a in activities if a.type == "task_completed"  and a.created_at.startswith(today))
    habits_done = sum(1 for a in activities if a.type == "habit_completed" and a.created_at.startswith(today))
    notes_done  = sum(1 for a in activities if a.type == "note_created"    and a.created_at.startswith(today))

    all_done  = tasks_done >= tasks_goal and habits_done >= habits_goal and notes_done >= notes_goal
    completed = already_complete or all_done

    if all_done and not already_complete:
        with Prisma() as client:
            client.dailymission.update(where={"id": mission_id}, data={"completed": True})

    return {
        "id":          mission_id,
        "user_id":     user_id,
        "date":        today,
        "tasks_goal":  tasks_goal,
        "habits_goal": habits_goal,
        "notes_goal":  notes_goal,
        "completed":   completed,
        "tasks_done":  min(tasks_done,  tasks_goal),
        "habits_done": min(habits_done, habits_goal),
        "notes_done":  min(notes_done,  notes_goal),
    }


# ── AI Usage ───────────────────────────────────────────────────────────

def count_ai_usage_today(user_id: int) -> int:
    """Return the number of successful AI requests made by user_id today."""
    today = datetime.now().date().isoformat()
    with Prisma() as client:
        return client.aiusage.count(where={"user_id": user_id, "date": today})


def log_ai_usage(user_id: int, request_type: str) -> None:
    """Record one successful AI request. Only call this after OpenAI responds successfully."""
    today = datetime.now().date().isoformat()
    with Prisma() as client:
        client.aiusage.create(data={
            "user_id":      user_id,
            "date":         today,
            "request_type": request_type,
            "created_at":   datetime.now().isoformat(),
        })


# ── AI Response Cache ──────────────────────────────────────────────────

def get_cached_ai_response(user_id: int, cache_type: str) -> dict | None:
    """Return cached AI response if one exists for today and is within 6 hours."""
    today  = datetime.now().date().isoformat()
    cutoff = (datetime.now() - timedelta(hours=6)).isoformat()
    with Prisma() as client:
        row = client.airesponsecache.find_first(
            where={"user_id": user_id, "type": cache_type, "date": today}
        )
    if row is None or row.created_at < cutoff:
        return None
    try:
        return json.loads(row.response)
    except Exception:
        return None


def cache_ai_response(user_id: int, cache_type: str, response: dict) -> None:
    """Upsert an AI response into the cache for today."""
    today = datetime.now().date().isoformat()
    now   = datetime.now().isoformat()
    with Prisma() as client:
        existing = client.airesponsecache.find_first(
            where={"user_id": user_id, "type": cache_type, "date": today}
        )
        if existing:
            client.airesponsecache.update(
                where={"id": existing.id},
                data={"response": json.dumps(response), "created_at": now},
            )
        else:
            client.airesponsecache.create(data={
                "user_id":    user_id,
                "type":       cache_type,
                "date":       today,
                "response":   json.dumps(response),
                "created_at": now,
            })


# ── Social Invitations ─────────────────────────────────────────────────

def create_social_invitation(sender_id: int, method: str, token: str) -> dict:
    now = datetime.now().isoformat()
    with Prisma() as client:
        row = client.invitation.create(data={
            "sender_id":  sender_id,
            "token":      token,
            "method":     method,
            "created_at": now,
        })
    return {"id": row.id, "token": row.token, "method": row.method}


def get_social_invitation(token: str) -> dict | None:
    with Prisma() as client:
        row = client.invitation.find_unique(where={"token": token})
    if not row:
        return None
    return {
        "id":                row.id,
        "sender_id":         row.sender_id,
        "token":             row.token,
        "method":            row.method,
        "created_at":        row.created_at,
        "opened_at":         row.opened_at,
        "accepted_at":       row.accepted_at,
        "recipient_user_id": row.recipient_user_id,
    }


def open_social_invitation(token: str) -> None:
    """Set opened_at once (idempotent)."""
    now = datetime.now().isoformat()
    with Prisma() as client:
        row = client.invitation.find_unique(where={"token": token})
        if row and not row.opened_at:
            client.invitation.update(
                where={"token": token},
                data={"opened_at": now},
            )


def accept_social_invitation(
    token: str,
    recipient_user_id: int,
    invitee_email: str | None = None,
) -> bool:
    """Mark accepted and create friendship. Returns False if already used."""
    now = datetime.now().isoformat()
    with Prisma() as client:
        row = client.invitation.find_unique(where={"token": token})
        if not row or row.accepted_at or row.recipient_user_id:
            return False
        update_data: dict = {"accepted_at": now, "recipient_user_id": recipient_user_id}
        if invitee_email:
            update_data["invitee_email"] = invitee_email
        client.invitation.update(where={"token": token}, data=update_data)
        # Create friendship if it doesn't already exist
        existing = client.friendship.find_first(where={
            "OR": [
                {"user_a": row.sender_id, "user_b": recipient_user_id},
                {"user_a": recipient_user_id, "user_b": row.sender_id},
            ]
        })
        if not existing:
            client.friendship.create(data={
                "user_a":      row.sender_id,
                "user_b":      recipient_user_id,
                "created_at":  now,
                "accepted_at": now,
            })
    return True


def get_user_invitations(user_id: int) -> list[dict]:
    """List all invitations sent by a user, with recipient name/email if accepted."""
    with Prisma() as client:
        rows = client.invitation.find_many(
            where={"sender_id": user_id},
            order={"created_at": "desc"},
        )
        recipient_ids = [r.recipient_user_id for r in rows if r.recipient_user_id]
        recipients: dict[int, dict] = {}
        if recipient_ids:
            users = client.user.find_many(where={"id": {"in": recipient_ids}})
            recipients = {
                u.id: {"name": u.display_name or u.email.split("@")[0], "email": u.email}
                for u in users
            }
    return [
        {
            "id":             row.id,
            "method":         row.method,
            "created_at":     row.created_at,
            "opened_at":      row.opened_at,
            "accepted_at":    row.accepted_at,
            "invitee_email":  row.invitee_email or (
                recipients[row.recipient_user_id]["email"]
                if row.recipient_user_id and row.recipient_user_id in recipients
                else None
            ),
            "recipient_name": (
                recipients[row.recipient_user_id]["name"]
                if row.recipient_user_id and row.recipient_user_id in recipients
                else None
            ),
        }
        for row in rows
    ]


# ── Friendships ─────────────────────────────────────────────────────────

def get_friends(user_id: int) -> list[dict]:
    """Return social friends (via Friendship model) with name + streak."""
    with Prisma() as client:
        friendships = client.friendship.find_many(where={
            "OR": [{"user_a": user_id}, {"user_b": user_id}]
        })
        friend_ids = [
            f.user_b if f.user_a == user_id else f.user_a
            for f in friendships
        ]
        friendship_dates = {
            (f.user_b if f.user_a == user_id else f.user_a): f.created_at
            for f in friendships
        }
        if not friend_ids:
            return []
        users = client.user.find_many(where={"id": {"in": friend_ids}})
    return [
        {
            "id":                u.id,
            "name":              u.display_name or u.email.split("@")[0],
            "display_name":      u.display_name,
            "email":             u.email,
            "current_streak":    u.current_streak,
            "streak":            u.current_streak,
            "last_active":       u.last_completed_date,
            "linkedin_verified": u.linkedin_verified,
            "friends_since":     friendship_dates.get(u.id),
        }
        for u in users
    ]


def get_friends_with_stats(user_id: int) -> list[dict]:
    """Return friends enriched with tasks_today, tasks_this_week, and last_login."""
    today      = datetime.now().date().isoformat()
    week_start = (datetime.now().date() - timedelta(days=datetime.now().weekday())).isoformat()

    with Prisma() as client:
        friendships = client.friendship.find_many(where={
            "OR": [{"user_a": user_id}, {"user_b": user_id}]
        })
        friend_ids = [
            f.user_b if f.user_a == user_id else f.user_a
            for f in friendships
        ]
        friendship_dates = {
            (f.user_b if f.user_a == user_id else f.user_a): f.created_at
            for f in friendships
        }
        if not friend_ids:
            return []

        users = client.user.find_many(where={"id": {"in": friend_ids}})
        activities = client.activity.find_many(where={
            "user_id": {"in": friend_ids},
            "type":    "task_completed",
        })

    tasks_today: dict[int, int] = {}
    tasks_week:  dict[int, int] = {}
    for a in activities:
        if a.created_at.startswith(today):
            tasks_today[a.user_id] = tasks_today.get(a.user_id, 0) + 1
        if a.created_at[:10] >= week_start:
            tasks_week[a.user_id] = tasks_week.get(a.user_id, 0) + 1

    result = [
        {
            "id":              u.id,
            "name":            u.display_name or u.email.split("@")[0],
            "current_streak":  u.current_streak or 0,
            "longest_streak":  u.longest_streak or 0,
            "last_login_at":   u.last_login_at or "",
            "last_active":     u.last_completed_date or "",
            "tasks_today":     tasks_today.get(u.id, 0),
            "tasks_this_week": tasks_week.get(u.id, 0),
            "friends_since":   friendship_dates.get(u.id),
            "linkedin_verified": u.linkedin_verified,
        }
        for u in users
    ]
    return sorted(result, key=lambda x: (-x["current_streak"], -x["tasks_this_week"]))


def get_user_stats_for_leaderboard(user_id: int) -> dict | None:
    """Return a single user's leaderboard-compatible stats dict."""
    today      = datetime.now().date().isoformat()
    week_start = (datetime.now().date() - timedelta(days=datetime.now().weekday())).isoformat()
    with Prisma() as client:
        user = client.user.find_unique(where={"id": user_id})
        if not user:
            return None
        activities = client.activity.find_many(where={
            "user_id": user_id,
            "type":    "task_completed",
        })
    tasks_today = sum(1 for a in activities if a.created_at.startswith(today))
    tasks_week  = sum(1 for a in activities if a.created_at[:10] >= week_start)
    return {
        "id":              user.id,
        "name":            user.display_name or user.email.split("@")[0],
        "current_streak":  user.current_streak or 0,
        "longest_streak":  user.longest_streak or 0,
        "last_login_at":   user.last_login_at or "",
        "last_active":     user.last_completed_date or "",
        "tasks_today":     tasks_today,
        "tasks_this_week": tasks_week,
    }


def update_last_login(user_id: int) -> None:
    """Stamp last_login_at for a user after a successful authentication."""
    now = datetime.now().isoformat()
    with Prisma() as client:
        client.user.update(where={"id": user_id}, data={"last_login_at": now})


def record_login_and_get_welcome(user_id: int) -> dict | None:
    """Track per-day login count and return a playful message for first 3 logins."""
    now = datetime.now()
    day_key = now.date().isoformat()

    with Prisma() as client:
        user = client.user.find_unique(where={"id": user_id})
        if not user:
            return None

        count = user.welcome_count_today if (user.welcome_day_key or "") == day_key else 0
        count += 1

        client.user.update(
            where={"id": user_id},
            data={
                "last_login_at": now.isoformat(),
                "welcome_day_key": day_key,
                "welcome_count_today": count,
            },
        )

        if count > 3:
            return None

        display_name = (user.display_name or user.email.split("@")[0]).strip()
        message = build_fun_welcome(display_name, user.gender or "prefer_not_to_say", count)
        return {"message": message, "count_today": count}


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
