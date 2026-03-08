import logging

from flask import Blueprint, jsonify, request, session

from ..models import db
from ..utils import api_login_required

commitment_bp = Blueprint("commitment", __name__)
logger = logging.getLogger(__name__)


@commitment_bp.route("/api/commitment/today")
@api_login_required
def get_commitment():
    return jsonify(db.get_commitment(session["user_id"]))


@commitment_bp.route("/api/commitment/set", methods=["POST"])
@api_login_required
def set_commitment():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    if len(text) > 200:
        return jsonify({"error": "Commitment too long (max 200 chars)"}), 400
    return jsonify(db.set_commitment(session["user_id"], text))


@commitment_bp.route("/api/commitment/complete", methods=["POST"])
@api_login_required
def complete_commitment():
    return jsonify(db.complete_commitment(session["user_id"]))
