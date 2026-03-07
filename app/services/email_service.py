"""
Email service — wraps Resend SDK for all transactional emails.

Required Fly secrets (set with `fly secrets set KEY=value`):
    RESEND_API_KEY   — API key from resend.com  (e.g. re_xxxxxxxxxxxx)
    APP_BASE_URL     — public app URL            (e.g. https://lookatme.fly.dev)
    EMAIL_FROM       — verified sender address   (e.g. LookatMe <hello@yourdomain.com>)

Until a custom domain is verified in Resend, use:
    EMAIL_FROM=LookatMe <onboarding@resend.dev>
    (Resend's shared test address — only delivers to the account owner's email)
"""

import logging
import os

import resend

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str) -> bool:
    """
    Send an email via Resend.

    Returns True on success.
    Returns False and logs the reason when:
      - RESEND_API_KEY is not set
      - the API call fails for any reason (bad key, unverified domain, network error)

    Never raises — callers can always treat email as best-effort.
    """
    # Read config inside the function so env vars set after module import are seen
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_address = os.environ.get("EMAIL_FROM", "LookatMe <onboarding@resend.dev>")
    base_url = os.environ.get("APP_BASE_URL", "https://lookatme.fly.dev")  # noqa: F841 (used by callers via module-level)

    # ── Key presence check ──────────────────────────────────────────────
    if not api_key:
        logger.warning("EMAIL_SKIP: RESEND_API_KEY is not set — email to %s not sent", to)
        return False

    if api_key in ("local_testing_disabled", "disabled", "skip"):
        logger.info("EMAIL_SKIP: RESEND_API_KEY=%s — email to %s not sent (dev mode)", api_key, to)
        return False

    key_preview = api_key[:6] + "..." if len(api_key) > 6 else "???"
    logger.info("EMAIL_ATTEMPT: to=%s subject=%r from=%s key_prefix=%s", to, subject, from_address, key_preview)

    # ── Send ────────────────────────────────────────────────────────────
    try:
        resend.api_key = api_key
        response = resend.Emails.send({
            "from": from_address,
            "to":   [to],
            "subject": subject,
            "html": html,
        })
        logger.info("EMAIL_OK: to=%s id=%s", to, getattr(response, "id", response))
        return True

    except resend.exceptions.ResendError as exc:
        logger.error(
            "EMAIL_FAIL [ResendError]: to=%s subject=%r key_prefix=%s error=%s",
            to, subject, key_preview, exc,
        )
        return False

    except Exception as exc:  # network timeout, unexpected SDK error, etc.
        logger.error(
            "EMAIL_FAIL [%s]: to=%s subject=%r error=%s",
            type(exc).__name__, to, subject, exc,
        )
        return False


# ── Public senders ──────────────────────────────────────────────────────────

def send_verification_email(to_email: str, token: str) -> bool:
    """Send account verification email with a one-click link."""
    base_url = os.environ.get("APP_BASE_URL", "https://lookatme.fly.dev")
    link = f"{base_url}/verify/{token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#3b82f6">Verify your LookatMe account</h2>
      <p>Click the button below to verify your email address. The link expires in 24 hours.</p>
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
    return _send(to_email, "Verify your LookatMe account", html)


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
    return _send(to_email, "Your LookatMe sign-in link", html)


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
    return _send(to_email, "Reset your LookatMe password", html)
