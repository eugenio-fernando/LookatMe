import logging
import os
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

logger = logging.getLogger(__name__)

# Page / token-redirect routes — registered without a url_prefix so that
# /login, /verify/<token>, /login/<token>, /reset/<token> stay at their
# canonical paths (email links and browser bookmarks point to these).
auth_bp = Blueprint("auth", __name__)

# JSON API routes — registered with url_prefix="/api/auth" in __init__.py.
# Route decorators use short paths: "/login", "/register", etc.
# Flask combines prefix + path, so the final URL is /api/auth/<path>.
auth_api_bp = Blueprint("auth_api", __name__)


# ── Page routes ────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("views.index"))
    return render_template("login.html")


@auth_bp.route("/verify/<token>")
def verify_email(token):
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    token_hash = db.hash_verification_token(token)
    user = db.get_user_by_verification_token_hash(token_hash, legacy_token=token)
    if not user:
        logger.warning("VERIFY_TOKEN_INVALID: token_prefix=%s", token[:8])
        return render_template("verify_error.html", reason="invalid"), 400

    expiry = user.get("verification_expiry", "")
    if expiry and datetime.fromisoformat(expiry) < datetime.now():
        logger.warning(
            "TOKEN_EXPIRED event=TOKEN_EXPIRED token_type=verification user_id=%s",
            user["id"],
        )
        try:
            db.create_activity_event(
                user_id=user["id"],
                event_type="TOKEN_EXPIRED",
                description="verification token expired",
                metadata={"token_type": "verification"},
            )
        except Exception:
            pass
        return render_template("verify_error.html", reason="expired"), 400

    db.mark_user_verified(user["id"])
    logger.info("USER_VERIFIED event=USER_VERIFIED user_id=%s", user["id"])
    try:
        db.create_activity_event(
            user_id=user["id"],
            event_type="USER_VERIFIED",
            description="user verified account",
            metadata={"source": "verify_link"},
        )
    except Exception:
        pass
    session["user_id"] = user["id"]
    workspaces = db.get_user_workspaces(user["id"])
    if workspaces:
        session["workspace_id"] = workspaces[0]["id"]
    session["fun_welcome"] = db.record_login_and_get_welcome(user["id"])
    return redirect(url_for("views.index"))


@auth_bp.route("/login/<token>")
def magic_login(token):
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
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
    session["fun_welcome"] = db.record_login_and_get_welcome(user["id"])
    return redirect(url_for("views.index"))


@auth_bp.route("/reset/<token>")
def reset_page(token):
    """Redirect to the login page with the reset token so the JS can render the form."""
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    return redirect(url_for("auth.login_page") + f"?reset_token={token}")


# ── API routes (prefix /api/auth applied in __init__.py) ──────────────────

@auth_api_bp.route("/register", methods=["POST"])
def register():
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
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
    try:
        db.create_activity_event(
            user_id=user["id"],
            event_type="USER_REGISTERED",
            description="user registered account",
            metadata={"email": email},
        )
    except Exception:
        pass
    workspace = db.create_workspace(
        name="Personal",
        created_at=datetime.now().isoformat(),
    )
    db.add_workspace_member(workspace["id"], user["id"], role="admin")

    # Auto-accept a social invite if the registration came through an invite link
    invite_token = body.get("invite_token", "").strip()
    if invite_token:
        try:
            accepted = db.accept_social_invitation(invite_token, user["id"], invitee_email=email)
            logger.info(
                "INVITE_ACCEPTED_ON_REGISTER token_prefix=%s user_id=%s accepted=%s",
                invite_token[:8], user["id"], accepted,
            )
        except Exception as exc:
            logger.warning("INVITE_ACCEPT_FAILED_ON_REGISTER token_prefix=%s err=%s",
                           invite_token[:8], exc)

    ver_token = secrets.token_urlsafe(32)
    expiry = (datetime.now() + timedelta(minutes=15)).isoformat()
    db.set_verification_token(user["id"], ver_token, expiry)
    attempts = db.count_verification_email_attempts_last_hour(user["id"])
    if attempts >= 3:
        logger.warning(
            "EMAIL_VERIFICATION_RATE_LIMIT event=EMAIL_SEND_FAIL reason=rate_limit user_id=%s attempts_last_hour=%s",
            user["id"], attempts,
        )
        return jsonify({"message": "Account created. Verification email temporarily rate-limited. Try again soon."}), 201
    logger.info("EMAIL_FUNCTION_CALLED: send_verification_email to=%s", email)
    verify_from = (os.environ.get("VERIFY_EMAIL_FROM", "") or "").strip() or None
    ok = send_verification_email(email, ver_token, from_address=verify_from)
    if ok:
        db.log_verification_email_attempt(user["id"], email)
    return jsonify({"message": "Account created. Check your email to verify your account."}), 201


