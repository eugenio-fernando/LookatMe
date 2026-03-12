from flask import Blueprint, jsonify, request, session

from ...extensions import socketio
from ...models import db
from ...utils import api_login_required
from .service import get_feed_for_user

activity_bp = Blueprint("activity", __name__)
_VALID_REACTIONS = {"like", "love", "fire", "clap"}


@activity_bp.route("/api/activity")
@api_login_required
def get_activity():
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(db.get_activity_feed(session["user_id"], limit=limit))


@activity_bp.route("/api/activity/feed")
@api_login_required
def get_activity_feed():
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(get_feed_for_user(session["user_id"], limit=limit))


@activity_bp.route("/api/activity/react", methods=["POST"])
@api_login_required
def react_to_activity():
    body = request.get_json(silent=True) or {}
    event_id = body.get("event_id")
    reaction_type = str(body.get("reaction_type", "")).strip().lower()

    if not isinstance(event_id, int):
        return jsonify({"error": "event_id must be a number"}), 400
    if reaction_type not in _VALID_REACTIONS:
        return jsonify({"error": "invalid reaction_type"}), 400

    event = db.get_activity_event_by_id(event_id)
    if not event:
        return jsonify({"error": "event not found"}), 404

    user_id = session["user_id"]
    if db.has_activity_reaction(event_id, user_id, reaction_type):
        counts = db.get_reaction_counts_for_event_ids([event_id]).get(
            event_id, {"like": 0, "love": 0, "fire": 0, "clap": 0}
        )
        return jsonify({"ok": True, "duplicate": True, "event_id": event_id, "reactions": counts})

    reaction = db.create_activity_reaction(event_id, user_id, reaction_type)
    counts = db.get_reaction_counts_for_event_ids([event_id]).get(
        event_id, {"like": 0, "love": 0, "fire": 0, "clap": 0}
    )
    payload = {
        "event_id": event_id,
        "reaction": reaction,
        "reactions": counts,
    }
    socketio.emit("reaction:new", payload, to=f"user_{event['user_id']}")
    if event["user_id"] != user_id:
        socketio.emit("reaction:new", payload, to=f"user_{user_id}")

    return jsonify({"ok": True, "event_id": event_id, "reactions": counts})
