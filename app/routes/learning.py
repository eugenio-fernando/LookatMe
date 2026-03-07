from datetime import datetime

from flask import Blueprint, jsonify, request

from ..models import db
from ..utils import api_login_required

learning_bp = Blueprint("learning", __name__)


@learning_bp.route("/api/learning")
@api_login_required
def get_learning():
    return jsonify(db.get_learning_items())


@learning_bp.route("/api/learning", methods=["POST"])
@api_login_required
def create_learning():
    body = request.get_json(silent=True) or {}
    title = body.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    item = db.create_learning_item(
        title=title,
        category=body.get("category", "general").strip(),
        progress=int(body.get("progress", 0)),
        hours_studied=float(body.get("hours_studied", 0)),
        notes=body.get("notes", "").strip(),
        created_at=datetime.now().isoformat(),
    )
    return jsonify(item), 201


@learning_bp.route("/api/learning/<int:item_id>", methods=["PATCH"])
@api_login_required
def update_learning(item_id):
    body = request.get_json(silent=True) or {}
    try:
        item = db.update_learning_item(
            item_id=item_id,
            progress=int(body.get("progress", 0)),
            hours_studied=float(body.get("hours_studied", 0)),
            notes=body.get("notes", "").strip(),
        )
        return jsonify(item)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@learning_bp.route("/api/learning/<int:item_id>", methods=["DELETE"])
@api_login_required
def delete_learning(item_id):
    try:
        db.delete_learning_item(item_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 404
