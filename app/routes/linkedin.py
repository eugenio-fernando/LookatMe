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
import re
import string
from html import unescape
from urllib.parse import urlparse, urlunparse

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


def _normalize_linkedin_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw

    p = urlparse(raw)
    scheme = "https"
    netloc = p.netloc.lower()
    if netloc == "linkedin.com":
        netloc = "www.linkedin.com"
    path = p.path or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def _valid_linkedin_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme != "https":
        return False
    if p.netloc not in {"www.linkedin.com", "linkedin.com"}:
        return False
    # Personal public profiles are under /in/<slug>
    return p.path.startswith("/in/")


def _candidate_profile_urls(url: str) -> list[str]:
    base = _normalize_linkedin_url(url)
    if not base:
        return []

    parsed = urlparse(base)
    base_path = parsed.path.rstrip("/")
    candidates = [
        urlunparse(("https", "www.linkedin.com", base_path, "", "", "")),
        urlunparse(("https", "www.linkedin.com", base_path + "/", "", "", "")),
    ]
    # Some profiles render differently with this query in public contexts
    candidates.append(candidates[1] + "?trk=public_profile")
    # De-dup while preserving order
    return list(dict.fromkeys(candidates))


def _normalize_for_match(text: str) -> str:
    t = unescape((text or "").lower())
    # Decode escaped unicode sequences that may appear in embedded JSON
    t = re.sub(r"\\u([0-9a-f]{4})", lambda m: chr(int(m.group(1), 16)), t)
    # Normalize dash variants to a plain hyphen
    t = t.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
    t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    return t


def _contains_verification_code(html_text: str, code: str) -> bool:
    hay = _normalize_for_match(html_text)
    needle = _normalize_for_match(code)
    if needle in hay:
        return True

    # Tolerate spacing/punctuation/encoding differences around the code
    needle_compact = re.sub(r"[^a-z0-9]", "", needle)
    hay_compact = re.sub(r"[^a-z0-9]", "", hay)
    return bool(needle_compact and needle_compact in hay_compact)


def _looks_like_login_wall(html_text: str, final_url: str, status_code: int) -> bool:
    text = (html_text or "").lower()
    final = (final_url or "").lower()
    return (
        status_code in {401, 403, 429}
        or "/authwall" in final
        or "/checkpoint/" in final
        or "join linkedin" in text
        or "sign in to linkedin" in text
        or "linkedin.com/login" in text
    )


@linkedin_bp.route("/api/linkedin/start-verification", methods=["POST"])
@api_login_required
def start_verification():
    user_id = session["user_id"]

    user = db.get_user_by_id(user_id)
    if user and user.get("linkedin_verified"):
        return jsonify({"error": "already_verified", "message": "LinkedIn already verified."}), 400

    raw_url = (request.json or {}).get("linkedin_url", (request.json or {}).get("url", "")).strip()
    url = _normalize_linkedin_url(raw_url)
    if not url:
        return jsonify({"error": "LinkedIn profile URL is required."}), 400
    if not _valid_linkedin_url(url):
        return jsonify({"error": "Must be a public LinkedIn profile URL like https://www.linkedin.com/in/yourname"}), 400

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

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    fetches = 0
    login_wall_hits = 0
    for candidate_url in _candidate_profile_urls(url):
        try:
            resp = requests.get(candidate_url, headers=headers, timeout=_FETCH_TIMEOUT, allow_redirects=True)
        except requests.RequestException as exc:
            logger.warning("LINKEDIN_FETCH_ERROR user_id=%s url=%s err=%s", user_id, candidate_url, exc)
            continue

        fetches += 1
        if _looks_like_login_wall(resp.text, resp.url, resp.status_code):
            login_wall_hits += 1
            continue

        if _contains_verification_code(resp.text, code):
            db.set_linkedin_verified(user_id)
            logger.info("LINKEDIN_VERIFIED user_id=%s", user_id)
            return jsonify({"verified": True})

    if fetches == 0:
        return jsonify({"verified": False, "message": "Could not reach LinkedIn. Please try again."}), 503

    if login_wall_hits == fetches:
        logger.info("LINKEDIN_VERIFICATION_BLOCKED user_id=%s", user_id)
        return jsonify({
            "verified": False,
            "message": (
                "LinkedIn blocked automated public verification right now. "
                "Make sure your profile visibility is public and try again in a minute."
            ),
        }), 503

    db.increment_linkedin_attempts(user_id)

    logger.info("LINKEDIN_VERIFICATION_FAILED user_id=%s attempts=%s", user_id, attempts + 1)
    return jsonify({
        "verified": False,
        "message":  (
            "Verification code was not found on your public LinkedIn profile. "
            "Confirm the exact code is visible in your headline/about, save, then retry."
        ),
    }), 422
