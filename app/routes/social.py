"""
Social accountability system — invitations and friendships.
"""

import logging
import os
import secrets
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..models import db
from ..services.activity_service import record_event
from ..services.email_service import send_friend_invite_email
from ..utils import api_login_required

social_bp = Blueprint("social", __name__)
logger = logging.getLogger(__name__)

_VALID_METHODS = {"whatsapp", "facebook", "twitter", "instagram", "email", "copy"}
_BASE_URL = "https://lookatme.fly.dev"


@social_bp.route("/api/invitations/create", methods=["POST"])
@api_login_required
def create_invitation():
    user_id = session["user_id"]
    method  = (request.json or {}).get("method", "copy").strip().lower()
    if method not in _VALID_METHODS:
        method = "copy"

    token      = secrets.token_urlsafe(24)
    invite_url = f"{_BASE_URL}/invite/{token}"

    db.create_social_invitation(user_id, method, token)
    logger.info("INVITE_CREATED user_id=%s method=%s token=%s", user_id, method, token)

    return jsonify({"ok": True, "invite_url": invite_url, "token": token})


@social_bp.route("/api/friends/invite", methods=["POST"])
@api_login_required
def create_friend_invite():
    user_id = session["user_id"]
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    me = db.get_user_by_id(user_id) or {}
    if (me.get("email") or "").strip().lower() == email:
        return jsonify({"error": "You cannot invite yourself"}), 400

    existing_user = db.get_user_by_email(email)
    if existing_user:
        created = db.create_friendship_if_missing(user_id, existing_user["id"])
        # Add user to inviter's first space and workspace, if any.
        inviter_spaces = db.get_user_spaces(user_id)
        if inviter_spaces:
            db.add_space_member(inviter_spaces[0]["id"], existing_user["id"], role="member")
        inviter_workspaces = db.get_user_workspaces(user_id)
        if inviter_workspaces:
            db.add_workspace_member(inviter_workspaces[0]["id"], existing_user["id"], role="member")
        # Send welcome direct message
        inviter_name = (me.get("display_name") or me.get("email", "").split("@")[0] or "A friend").strip()
        db.create_message(
            sender_id=user_id,
            recipient_id=existing_user["id"],
            subject="Welcome to my circle",
            content=f"Hi! {inviter_name} added you as a friend on LookatMe.",
            created_at=datetime.now().isoformat(),
        )
        record_event(
            existing_user["id"],
            "friend_joined",
            "joined your circle",
            metadata={"visibility": "public", "inviter_id": user_id, "auto_added": True},
        )
        logger.info(
            "FRIEND_INVITE_AUTO_CONNECTED inviter_id=%s recipient_id=%s created=%s",
            user_id, existing_user["id"], created,
        )
        return jsonify({
            "ok": True,
            "mode": "auto_connected",
            "recipient_user_id": existing_user["id"],
            "friendship_created": created,
        })

    token = secrets.token_urlsafe(32)
    invite = db.create_friend_invite(user_id, email, token)
    base_url = os.environ.get("APP_BASE_URL", _BASE_URL).rstrip("/")
    invite_url = f"{base_url}/invite/{token}"
    inviter_name = (me.get("display_name") or me.get("email", "").split("@")[0] or "A friend").strip()
    email_sent = send_friend_invite_email(email, token, inviter_name)
    logger.info(
        "FRIEND_INVITE_CREATED inviter_id=%s email=%s token_prefix=%s email_sent=%s",
        user_id, email, token[:8], email_sent,
    )

    return jsonify({
        "ok": True,
        "mode": "email_invite",
        "invite": invite,
        "invite_url": invite_url,
        "email_sent": email_sent,
    })


@social_bp.route("/api/friends/invite-info/<token>", methods=["GET"])
def friend_invite_info(token: str):
    inv = db.get_friend_invite(token)
    if not inv:
        return jsonify({"error": "Invalid invite link"}), 404
    if inv.get("status") != "pending" or inv.get("accepted_at"):
        return jsonify({"error": "already_accepted", "message": "This invite has already been used."}), 400

    inviter = db.get_user_by_id(inv["inviter_id"]) if inv.get("inviter_id") else None
    inviter_name = (
        (inviter.get("display_name") or inviter.get("email", "").split("@")[0]).strip()
        if inviter else "Someone"
    ) or "Someone"
    return jsonify({
        "ok": True,
        "type": "friend",
        "inviter_name": inviter_name,
        "email": inv.get("email"),
        "token": token,
    })


