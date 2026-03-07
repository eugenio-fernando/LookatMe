from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..extensions import socketio
from ..models import db
from ..utils import api_login_required

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/api/todos")
@api_login_required
def get_todos():
    return jsonify(db.get_todos(workspace_id=session["workspace_id"]))


@tasks_bp.route("/api/todos/today")
@api_login_required
def get_todos_today():
    return jsonify(db.get_todos_today(workspace_id=session["workspace_id"]))


@tasks_bp.route("/api/todos/upcoming")
@api_login_required
def get_todos_upcoming():
    return jsonify(db.get_todos_upcoming(workspace_id=session["workspace_id"]))


@tasks_bp.route("/api/todos", methods=["POST"])
@api_login_required
def create_todo():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    todo = db.create_todo(
        text=text,
        priority=body.get("priority", "medium"),
        due_date=body.get("due_date", ""),
        timestamp=datetime.now().isoformat(),
        workspace_id=session["workspace_id"],
        created_by=session["user_id"],
    )
    activity = db.log_activity(session["user_id"], "task_created", f"Created: {text}")
    uid = session["user_id"]
    socketio.emit("task_created", {"task": todo}, to=f"user_{uid}")
    socketio.emit("activity_created", {"activity": activity}, to=f"user_{uid}")
    return jsonify(todo), 201


@tasks_bp.route("/api/todos/<int:todo_id>/complete", methods=["POST"])
@api_login_required
def complete_todo(todo_id):
    todo = db.get_todo_by_id(todo_id)
    if not todo or todo["workspace_id"] != session["workspace_id"]:
        return jsonify({"error": "Not found"}), 404
    updated_streak = db.complete_todo(todo_id)
    activity = db.log_activity(session["user_id"], "task_completed", f"Completed: {todo['text']}")
    uid = session["user_id"]
    socketio.emit("task_completed", {"todo_id": todo_id, "streak": updated_streak}, to=f"user_{uid}")
    socketio.emit("streak_updated", {"streak": updated_streak}, to=f"user_{uid}")
    socketio.emit("activity_created", {"activity": activity}, to=f"user_{uid}")
    return jsonify({"streak": updated_streak})


@tasks_bp.route("/api/todos/<int:todo_id>", methods=["DELETE"])
@api_login_required
def delete_todo(todo_id):
    todo = db.get_todo_by_id(todo_id)
    if not todo or todo["workspace_id"] != session["workspace_id"]:
        return jsonify({"error": "Not found"}), 404
    db.delete_todo(todo_id)
    return jsonify({"ok": True})
