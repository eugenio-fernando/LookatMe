import logging

from flask import Blueprint, jsonify, request

from ..models import db

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/api/webhooks/resend", methods=["POST"])
def resend_webhook():
    payload = request.get_json(silent=True) or {}
    event_type = str(payload.get("type", "")).strip().lower()
    data = payload.get("data") or {}

    message_id = str(data.get("email_id") or data.get("id") or payload.get("id") or "").strip() or None
    email = None
    to_value = data.get("to")
    if isinstance(to_value, list) and to_value:
        email = str(to_value[0])
    elif isinstance(to_value, str):
        email = to_value
    elif data.get("email"):
        email = str(data.get("email"))

    try:
        db.log_email_webhook_event(
            provider="resend",
            event_type=event_type or "unknown",
            email=email,
            message_id=message_id,
            payload=payload,
        )
    except Exception as exc:
        logger.error(
            "WEBHOOK_PERSIST_FAIL event=EMAIL_SEND_FAIL provider=resend type=%s message_id=%s err=%s",
            event_type, message_id, exc,
        )

    if event_type == "email.sent":
        logger.info("EMAIL_SEND_SUCCESS event=EMAIL_SEND_SUCCESS source=webhook provider=resend email=%s message_id=%s", email, message_id)
    elif event_type == "email.delivered":
        logger.info("EMAIL_DELIVERED event=EMAIL_DELIVERED provider=resend email=%s message_id=%s", email, message_id)
    elif event_type == "email.opened":
        logger.info("EMAIL_OPENED event=EMAIL_OPENED provider=resend email=%s message_id=%s", email, message_id)
    elif event_type == "email.bounced":
        logger.warning("EMAIL_BOUNCED event=EMAIL_BOUNCED provider=resend email=%s message_id=%s", email, message_id)
    else:
        logger.info("EMAIL_WEBHOOK_IGNORED event=EMAIL_WEBHOOK_IGNORED provider=resend type=%s message_id=%s", event_type, message_id)

    return jsonify({"ok": True})
