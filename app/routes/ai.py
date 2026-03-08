import json
import logging
import os

from flask import Blueprint, jsonify, session

from ..models import db
from ..utils import api_login_required
from ..services import ai_service

ai_bp = Blueprint("ai", __name__)
logger = logging.getLogger(__name__)

MAX_CALLS_PER_DAY = 10

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR  = "/data" if os.path.isdir("/data") else _BASE_DIR


def _read_notes() -> list[dict]:
    """Read daily notes from the JSON file store."""
    try:
        with open(os.path.join(_DATA_DIR, "daily_notes.json")) as f:
            return json.load(f)
    except Exception:
        return []


def _check_limit(user_id: int) -> tuple[bool, int]:
    """Return (allowed, remaining). Does NOT increment — usage is recorded on success only."""
    used      = db.count_ai_usage_today(user_id)
    remaining = max(0, MAX_CALLS_PER_DAY - used)
    return remaining > 0, remaining


def _limit_response():
    return jsonify({
        "error":   "limit_reached",
        "message": f"Daily AI limit reached ({MAX_CALLS_PER_DAY} per day). Try again tomorrow.",
    }), 429


@ai_bp.route("/api/ai/analyze-day", methods=["POST"])
@api_login_required
def analyze_day():
    user_id      = session["user_id"]
    workspace_id = session.get("workspace_id")
    logger.info("AI_REQUEST_STARTED user_id=%s type=analyze-day", user_id)

    allowed, remaining = _check_limit(user_id)
    if not allowed:
        return _limit_response()

    try:
        tasks  = db.get_todos(workspace_id) if workspace_id else []
        notes  = _read_notes()
        result = ai_service.analyze_day(tasks, notes)
        db.log_ai_usage(user_id, "analyze-day")
        logger.info("AI_REQUEST_SUCCESS user_id=%s type=analyze-day", user_id)
        return jsonify({"ok": True, "result": result, "remaining": remaining - 1})
    except RuntimeError as e:
        logger.info("AI_REQUEST_FAILED user_id=%s type=analyze-day reason=%s", user_id, e)
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.info("AI_REQUEST_FAILED user_id=%s type=analyze-day reason=%s", user_id, e)
        return jsonify({"error": "AI service unavailable."}), 500


@ai_bp.route("/api/ai/plan-tomorrow", methods=["POST"])
@api_login_required
def plan_tomorrow():
    user_id      = session["user_id"]
    workspace_id = session.get("workspace_id")
    logger.info("AI_REQUEST_STARTED user_id=%s type=plan-tomorrow", user_id)

    allowed, remaining = _check_limit(user_id)
    if not allowed:
        return _limit_response()

    try:
        tasks  = db.get_todos(workspace_id) if workspace_id else []
        notes  = _read_notes()
        result = ai_service.plan_tomorrow(tasks, notes)
        db.log_ai_usage(user_id, "plan-tomorrow")
        logger.info("AI_REQUEST_SUCCESS user_id=%s type=plan-tomorrow", user_id)
        return jsonify({"ok": True, "result": result, "remaining": remaining - 1})
    except RuntimeError as e:
        logger.info("AI_REQUEST_FAILED user_id=%s type=plan-tomorrow reason=%s", user_id, e)
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.info("AI_REQUEST_FAILED user_id=%s type=plan-tomorrow reason=%s", user_id, e)
        return jsonify({"error": "AI service unavailable."}), 500


@ai_bp.route("/api/ai/summarize-notes", methods=["POST"])
@api_login_required
def summarize_notes():
    user_id = session["user_id"]
    logger.info("AI_REQUEST_STARTED user_id=%s type=summarize-notes", user_id)

    allowed, remaining = _check_limit(user_id)
    if not allowed:
        return _limit_response()

    try:
        notes  = _read_notes()
        result = ai_service.summarize_notes(notes)
        db.log_ai_usage(user_id, "summarize-notes")
        logger.info("AI_REQUEST_SUCCESS user_id=%s type=summarize-notes", user_id)
        return jsonify({"ok": True, "result": result, "remaining": remaining - 1})
    except RuntimeError as e:
        logger.info("AI_REQUEST_FAILED user_id=%s type=summarize-notes reason=%s", user_id, e)
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.info("AI_REQUEST_FAILED user_id=%s type=summarize-notes reason=%s", user_id, e)
        return jsonify({"error": "AI service unavailable."}), 500
