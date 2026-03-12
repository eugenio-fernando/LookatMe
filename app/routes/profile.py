import logging
import os

from flask import Blueprint, jsonify, request, session
from werkzeug.utils import secure_filename

from ..models import db
from ..utils import api_login_required

profile_bp = Blueprint("profile", __name__)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(__file__), "..", "static", "uploads", "avatars"
)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
SUPPORTED_LANGUAGES = {"en", "es", "it"}


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
        "avatar_url",
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
@profile_bp.route("/api/profile/upload-avatar", methods=["POST"])
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
    filename = secure_filename(f"user_{session['user_id']}.{ext}")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    avatar_path = f"/static/uploads/avatars/{filename}"
    user = db.update_profile(
        session["user_id"],
        avatar_path=avatar_path,
        avatar_url=avatar_path,
    )
    return jsonify(user)


@profile_bp.route("/api/profile/language", methods=["GET"])
@api_login_required
def get_language():
    user = db.get_user_by_id(session["user_id"])
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"language": user.get("language", "en")})


@profile_bp.route("/api/profile/language", methods=["POST"])
@api_login_required
def set_language():
    body = request.get_json(silent=True) or {}
    language = str(body.get("language", "en")).strip().casefold()
    if language not in SUPPORTED_LANGUAGES:
        return jsonify({"error": "invalid language"}), 400

    user = db.update_user_language(session["user_id"], language)
    session["lang"] = language
    return jsonify({"ok": True, "language": user.get("language", language)})


@profile_bp.route("/api/user/set-language", methods=["POST"])
@api_login_required
def set_user_language():
    body = request.get_json(silent=True) or {}
    language = str(body.get("language", "en")).strip().casefold()
    if language not in SUPPORTED_LANGUAGES:
        return jsonify({"error": "invalid language"}), 400
    user = db.update_user_language(session["user_id"], language)
    session["lang"] = language
    return jsonify({"ok": True, "language": user.get("language", language)})