@social_bp.route("/api/friends/accept-invite", methods=["POST"])
@api_login_required
def accept_friend_invite():
    token = (request.json or {}).get("token", "").strip()
    if not token:
        return jsonify({"error": "Token required"}), 400

    me = db.get_user_by_id(session["user_id"]) or {}
    result = db.accept_friend_invite(token, session["user_id"], invitee_email=me.get("email"))
    if not result.get("accepted"):
        reason = result.get("reason") or "invalid_invite"
        if reason == "already_accepted":
            return jsonify({"error": "already_accepted", "message": "This invite has already been used."}), 400
        if reason == "own_invite":
            return jsonify({"error": "Cannot accept your own invite"}), 400
        if reason == "email_mismatch":
            return jsonify({"error": "This invite was sent to a different email address"}), 403
        return jsonify({"error": "Invalid invite link"}), 404

    record_event(
        session["user_id"],
        "friend_joined",
        "joined your circle",
        metadata={"visibility": "public", "inviter_id": result.get("inviter_id")},
    )
    logger.info(
        "FRIEND_INVITE_ACCEPTED token_prefix=%s recipient_user_id=%s inviter_id=%s",
        token[:8], session["user_id"], result.get("inviter_id"),
    )
    return jsonify({"ok": True})


@social_bp.route("/api/invitations/info/<token>", methods=["GET"])
def invitation_info(token: str):
    """Public — returns sender info and marks the invite opened."""
    inv = db.get_social_invitation(token)
    if not inv:
        return jsonify({"error": "Invalid invite link"}), 404
    if inv["accepted_at"]:
        return jsonify({"error": "already_accepted",
                        "message": "This invite has already been used."}), 400

    sender = db.get_user_by_id(inv["sender_id"])
    sender_name = (
        (sender.get("display_name") or sender["email"].split("@")[0])
        if sender else "Someone"
    )

    db.open_social_invitation(token)
    logger.info("INVITE_OPENED token=%s", token)

    return jsonify({
        "ok":          True,
        "type":        "social",
        "sender_name": sender_name,
        "token":       token,
    })


@social_bp.route("/api/invitations/accept", methods=["POST"])
@api_login_required
def accept_invitation():
    user_id = session["user_id"]
    token   = (request.json or {}).get("token", "").strip()

    if not token:
        return jsonify({"error": "Token required"}), 400

    inv = db.get_social_invitation(token)
    if not inv:
        return jsonify({"error": "Invalid invite link"}), 404
    if inv["sender_id"] == user_id:
        return jsonify({"error": "Cannot accept your own invitation"}), 400

    # Capture the acceptor's email so it appears in the inviter's dashboard
    acceptor = db.get_user_by_id(user_id)
    invitee_email = acceptor["email"] if acceptor else None

    ok = db.accept_social_invitation(token, user_id, invitee_email=invitee_email)
    if not ok:
        return jsonify({"error": "already_accepted",
                        "message": "This invite has already been used."}), 400

    logger.info("INVITE_ACCEPTED token=%s recipient_user_id=%s email=%s",
                token, user_id, invitee_email)
    record_event(
        user_id,
        "friend_joined",
        "joined a friend circle",
        metadata={"token_prefix": token[:8]},
    )
    return jsonify({"ok": True})


@social_bp.route("/api/invitations", methods=["GET"])
@api_login_required
def list_invitations():
    return jsonify(db.get_user_invitations(session["user_id"]))


@social_bp.route("/api/friends", methods=["GET"])
@api_login_required
def get_friends():
    return jsonify(db.get_friends(session["user_id"]))


@social_bp.route("/api/friends/overview", methods=["GET"])
@api_login_required
def friends_overview():
    user_id = session["user_id"]
    return jsonify({
        "friends": db.get_friends(user_id),
        "pending_invites": db.get_pending_friend_invites(user_id),
    })


@social_bp.route("/api/friends/streaks", methods=["GET"])
@api_login_required
def friend_streaks():
    """Friend streak feed sorted by highest streak first."""
    return jsonify(db.get_friend_streaks(session["user_id"]))


@social_bp.route("/api/friends/leaderboard", methods=["GET"])
@api_login_required
def friends_leaderboard():
    """Top 10 friends + self, sorted by streak desc then weekly tasks desc."""
    user_id = session["user_id"]

    # Friends stats (already sorted)
    friends = db.get_friends_with_stats(user_id)

    # Build self entry so the user sees their own rank
    me_stats = db.get_user_stats_for_leaderboard(user_id)
    if me_stats:
        me_stats["is_me"] = True
        combined = friends + [me_stats]
        combined.sort(key=lambda x: (-x["current_streak"], -x["tasks_this_week"]))
    else:
        combined = friends

    for i, entry in enumerate(combined):
        entry["rank"] = i + 1

    logger.info("FRIENDS_LEADERBOARD user_id=%s friends=%s", user_id, len(friends))
    return jsonify(combined[:10])


@social_bp.route("/api/friends/<int:friend_id>", methods=["GET"])
@api_login_required
def friend_profile(friend_id: int):
    """Friend profile API for the social circle click-through page."""
    profile = db.get_friend_public_profile(session["user_id"], friend_id)
    if not profile:
        return jsonify({"error": "Friend not found"}), 404
    return jsonify(profile)


@social_bp.route("/api/friends/focus-status", methods=["GET"])
@api_login_required
def friends_focus_status():
    """Live-ish friend focus presence, fetched on demand by the dashboard."""
    return jsonify(db.get_friends_focus_status(session["user_id"]))
