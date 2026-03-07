from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..models import db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("views.index"))
    return render_template("login.html")


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if db.get_user_by_email(email):
        return jsonify({"error": "An account with this email already exists"}), 409

    password_hash = generate_password_hash(password)
    user = db.create_user(
        email=email,
        password_hash=password_hash,
        created_at=datetime.now().isoformat(),
    )
    # Create a personal workspace for the new user
    workspace = db.create_workspace(
        name="Personal",
        created_at=datetime.now().isoformat(),
    )
    db.add_workspace_member(workspace["id"], user["id"], role="admin")
    session["user_id"] = user["id"]
    session["workspace_id"] = workspace["id"]
    return jsonify({"id": user["id"], "email": user["email"]}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user["id"]
    # Restore the user's first workspace as the active one
    workspaces = db.get_user_workspaces(user["id"])
    if workspaces:
        session["workspace_id"] = workspaces[0]["id"]
    return jsonify({"id": user["id"], "email": user["email"]})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    """Reset password without being logged in — requires only email + new password."""
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    new_password = body.get("new_password", "")

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user = db.get_user_by_email(email)
    if not user:
        return jsonify({"error": "No account found with that email"}), 404

    db.update_password(user["id"], generate_password_hash(new_password))
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/change-password", methods=["POST"])
def change_password():
    """Change password while logged in — requires current password verification."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    body = request.get_json(silent=True) or {}
    current = body.get("current_password", "")
    new_password = body.get("new_password", "")

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user_pub = db.get_user_by_id(user_id)
    if not user_pub:
        return jsonify({"error": "User not found"}), 404

    user = db.get_user_by_email(user_pub["email"])
    if not check_password_hash(user["password_hash"], current):
        return jsonify({"error": "Current password is incorrect"}), 401

    db.update_password(user_id, generate_password_hash(new_password))
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = db.get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"error": "User not found"}), 404

    return jsonify({"id": user["id"], "email": user["email"]})
