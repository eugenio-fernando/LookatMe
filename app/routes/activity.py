from flask import Blueprint, jsonify, request, session

from ..models import db
from ..utils import api_login_required

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/api/activity")
@api_login_required
def get_activity():
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(db.get_activity_feed(session["user_id"], limit=limit))
