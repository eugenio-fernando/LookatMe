"""
Debug routes — developer-only endpoints for testing email delivery.

Disabled in production (FLASK_ENV=production).
"""

import logging
import os
import secrets

from flask import Blueprint, jsonify, request

from ..services.email_service import send_verification_email

logger = logging.getLogger(__name__)

debug_bp = Blueprint("debug", __name__)


@debug_bp.route("/send-test-email", methods=["POST"])
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
