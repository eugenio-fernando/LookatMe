from flask import Blueprint, jsonify, request, session

from ..models import db
from ..services.activity_service import get_feed_for_user
from ..utils import api_login_required

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/api/activity")
@api_login_required
def get_activity():
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(db.get_activity_feed(session["user_id"], limit=limit))


@activity_bp.route("/api/activity/feed")
@api_login_required
def get_activity_feed():
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(get_feed_for_user(session["user_id"], limit=limit))
