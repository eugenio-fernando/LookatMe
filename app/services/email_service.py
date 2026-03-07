"""
Email service — wraps Resend SDK for all transactional emails.

Required environment variable:
    RESEND_API_KEY   — API key from resend.com

From address: noreply@lookatme.fly.dev (update once domain is verified in Resend)
"""

import os

import resend

BASE_URL = os.environ.get("APP_BASE_URL", "https://lookatme.fly.dev")
FROM_ADDRESS = os.environ.get("EMAIL_FROM", "LookatMe <noreply@lookatme.fly.dev>")


def _send(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success, False if not configured."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return False
    resend.api_key = api_key
    resend.Emails.send({
        "from": FROM_ADDRESS,
        "to": [to],
        "subject": subject,
        "html": html,
    })
    return True


def send_verification_email(to_email: str, token: str) -> bool:
    """Send account verification email with a one-click link."""
    link = f"{BASE_URL}/verify/{token}"
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
    link = f"{BASE_URL}/login/{token}"
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
    link = f"{BASE_URL}/reset/{token}"
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