@auth_api_bp.route("/login", methods=["POST"])
def login():
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    user = db.get_user_by_email(email)
    if user:
        try:
            db.create_activity_event(
                user_id=user["id"],
                event_type="LOGIN_ATTEMPT",
                description="login attempt",
                metadata={"email": email},
            )
        except Exception:
            pass
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user.get("verified"):
        return jsonify({"error": "Please verify your email before signing in."}), 403

    session["user_id"] = user["id"]
    workspaces = db.get_user_workspaces(user["id"])
    if workspaces:
        session["workspace_id"] = workspaces[0]["id"]
    session["fun_welcome"] = db.record_login_and_get_welcome(user["id"])
    return jsonify({"id": user["id"], "email": user["email"]})


@auth_api_bp.route("/logout", methods=["POST"])
def logout():
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    session.clear()
    return jsonify({"ok": True})


@auth_api_bp.route("/me")
def me():
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = db.get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"error": "User not found"}), 404

    return jsonify({"id": user["id"], "email": user["email"]})


@auth_api_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Reset password without being logged in — requires only email + new password."""
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
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


@auth_api_bp.route("/change-password", methods=["POST"])
def change_password():
    """Change password while logged in — requires current password verification."""
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
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


# ── Onboarding ────────────────────────────────────────────────────────────

@auth_api_bp.route("/dismiss-onboarding", methods=["POST"])
def dismiss_onboarding():
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    db.mark_onboarding_seen(user_id)
    return jsonify({"ok": True})


# ── Resend verification ────────────────────────────────────────────────────

@auth_api_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    """Re-generate and re-send a verification email for an unverified account."""
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400

    user = db.get_user_by_email(email)
    if user and not user.get("verified"):
        attempts = db.count_verification_email_attempts_last_hour(user["id"])
        if attempts >= 3:
            logger.warning(
                "EMAIL_VERIFICATION_RATE_LIMIT event=EMAIL_SEND_FAIL reason=rate_limit user_id=%s attempts_last_hour=%s",
                user["id"], attempts,
            )
            return jsonify({"ok": True})
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now() + timedelta(minutes=15)).isoformat()
        db.set_verification_token(user["id"], token, expiry)
        logger.info("EMAIL_FUNCTION_CALLED: send_verification_email to=%s", email)
        verify_from = (os.environ.get("VERIFY_EMAIL_FROM", "") or "").strip() or None
        ok = send_verification_email(email, token, from_address=verify_from)
        if ok:
            db.log_verification_email_attempt(user["id"], email)
    else:
        logger.info(
            "RESEND_VERIFICATION_SKIP: email=%s user_found=%s already_verified=%s",
            email, user is not None, bool(user and user.get("verified")),
        )

    # Always return ok — don't reveal account state
    return jsonify({"ok": True})


# ── Magic login ────────────────────────────────────────────────────────────

@auth_api_bp.route("/magic-login", methods=["POST"])
def request_magic_login():
    """Generate a magic sign-in link and email it to the user."""
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400

    user = db.get_user_by_email(email)
    if not user:
        logger.info("MAGIC_LOGIN_SKIP: no account found for email=%s", email)
        return jsonify({"ok": True})

    if not user.get("verified"):
        logger.warning(
            "MAGIC_LOGIN_SKIP: account email=%s exists but is NOT verified — "
            "user must verify their email before using magic login",
            email,
        )
        return jsonify({"ok": True})

    token = secrets.token_urlsafe(32)
    expiry = (datetime.now() + timedelta(minutes=15)).isoformat()
    db.set_magic_login_token(user["id"], token, expiry)
    logger.info("EMAIL_FUNCTION_CALLED: send_magic_login_link to=%s", email)
    send_magic_login_link(email, token)
    return jsonify({"ok": True})


# ── Token-based password reset ─────────────────────────────────────────────

@auth_api_bp.route("/request-reset", methods=["POST"])
def request_reset():
    """Generate a password-reset token and email it. Always returns 200 to avoid enumeration."""
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400

    user = db.get_user_by_email(email)
    if user:
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now() + timedelta(hours=1)).isoformat()
        db.set_reset_token(user["id"], token, expiry)
        logger.info("EMAIL_FUNCTION_CALLED: send_password_reset_email to=%s", email)
        send_password_reset_email(email, token)
    else:
        logger.info("REQUEST_RESET_SKIP: no account found for email=%s", email)

    return jsonify({"ok": True})


@auth_api_bp.route("/reset-with-token", methods=["POST"])
def reset_with_token():
    """Complete a token-based password reset."""
    logger.info("AUTH_ENDPOINT: %s %s", request.method, request.path)
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
