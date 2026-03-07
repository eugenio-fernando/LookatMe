"""
Shared decorators for Write it Down.
"""

from functools import wraps

from flask import jsonify, redirect, session, url_for


def login_required(f):
    """For page routes — redirects unauthenticated requests to /login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    """For API routes — returns 401 JSON for unauthenticated requests."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated
