import secrets
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..models import db
from ..services.email_service import (
    send_magic_login_link,
    send_password_reset_email,
    send_verification_email,
)

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
    token = secrets.token_urlsafe(32)
    expiry = (datetime.now() + timedelta(hours=24)).isoformat()
    db.set_verification_token(user["id"], token, expiry)
    send_verification_email(email, token)
    return jsonify({"message": "Account created. Check your email to verify your account."}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user.get("verified"):
        return jsonify({"error": "Please verify your email before signing in."}), 403

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


# ── Email verification ─────────────────────────────────────────────────────

@auth_bp.route("/verify/<token>")
def verify_email(token):
    user = db.get_user_by_verification_token(token)
    if not user:
        return redirect(url_for("auth.login_page") + "?msg=invalid_token")

    expiry = user.get("verification_expiry", "")
    if expiry and datetime.fromisoformat(expiry) < datetime.now():
        return redirect(url_for("auth.login_page") + "?msg=token_expired")

    db.mark_user_verified(user["id"])
    session["user_id"] = user["id"]
    workspaces = db.get_user_workspaces(user["id"])
    if workspaces:
        session["workspace_id"] = workspaces[0]["id"]
    return redirect(url_for("views.index"))


# ── Resend verification ────────────────────────────────────────────────────

@auth_bp.route("/api/auth/resend-verification", methods=["POST"])
def resend_verification():
    """Re-generate and re-send a verification email for an unverified account."""
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400

    user = db.get_user_by_email(email)
    if user and not user.get("verified"):
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now() + timedelta(hours=24)).isoformat()
        db.set_verification_token(user["id"], token, expiry)
        send_verification_email(email, token)

    # Always return ok — don't reveal account state
    return jsonify({"ok": True})


# ── Magic login ────────────────────────────────────────────────────────────

@auth_bp.route("/api/auth/magic-login", methods=["POST"])
def request_magic_login():
    """Generate a magic sign-in link and email it to the user."""
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400

    user = db.get_user_by_email(email)
    if not user or not user.get("verified"):
        # Don't reveal whether the account exists or is unverified
        return jsonify({"ok": True})

    token = secrets.token_urlsafe(32)
    expiry = (datetime.now() + timedelta(minutes=15)).isoformat()
    db.set_magic_login_token(user["id"], token, expiry)
    send_magic_login_link(email, token)
    return jsonify({"ok": True})


@auth_bp.route("/login/<token>")
def magic_login(token):
    user = db.get_user_by_magic_token(token)
    if not user:
        return redirect(url_for("auth.login_page") + "?msg=invalid_token")

    expiry = user.get("magic_login_expiry", "")
    if expiry and datetime.fromisoformat(expiry) < datetime.now():
        return redirect(url_for("auth.login_page") + "?msg=token_expired")

    db.clear_magic_token(user["id"])
    if not user.get("verified"):
        return redirect(url_for("auth.login_page") + "?msg=invalid_token")
    session["user_id"] = user["id"]
    workspaces = db.get_user_workspaces(user["id"])
    if workspaces:
        session["workspace_id"] = workspaces[0]["id"]
    return redirect(url_for("views.index"))


# ── Token-based password reset ─────────────────────────────────────────────

@auth_bp.route("/api/auth/request-reset", methods=["POST"])
def request_reset():
    """Generate a password-reset token and email it. Always returns 200 to avoid enumeration."""
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400

    user = db.get_user_by_email(email)
    if user:
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now() + timedelta(hours=1)).isoformat()
        db.set_reset_token(user["id"], token, expiry)
        send_password_reset_email(email, token)

    return jsonify({"ok": True})


@auth_bp.route("/reset/<token>")
def reset_page(token):
    """Redirect to the login page with the reset token in the URL so the JS can render the form."""
    return redirect(url_for("auth.login_page") + f"?reset_token={token}")


@auth_bp.route("/api/auth/reset-with-token", methods=["POST"])
def reset_with_token():
    """Complete a token-based password reset."""
    body = request.get_json(silent=True) or {}
    token = body.get("token", "")
    new_password = body.get("new_password", "")

    if not token:
        return jsonify({"error": "Reset token is required"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user = db.get_user_by_reset_token(token)
    if not user:
        return jsonify({"error": "Invalid or expired reset link"}), 400

    expiry = user.get("reset_expiry", "")
    if expiry and datetime.fromisoformat(expiry) < datetime.now():
        return jsonify({"error": "Reset link has expired"}), 400

    db.update_password(user["id"], generate_password_hash(new_password))
    db.clear_reset_token(user["id"])
    return jsonify({"ok": True})
