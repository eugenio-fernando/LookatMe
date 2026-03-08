"""
LinkedIn profile verification.

Flow:
  1. POST /api/linkedin/start-verification  → generate code, return instructions
  2. User adds code to their LinkedIn bio/headline and saves
  3. POST /api/linkedin/verify              → fetch profile HTML, check for code

Note: LinkedIn aggressively restricts unauthenticated access. The HTML fetch
may receive a login-gate page rather than the actual profile. If verification
fails consistently, consider a manual/honour-system fallback.
"""

import logging
import random
import string

import requests

from flask import Blueprint, jsonify, request, session

from ..models import db
from ..utils import api_login_required

linkedin_bp = Blueprint("linkedin", __name__)
logger = logging.getLogger(__name__)

_FETCH_TIMEOUT   = 10   # seconds
_MAX_ATTEMPTS    = 5    # max verify attempts before lockout


def _generate_code() -> str:
    digits = "".join(random.choices(string.digits, k=6))
    return f"LOOKATME-VERIFY-{digits}"


def _valid_linkedin_url(url: str) -> bool:
    return url.startswith("https://www.linkedin.com/") or url.startswith(
        "https://linkedin.com/"
    )


@linkedin_bp.route("/api/linkedin/start-verification", methods=["POST"])
@api_login_required
def start_verification():
    user_id = session["user_id"]

    user = db.get_user_by_id(user_id)
    if user and user.get("linkedin_verified"):
        return jsonify({"error": "already_verified", "message": "LinkedIn already verified."}), 400

    url = (request.json or {}).get("linkedin_url", (request.json or {}).get("url", "")).strip()
    if not url:
        return jsonify({"error": "LinkedIn profile URL is required."}), 400
    if not _valid_linkedin_url(url):
        return jsonify({"error": "Must be a linkedin.com profile URL."}), 400

    code = _generate_code()
    db.set_linkedin_verification(user_id, url, code)
    logger.info("LINKEDIN_VERIFICATION_STARTED user_id=%s", user_id)

    return jsonify({
        "ok":                True,
        "verification_code": code,
        "code":              code,   # backwards-compat alias
        "instructions": (
            "Add this code temporarily to your LinkedIn headline or bio, "
            "save your profile, then click Verify. "
            "You can remove it after verification."
        ),
    })


@linkedin_bp.route("/api/linkedin/verify", methods=["POST"])
@api_login_required
def verify():
    user_id = session["user_id"]

    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    if user.get("linkedin_verified"):
        return jsonify({"error": "already_verified", "message": "Already verified."}), 400

    # Rate-limit check
    attempts = db.get_linkedin_attempts(user_id)
    if attempts >= _MAX_ATTEMPTS:
        return jsonify({
            "verified": False,
            "message":  f"Too many verification attempts ({_MAX_ATTEMPTS} max). Please contact support.",
        }), 429

    url  = user.get("linkedin_url")
    code = db.get_linkedin_verification_code(user_id)

    if not url or not code:
        return jsonify({"error": "Start verification first."}), 400

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=_FETCH_TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        logger.warning("LINKEDIN_FETCH_ERROR user_id=%s err=%s", user_id, exc)
        return jsonify({"verified": False, "message": "Could not reach LinkedIn. Please try again."}), 503

    db.increment_linkedin_attempts(user_id)

    if code in resp.text:
        db.set_linkedin_verified(user_id)
        logger.info("LINKEDIN_VERIFIED user_id=%s", user_id)
        return jsonify({"verified": True})

    logger.info("LINKEDIN_VERIFICATION_FAILED user_id=%s attempts=%s", user_id, attempts + 1)
    return jsonify({
        "verified": False,
        "message":  (
            "Verification code not found on LinkedIn profile. "
            "Make sure you saved your bio after adding the code, then try again."
        ),
    }), 422
