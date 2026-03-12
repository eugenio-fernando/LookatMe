"""
Focus Mode API endpoints.
Timer remains client-side; the backend records lifecycle events only.
"""

from flask import Blueprint, jsonify, request, session

from ..models import db
from ..services.activity_service import record_event
from ..utils import api_login_required

focus_bp = Blueprint("focus", __name__)


@focus_bp.route("/api/focus/start", methods=["POST"])
@api_login_required
def focus_start():
    body = request.get_json(silent=True) or {}
    task = (body.get("task") or "").strip()
    result = db.start_focus_session(session["user_id"], task=task)
    if not result:
        return jsonify({"error": "User not found"}), 404
    return jsonify(result)


@focus_bp.route("/api/focus/complete", methods=["POST"])
@api_login_required
def focus_complete():
    body = request.get_json(silent=True) or {}
    completed = bool(body.get("completed", True))
    result = db.complete_focus_session(session["user_id"], completed=completed)
    if completed:
        record_event(
            session["user_id"],
            "focus_completed",
            "completed a focus session",
            metadata={"status": "completed"},
        )
    return jsonify(result)


@focus_bp.route("/api/focus/status", methods=["GET"])
@api_login_required
def focus_status():
    return jsonify(db.get_focus_status(session["user_id"]))


@focus_bp.route("/api/focus/stats", methods=["GET"])
@api_login_required
def focus_stats():
    return jsonify(db.get_focus_stats(session["user_id"]))


@focus_bp.route("/api/focus/vip", methods=["GET"])
@api_login_required
def list_vip_contacts():
    return jsonify({"ids": db.list_vip_contact_ids(session["user_id"])})


@focus_bp.route("/api/focus/vip", methods=["POST"])
@api_login_required
def add_vip_contact():
    body = request.get_json(silent=True) or {}
    vip_user_id = body.get("vip_user_id")
    if not isinstance(vip_user_id, int):
        return jsonify({"error": "vip_user_id must be an integer"}), 400
    ok = db.set_vip_contact(session["user_id"], vip_user_id)
    if not ok:
        return jsonify({"error": "Invalid vip_user_id"}), 400
    return jsonify({"ok": True})


@focus_bp.route("/api/focus/vip/<int:vip_user_id>", methods=["DELETE"])
@api_login_required
def delete_vip_contact(vip_user_id: int):
    db.remove_vip_contact(session["user_id"], vip_user_id)
    return jsonify({"ok": True})
