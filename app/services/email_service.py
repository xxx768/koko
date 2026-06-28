import logging

import resend

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


async def send_verification_email(to_email: str, username: str, code: str) -> bool:
    """Send a 5-digit email verification code via Resend."""
    try:
        params: resend.Emails.SendParams = {
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Verify your email address",
            "html": _verification_email_html(username, code),
        }
        resend.Emails.send(params)
        logger.info("Verification email sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send verification email to %s: %s", to_email, exc)
        return False


async def send_notification_email(to_email: str, username: str, title: str, message: str) -> bool:
    """Send an in-app notification also via email."""
    try:
        params: resend.Emails.SendParams = {
            "from": settings.email_from,
            "to": [to_email],
            "subject": title,
            "html": _notification_email_html(username, title, message),
        }
        resend.Emails.send(params)
        logger.info("Notification email sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send notification email to %s: %s", to_email, exc)
        return False


# ---------------------------------------------------------------------------
# HTML email templates
# ---------------------------------------------------------------------------

def _verification_email_html(username: str, code: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h2>Nova earns email verification</h2>
  <p>Hello <strong>{username}</strong>,</p>
  <p>Welcome to Nova earns! Please use the following verification code to complete your email verification process:</p>
  <p>Your verification code is:</p>
  <div style="font-size:36px;font-weight:bold;letter-spacing:8px;padding:20px;
              background:#f4f4f4;text-align:center;border-radius:8px;margin:20px 0">
    {code}
  </div>
  <p>This code expires in <strong>10 minutes</strong>.</p>
  <p>If you did not create an account, please ignore this email.</p>
</body>
</html>
"""


def _notification_email_html(username: str, title: str, message: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h2>{title}</h2>
  <p>Hello <strong>{username}</strong>,</p>
  <p>{message}</p>
  <hr>
  <small>This notification was sent by the Nova Earns platform.</small>
</body>
</html>
"""
