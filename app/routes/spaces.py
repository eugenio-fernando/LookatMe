from flask import Blueprint, jsonify, request, session

from ..models import db
from ..services.event_service import record_event
from ..utils import api_login_required

spaces_bp = Blueprint("spaces", __name__)


@spaces_bp.route("/api/spaces")
@api_login_required
def list_spaces():
    spaces = db.get_user_spaces(session["user_id"])
    return jsonify(spaces)


@spaces_bp.route("/api/spaces/create", methods=["POST"])
@api_login_required
def create_space():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    space = db.create_space(owner_id=session["user_id"], name=name)
    record_event(
        session["user_id"],
        "space_created",
        f"created space {name}",
        metadata={"visibility": "private", "space_id": space["id"]},
    )
    return jsonify(space), 201


@spaces_bp.route("/api/spaces/join", methods=["POST"])
@api_login_required
def join_space():
    body = request.get_json(silent=True) or {}
    invite_code = str(body.get("invite_code", "")).strip()
    if not invite_code:
        return jsonify({"error": "invite_code is required"}), 400

    space = db.join_space_by_invite_code(session["user_id"], invite_code)
    if not space:
        return jsonify({"error": "invalid invite code"}), 404

    record_event(
        session["user_id"],
        "space_joined",
        f"joined space {space['name']}",
        metadata={"visibility": "space", "space_id": space["id"]},
    )
    return jsonify(space)
