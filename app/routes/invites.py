import logging
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session

from ..models import db
from ..utils import api_login_required

invites_bp = Blueprint("invites", __name__)
logger = logging.getLogger(__name__)


@invites_bp.route("/api/workspaces/invite", methods=["POST"])
@api_login_required
def send_invite():
    body         = request.get_json(silent=True) or {}
    email        = body.get("email", "").strip().lower()
    workspace_id = session.get("workspace_id")

    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    role = db.get_workspace_role(workspace_id, session["user_id"])
    if role != "admin":
        return jsonify({"error": "Only workspace admins can invite"}), 403

    token      = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
    db.create_workspace_invite(workspace_id, email, token, expires_at)

    invite_url = f"https://lookatme.fly.dev/invite/{token}"
    logger.info("WORKSPACE_INVITE_CREATED: workspace_id=%s email=%s", workspace_id, email)
    return jsonify({"ok": True, "invite_url": invite_url})


@invites_bp.route("/api/workspaces/accept-invite", methods=["POST"])
@api_login_required
def accept_invite():
    body  = request.get_json(silent=True) or {}
    token = body.get("token", "")

    if not token:
        return jsonify({"error": "Token required"}), 400

    invite = db.get_workspace_invite(token)
    if not invite:
        return jsonify({"error": "Invalid or expired invite"}), 400
    if datetime.fromisoformat(invite["expires_at"]) < datetime.utcnow():
        return jsonify({"error": "Invite has expired"}), 400

    db.add_workspace_member(invite["workspace_id"], session["user_id"])
    db.consume_workspace_invite(token)
    logger.info("WORKSPACE_INVITE_ACCEPTED: workspace_id=%s user_id=%s",
                invite["workspace_id"], session["user_id"])
    return jsonify({"ok": True, "workspace_id": invite["workspace_id"]})
