"""
Email service — wraps Resend SDK for all transactional emails.

Required Fly secrets (set with `fly secrets set KEY=value -a lookatme`):
    RESEND_API_KEY   — API key from resend.com       (e.g. re_xxxxxxxxxxxx)
    APP_BASE_URL     — public app URL                 (e.g. https://lookatme.fly.dev)
    VERIFY_EMAIL_FROM — sender for verification emails
    SUPPORT_EMAIL_FROM — sender for support/reset/magic-link emails
    REPLY_TO_EMAIL   — optional reply-to address for all transactional emails

⚠ Sender address rules:
  • onboarding@resend.dev  — Resend shared test sender.
                             Emails are ONLY delivered to the Resend account owner's
                             email address, regardless of the `to` field.
                             Use for development/testing only.
  • verify@aitoptutor.com  — Verified production sender (aitoptutor.com domain).
  • Any other address      — The domain MUST be verified in the Resend dashboard.
                             Unverified domains cause HTTP 403 / invalid_api_key errors.
"""

import logging
import os

import resend

from ..models import db

logger = logging.getLogger(__name__)


def _sender_for(email_type: str, explicit_from: str | None = None) -> str:
    if explicit_from and explicit_from.strip():
        return explicit_from.strip()
    if email_type == "verification":
        return (
            os.environ.get("VERIFY_EMAIL_FROM", "").strip()
            or os.environ.get("EMAIL_FROM", "").strip()
            or "LookatMe <verify@aitoptutor.com>"
        )
    if email_type in ("magic_login", "password_reset", "support"):
        return (
            os.environ.get("SUPPORT_EMAIL_FROM", "").strip()
            or os.environ.get("EMAIL_FROM", "").strip()
            or "LookatMe <verify@aitoptutor.com>"
        )
    return os.environ.get("EMAIL_FROM", "").strip() or "LookatMe <verify@aitoptutor.com>"


def _send(
    to: str,
    subject: str,
    html: str,
    *,
    email_type: str,
    from_address: str | None = None,
) -> bool:
    """
    Send an email via Resend.

    Returns True on success, False on any failure.
    Never raises — email is always treated as best-effort.
    All failures are logged with enough detail to diagnose in fly logs.
    """
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = _sender_for(email_type, from_address)
    reply_to = os.environ.get("REPLY_TO_EMAIL", "").strip()

    # ── Guard: key missing ───────────────────────────────────────────────
    if not api_key:
        logger.warning(
            "EMAIL_SKIP: RESEND_API_KEY not set — skipping email to=%s subject=%r",
            to, subject,
        )
        return False

    # ── Guard: known dev-mode placeholder values ─────────────────────────
    if api_key in ("local_testing_disabled", "disabled", "skip"):
        logger.info(
            "EMAIL_SKIP: dev-mode key (%s) — skipping email to=%s subject=%r",
            api_key, to, subject,
        )
        return False

    # ── Warn if using the shared test sender ─────────────────────────────
    if "onboarding@resend.dev" in sender:
        logger.warning(
            "EMAIL_WARN: using Resend test sender (%s) — email will be delivered "
            "to the Resend account owner, NOT to to=%s",
            sender, to,
        )

    key_preview = api_key[:6] + "..." if len(api_key) > 6 else "???"
    logger.info(
        "EMAIL_SEND_ATTEMPT event=EMAIL_SEND_ATTEMPT type=%s to=%s subject=%r from=%s reply_to=%s key_prefix=%s",
        email_type, to, subject, sender, reply_to or "-", key_preview,
    )
    try:
        db.create_activity_event(
            user_id=0,
            event_type="EMAIL_SEND_ATTEMPT",
            description=f"{email_type} email attempt to {to}",
            metadata={"subject": subject, "from": sender, "email_type": email_type},
        )
    except Exception:
        pass

    # ── Send ─────────────────────────────────────────────────────────────
    try:
        resend.api_key = api_key
        payload = {
            "from":    sender,
            "to":      [to],
            "subject": subject,
            "html":    html,
        }
        if reply_to:
            payload["reply_to"] = reply_to
        response = resend.Emails.send(payload)
        logger.info(
            "EMAIL_SEND_SUCCESS event=EMAIL_SEND_SUCCESS type=%s sender=%s to=%s subject=%r id=%s response=%r",
            email_type, sender, to, subject, getattr(response, "id", None), response,
        )
        try:
            db.create_activity_event(
                user_id=0,
                event_type="EMAIL_SEND_SUCCESS",
                description=f"{email_type} email accepted by provider for {to}",
                metadata={"subject": subject, "email_type": email_type},
            )
        except Exception:
            pass
        return True

    except resend.exceptions.ResendError as exc:
        # Log code + error_type separately so fly logs can distinguish:
        #   403 invalid_api_key  → bad key OR unverified sender domain
        #   422 validation_error → malformed request / unverified domain
        #   429 rate_limit_*     → too many requests
        #   500 application_error → Resend-side problem
        logger.error(
            "EMAIL_SEND_FAIL event=EMAIL_SEND_FAIL type=%s [ResendError]: to=%s subject=%r "
            "http_code=%s error_type=%s message=%s key_prefix=%s",
            email_type, to, subject,
            getattr(exc, "code", "?"),
            getattr(exc, "error_type", "?"),
            exc.message if hasattr(exc, "message") else str(exc),
            key_preview,
        )
        try:
            db.create_activity_event(
                user_id=0,
                event_type="EMAIL_SEND_FAIL",
                description=f"{email_type} email failed for {to}",
                metadata={"subject": subject, "email_type": email_type, "error": str(exc)},
            )
        except Exception:
            pass
        return False

    except Exception as exc:
        logger.error(
            "EMAIL_SEND_FAIL event=EMAIL_SEND_FAIL type=%s [%s]: to=%s subject=%r error=%s",
            email_type, type(exc).__name__, to, subject, exc,
        )
        try:
            db.create_activity_event(
                user_id=0,
                event_type="EMAIL_SEND_FAIL",
                description=f"{email_type} email failed for {to}",
                metadata={"subject": subject, "email_type": email_type, "error": str(exc)},
            )
        except Exception:
            pass
        return False


