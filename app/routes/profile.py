import logging
import os

from flask import Blueprint, jsonify, request, session
from werkzeug.utils import secure_filename

from ..models import db
from ..utils import api_login_required

profile_bp = Blueprint("profile", __name__)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@profile_bp.route("/api/profile")
@api_login_required
def get_profile():
    user = db.get_user_by_id(session["user_id"])
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@profile_bp.route("/api/profile", methods=["PATCH"])
@api_login_required
def update_profile():
    body = request.get_json(silent=True) or {}
    allowed_genders = {"male", "female", "non_binary", "prefer_not_to_say"}
    if "gender" in body and body["gender"] not in allowed_genders:
        return jsonify({"error": "Invalid gender value"}), 400

    allowed_fields = {
        "display_name", "bio", "company",
        "address", "city", "zip_code", "phone", "hobbies", "interests", "gender",
        "instagram_username", "favorite_topics", "favorite_news_sources", "favorite_teams",
    }
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    user = db.update_profile(session["user_id"], **updates)
    return jsonify(user)


@profile_bp.route("/api/user/onboarding-seen", methods=["POST"])
@api_login_required
def onboarding_seen():
    db.update_onboarding_seen(session["user_id"])
    logger.info("ONBOARDING_SEEN_UPDATED user_id=%s", session["user_id"])
    return jsonify({"ok": True})


@profile_bp.route("/api/profile/avatar", methods=["POST"])
@api_login_required
def upload_avatar():
    if "avatar" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["avatar"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not _allowed(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"avatar_{session['user_id']}.{ext}")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    avatar_url = f"/static/uploads/{filename}"
    user = db.update_profile(session["user_id"], avatar_url=avatar_url)
    return jsonify(user)
