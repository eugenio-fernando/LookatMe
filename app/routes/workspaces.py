from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..models import db
from ..utils import api_login_required

workspaces_bp = Blueprint("workspaces", __name__)


@workspaces_bp.route("/api/workspaces")
@api_login_required
def list_workspaces():
    workspaces = db.get_user_workspaces(session["user_id"])
    current_id = session.get("workspace_id")
    return jsonify({"workspaces": workspaces, "current_workspace_id": current_id})


@workspaces_bp.route("/api/workspaces", methods=["POST"])
@api_login_required
def create_workspace():
    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    workspace = db.create_workspace(name=name, created_at=datetime.now().isoformat())
    db.add_workspace_member(workspace["id"], session["user_id"], role="admin")
    session["workspace_id"] = workspace["id"]
    return jsonify(workspace), 201


@workspaces_bp.route("/api/workspace/current")
@api_login_required
def current_workspace():
    workspace_id = session.get("workspace_id")
    if not workspace_id:
        return jsonify({"error": "No active workspace"}), 404
    workspace = db.get_workspace_by_id(workspace_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    return jsonify(workspace)


@workspaces_bp.route("/api/workspace/switch", methods=["POST"])
@api_login_required
def switch_workspace():
    body = request.get_json(silent=True) or {}
    workspace_id = body.get("workspace_id")
    if not workspace_id:
        return jsonify({"error": "workspace_id is required"}), 400
    if not db.is_workspace_member(workspace_id, session["user_id"]):
        return jsonify({"error": "Access denied"}), 403
    session["workspace_id"] = workspace_id
    workspace = db.get_workspace_by_id(workspace_id)
    return jsonify(workspace)


@workspaces_bp.route("/api/workspace/members")
@api_login_required
def list_members():
    workspace_id = session.get("workspace_id")
    if not workspace_id:
        return jsonify({"error": "No active workspace"}), 404
    if not db.is_workspace_member(workspace_id, session["user_id"]):
        return jsonify({"error": "Access denied"}), 403
    return jsonify(db.get_workspace_members(workspace_id))


@workspaces_bp.route("/api/workspace/invite", methods=["POST"])
@api_login_required
def invite_member():
    workspace_id = session.get("workspace_id")
    if not workspace_id:
        return jsonify({"error": "No active workspace"}), 404
    role = db.get_workspace_role(workspace_id, session["user_id"])
    if role != "admin":
        return jsonify({"error": "Only admins can invite members"}), 403
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400
    member = db.invite_to_workspace(workspace_id, email)
    if member is None:
        return jsonify({"error": "No user found with that email"}), 404
    return jsonify(member), 201