# ── Public senders ───────────────────────────────────────────────────────────

def send_verification_email(to_email: str, token: str, *, from_address: str | None = None) -> bool:
    """Send account verification email with a one-click link."""
    base_url = os.environ.get("APP_BASE_URL", "https://lookatme.fly.dev")
    link = f"{base_url}/verify/{token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#3b82f6">Verify your LookatMe account</h2>
      <p>Click the button below to verify your email address. The link expires in 15 minutes.</p>
      <a href="{link}"
         style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 24px;
                border-radius:8px;text-decoration:none;font-weight:600">
        Verify email
      </a>
      <p style="color:#6b7280;font-size:12px;margin-top:24px">
        If you didn't create a LookatMe account, you can ignore this email.
      </p>
    </div>
    """
    return _send(
        to_email,
        "Verify your LookatMe account",
        html,
        email_type="verification",
        from_address=from_address,
    )


def send_magic_login_link(to_email: str, token: str) -> bool:
    """Send a magic sign-in link (passwordless login)."""
    base_url = os.environ.get("APP_BASE_URL", "https://lookatme.fly.dev")
    link = f"{base_url}/login/{token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#3b82f6">Sign in to LookatMe</h2>
      <p>Click the button below to sign in. The link expires in 15 minutes and can only be used once.</p>
      <a href="{link}"
         style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 24px;
                border-radius:8px;text-decoration:none;font-weight:600">
        Sign in
      </a>
      <p style="color:#6b7280;font-size:12px;margin-top:24px">
        If you didn't request this link, you can ignore this email.
      </p>
    </div>
    """
    return _send(
        to_email,
        "Your LookatMe sign-in link",
        html,
        email_type="magic_login",
    )


def send_password_reset_email(to_email: str, token: str) -> bool:
    """Send a password reset link."""
    base_url = os.environ.get("APP_BASE_URL", "https://lookatme.fly.dev")
    link = f"{base_url}/reset/{token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#3b82f6">Reset your LookatMe password</h2>
      <p>Click the button below to choose a new password. The link expires in 1 hour.</p>
      <a href="{link}"
         style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 24px;
                border-radius:8px;text-decoration:none;font-weight:600">
        Reset password
      </a>
      <p style="color:#6b7280;font-size:12px;margin-top:24px">
        If you didn't request a password reset, you can ignore this email.
      </p>
    </div>
    """
    return _send(
        to_email,
        "Reset your LookatMe password",
        html,
        email_type="password_reset",
    )
