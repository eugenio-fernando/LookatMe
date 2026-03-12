from flask import Blueprint, jsonify, request, session

from ..models import db
from ..services.event_service import record_event
from ..utils import api_login_required

challenges_bp = Blueprint("challenges", __name__)
_VALID_METRICS = {"focus_minutes", "tasks_completed", "km_run", "books_read"}


@challenges_bp.route("/api/challenges")
@api_login_required
def list_challenges():
    space_id = request.args.get("space_id", type=int)
    return jsonify(db.get_challenges_for_user(session["user_id"], space_id=space_id))


@challenges_bp.route("/api/challenges/create", methods=["POST"])
@api_login_required
def create_challenge():
    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    metric = str(body.get("metric", "")).strip()
    goal = body.get("goal")
    space_id = body.get("space_id")

    if not title:
        return jsonify({"error": "title is required"}), 400
    if metric not in _VALID_METRICS:
        return jsonify({"error": "invalid metric"}), 400
    if not isinstance(goal, int) or goal <= 0:
        return jsonify({"error": "goal must be a positive integer"}), 400
    if not isinstance(space_id, int):
        return jsonify({"error": "space_id must be an integer"}), 400
    if not db.is_space_member(space_id, session["user_id"]):
        return jsonify({"error": "access denied for space"}), 403

    challenge = db.create_challenge(
        space_id=space_id,
        title=title,
        goal=goal,
        metric=metric,
        created_by=session["user_id"],
    )
    record_event(
        session["user_id"],
        "challenge_started",
        f"started challenge {title}",
        metadata={"visibility": "space", "space_id": space_id, "challenge_id": challenge["id"]},
    )
    return jsonify(challenge), 201


@challenges_bp.route("/api/challenges/update-progress", methods=["POST"])
@api_login_required
def update_challenge_progress():
    body = request.get_json(silent=True) or {}
    challenge_id = body.get("challenge_id")
    progress = body.get("progress")

    if not isinstance(challenge_id, int):
        return jsonify({"error": "challenge_id must be an integer"}), 400
    if not isinstance(progress, int) or progress < 0:
        return jsonify({"error": "progress must be a non-negative integer"}), 400

    progress_row = db.upsert_challenge_progress(challenge_id, session["user_id"], progress)
    if not progress_row:
        return jsonify({"error": "challenge not found"}), 404

    challenges = db.get_challenges_for_user(session["user_id"])
    challenge = next((c for c in challenges if c["id"] == challenge_id), None)
    if not challenge:
        return jsonify({"error": "challenge not visible to user"}), 403

    event_type = "challenge_completed" if progress_row["completed"] else "challenge_progress"
    record_event(
        session["user_id"],
        event_type,
        f"updated challenge progress to {progress}",
        metadata={"visibility": "space", "space_id": challenge["space_id"], "challenge_id": challenge_id},
    )
    return jsonify(progress_row)
