import os
from datetime import datetime

from flask import Blueprint, current_app, render_template, send_from_directory, session

from ..models import db
from ..utils import login_required

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
@login_required
def index():
    user = db.get_user_by_id(session["user_id"])
    fun_welcome = session.pop("fun_welcome", None)
    name = (user.get("display_name") or user["email"].split("@")[0]) if user else "there"
    hour = datetime.utcnow().hour
    if 5 <= hour < 12:
        word = "Good morning"
    elif 12 <= hour < 18:
        word = "Good afternoon"
    else:
        word = "Good evening"
    # Only show on first login (last_onboarding_seen is empty = never completed onboarding)
    show_onboarding = bool(user) and not user.get("last_onboarding_seen", "")
    return render_template(
        "dashboard.html",
        greeting_message=f"{word}, {name}",
        show_onboarding=show_onboarding,
        fun_welcome=fun_welcome,
    )


@views_bp.route("/focus")
@login_required
def focus():
    return render_template("focus.html")


@views_bp.route("/learning")
@login_required
def learning():
    return render_template("learning.html")


@views_bp.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


@views_bp.route("/inbox")
@login_required
def inbox():
    return render_template("inbox.html")


@views_bp.route("/invite/<token>")
def invite_page(token):
    return render_template("invite.html", token=token)


@views_bp.route("/invitations")
@login_required
def invitations():
    return render_template("invitations.html")


@views_bp.route("/favicon.svg")
def favicon():
    return send_from_directory(current_app.static_folder, "favicon.svg",
                               mimetype="image/svg+xml")


@views_bp.route("/logo.svg")
def logo():
    return send_from_directory(current_app.static_folder, "logo.svg",
                               mimetype="image/svg+xml")


@views_bp.route("/manifest.json")
def manifest():
    return send_from_directory(current_app.static_folder, "manifest.json")


@views_bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(current_app.static_folder, "sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@views_bp.route("/icons/<path:filename>")
def icons(filename):
    return send_from_directory(
        os.path.join(current_app.static_folder, "icons"), filename
    )
