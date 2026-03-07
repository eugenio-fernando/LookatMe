from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..extensions import socketio
from ..models import db
from ..utils import api_login_required

messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/api/messages/inbox")
@api_login_required
def inbox():
    return jsonify(db.get_inbox(user_id=session["user_id"]))


@messages_bp.route("/api/messages/sent")
@api_login_required
def sent():
    return jsonify(db.get_sent(user_id=session["user_id"]))


@messages_bp.route("/api/messages/unread-count")
@api_login_required
def unread_count():
    return jsonify({"count": db.count_unread(user_id=session["user_id"])})


@messages_bp.route("/api/messages/users")
@api_login_required
def list_users():
    """All users available as message recipients."""
    users = db.get_all_users()
    me = session["user_id"]
    return jsonify([u for u in users if u["id"] != me])


@messages_bp.route("/api/messages", methods=["POST"])
@api_login_required
def send_message():
    body = request.get_json(silent=True) or {}
    recipient_id = body.get("recipient_id")
    subject = (body.get("subject") or "").strip()
    content = (body.get("content") or "").strip()

    if not recipient_id or not subject or not content:
        return jsonify({"error": "recipient_id, subject, and content are required"}), 400

    if not isinstance(recipient_id, int):
        return jsonify({"error": "recipient_id must be an integer"}), 400

    if recipient_id == session["user_id"]:
        return jsonify({"error": "Cannot send a message to yourself"}), 400

    msg = db.create_message(
        sender_id=session["user_id"],
        recipient_id=recipient_id,
        subject=subject,
        content=content,
        created_at=datetime.now().isoformat(),
    )
    activity = db.log_activity(session["user_id"], "message_sent", f"Sent: {subject}")
    uid = session["user_id"]
    socketio.emit(
        "new_message",
        {"id": msg["id"], "sender_id": uid, "subject": msg["subject"], "preview": msg["content"][:80]},
        to=f"user_{recipient_id}",
    )
    socketio.emit("activity_created", {"activity": activity}, to=f"user_{uid}")
    return jsonify(msg), 201


@messages_bp.route("/api/messages/<int:message_id>/read", methods=["PATCH"])
@api_login_required
def mark_read(message_id):
    msg = db.mark_message_read(message_id, user_id=session["user_id"])
    if msg is None:
        return jsonify({"error": "Not found or access denied"}), 404
    return jsonify(msg)
