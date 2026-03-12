"""
Debug routes.

Includes admin debug page and a dev-only email testing endpoint.
"""

import logging
import os
import secrets

from flask import Blueprint, abort, jsonify, render_template, request, session

from ..models import db
from ..services.email_service import send_verification_email
from ..utils import login_required

logger = logging.getLogger(__name__)

debug_bp = Blueprint("debug", __name__)
AUTHORIZED_DEBUG_EMAIL = "eugenio.fernando@icloud.com"


def _is_admin_user(user_id: int) -> bool:
    user = db.get_user_by_id(user_id)
    return bool(
        user
        and user.get("email", "").casefold() == AUTHORIZED_DEBUG_EMAIL.casefold()
    )


@debug_bp.route("/admin/debug", methods=["GET"])
@login_required
def admin_debug():
    user_id = session.get("user_id")
    if not user_id or not _is_admin_user(int(user_id)):
        abort(403)

    email_event_types = [
        "EMAIL_SEND_ATTEMPT",
        "EMAIL_SEND_SUCCESS",
        "EMAIL_SEND_FAIL",
        "EMAIL_FAIL",
        "EMAIL_DELIVERED",
    ]
    user_event_types = [
        "USER_REGISTERED",
        "USER_VERIFIED",
        "LOGIN_ATTEMPT",
        "TOKEN_EXPIRED",
    ]
    webhook_event_types = [
        "email.sent",
        "email.delivered",
        "email.opened",
        "email.bounced",
    ]

    try:
        activity_events = db.get_recent_activity_events(
            limit=50,
            event_types=email_event_types + user_event_types,
        )
    except Exception as exc:
        logger.warning("ADMIN_DEBUG_ACTIVITY_EVENTS_UNAVAILABLE err=%s", exc)
        activity_events = []

    try:
        webhook_events = db.get_recent_email_webhook_events(
            limit=50,
            event_types=webhook_event_types,
        )
    except Exception as exc:
        logger.warning("ADMIN_DEBUG_WEBHOOK_EVENTS_UNAVAILABLE err=%s", exc)
        webhook_events = []

    email_events = [e for e in activity_events if e.get("event_type") in email_event_types][:50]
    user_events = [e for e in activity_events if e.get("event_type") in user_event_types][:50]

    return render_template(
        "admin_debug.html",
        email_events=email_events,
        user_events=user_events,
        webhook_events=webhook_events[:50],
    )


@debug_bp.route("/api/debug/send-test-email", methods=["POST"])
def send_test_email():
    if os.environ.get("FLASK_ENV", "development") == "production":
        return jsonify({"error": "Not available in production"}), 403

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"error": "email is required"}), 400

    token = secrets.token_urlsafe(32)
    logger.info("DEBUG_EMAIL_ATTEMPT: to=%s token_prefix=%s", email, token[:8])

    try:
        ok = send_verification_email(email, token)
        if ok:
            logger.info("DEBUG_EMAIL_SUCCESS: to=%s", email)
            return jsonify({"ok": True})
        logger.warning("DEBUG_EMAIL_FAIL: to=%s send returned False", email)
        return jsonify({"ok": False, "error": "send returned False"}), 500
    except Exception as exc:
        logger.error("DEBUG_EMAIL_FAIL: to=%s error=%s", email, exc)
        return jsonify({"ok": False, "error": str(exc)}), 500
