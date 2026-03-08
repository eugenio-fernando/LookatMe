import logging
from datetime import date

from flask import Blueprint, jsonify, session

from ..models import db
from ..utils import api_login_required
from ..services import ai_service

ai_bp = Blueprint("ai", __name__)
logger = logging.getLogger(__name__)

_rate: dict = {}   # {user_id: {"date": str, "count": int}}
MAX_CALLS_PER_DAY = 3


def _allow(user_id: int) -> bool:
    today = date.today().isoformat()
    entry = _rate.get(user_id)
    if not entry or entry["date"] != today:
        _rate[user_id] = {"date": today, "count": 0}
    if _rate[user_id]["count"] >= MAX_CALLS_PER_DAY:
        return False
    _rate[user_id]["count"] += 1
    return True


def _remaining(user_id: int) -> int:
    today = date.today().isoformat()
    entry = _rate.get(user_id)
    if not entry or entry["date"] != today:
        return MAX_CALLS_PER_DAY
    return max(0, MAX_CALLS_PER_DAY - entry["count"])


@ai_bp.route("/api/ai/analyze-day", methods=["POST"])
@api_login_required
def analyze_day():
    user_id      = session["user_id"]
    workspace_id = session.get("workspace_id")
    if not _allow(user_id):
        return jsonify({"error": "Daily AI limit reached (3 per day). Try again tomorrow."}), 429
    try:
        tasks  = db.get_todos(user_id, workspace_id) or []
        notes  = db.get_notes(user_id) or []
        result = ai_service.analyze_day(tasks, notes)
        logger.info("AI_ANALYZE_DAY user_id=%s", user_id)
        return jsonify({"ok": True, "result": result, "remaining": _remaining(user_id)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.exception("AI analyze-day error: %s", e)
        return jsonify({"error": "AI service unavailable."}), 500


@ai_bp.route("/api/ai/plan-tomorrow", methods=["POST"])
@api_login_required
def plan_tomorrow():
    user_id      = session["user_id"]
    workspace_id = session.get("workspace_id")
    if not _allow(user_id):
        return jsonify({"error": "Daily AI limit reached (3 per day). Try again tomorrow."}), 429
    try:
        tasks  = db.get_todos(user_id, workspace_id) or []
        notes  = db.get_notes(user_id) or []
        result = ai_service.plan_tomorrow(tasks, notes)
        logger.info("AI_PLAN_TOMORROW user_id=%s", user_id)
        return jsonify({"ok": True, "result": result, "remaining": _remaining(user_id)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.exception("AI plan-tomorrow error: %s", e)
        return jsonify({"error": "AI service unavailable."}), 500


@ai_bp.route("/api/ai/summarize-notes", methods=["POST"])
@api_login_required
def summarize_notes():
    user_id = session["user_id"]
    if not _allow(user_id):
        return jsonify({"error": "Daily AI limit reached (3 per day). Try again tomorrow."}), 429
    try:
        notes  = db.get_notes(user_id) or []
        result = ai_service.summarize_notes(notes)
        logger.info("AI_SUMMARIZE_NOTES user_id=%s", user_id)
        return jsonify({"ok": True, "result": result, "remaining": _remaining(user_id)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.exception("AI summarize-notes error: %s", e)
        return jsonify({"error": "AI service unavailable."}), 500
