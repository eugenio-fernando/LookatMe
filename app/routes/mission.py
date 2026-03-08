from flask import Blueprint, jsonify, session

from ..models import db
from ..utils import api_login_required

mission_bp = Blueprint("mission", __name__)


@mission_bp.route("/api/mission/today")
@api_login_required
def get_mission():
    return jsonify(db.get_mission_with_progress(session["user_id"]))
