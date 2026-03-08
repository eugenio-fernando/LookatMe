"""
Social accountability system — invitations and friendships.
"""

import logging
import secrets

from flask import Blueprint, jsonify, request, session

from ..models import db
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

    ok = db.accept_social_invitation(token, user_id)
    if not ok:
        return jsonify({"error": "already_accepted",
                        "message": "This invite has already been used."}), 400

    logger.info("INVITE_ACCEPTED token=%s recipient_user_id=%s", token, user_id)
    return jsonify({"ok": True})


@social_bp.route("/api/invitations", methods=["GET"])
@api_login_required
def list_invitations():
    return jsonify(db.get_user_invitations(session["user_id"]))


@social_bp.route("/api/friends", methods=["GET"])
@api_login_required
def get_friends():
    return jsonify(db.get_friends(session["user_id"]))
