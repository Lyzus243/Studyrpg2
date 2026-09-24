import os
import aiohttp
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
EMAIL_FROM     = os.getenv("EMAIL_FROM", "onboarding@resend.dev").strip()
FRONTEND_URL   = os.getenv("FRONTEND_URL", "http://localhost:8000").strip()
DEV_MODE       = os.getenv("DEV_MODE", "true").lower() == "true"

logger.info(f"Resend API Key: {'SET' if RESEND_API_KEY else 'NOT SET'} | From: {EMAIL_FROM} | DEV_MODE: {DEV_MODE}")


async def _send_via_resend(to_email: str, subject: str, html: str) -> bool:
    """Send email through Resend API."""
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not set.")
        return False

    payload = {
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post("https://api.resend.com/emails", json=payload, headers=headers) as resp:
                if resp.status == 200 or resp.status == 201:
                    logger.info(f"Email sent via Resend to {to_email}")
                    return True
                text = await resp.text()
                logger.error(f"Resend error {resp.status}: {text}")
                return False
    except Exception as e:
        logger.error(f"Resend request failed: {e}")
        return False


async def send_verification_email(to_email: str, username: str, token: str) -> bool:
    """Send email verification link."""
    verify_link = f"{FRONTEND_URL}/auth/verify-email?token={token}"

    if DEV_MODE:
        print("\n" + "="*60)
        print("📧 VERIFICATION EMAIL (DEV MODE)")
        print("="*60)
        print(f"To:    {to_email}")
        print(f"User:  {username}")
        print(f"Token: {token}")
        print(f"Link:  {verify_link}")
        print("="*60 + "\n")
        logger.info(f"[DEV] Verification token for {username}: {token}")
        return True

    subject = "Verify your StudyRPG email"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;background:#0f172a;color:#DCDDDE;border-radius:12px;">
      <h2 style="color:#38bdf8;">Welcome to StudyRPG, {username}!</h2>
      <p>Click the button below to verify your email address.</p>
      <a href="{verify_link}" style="display:inline-block;margin:1.5rem 0;padding:0.75rem 1.5rem;background:#5865F2;color:white;border-radius:8px;text-decoration:none;font-weight:bold;">Verify Email</a>
      <p style="color:#72767D;font-size:0.85rem;">If you did not create an account, you can ignore this email.</p>
    </div>
    """
    return await _send_via_resend(to_email, subject, html)


async def send_broadcast_email(to_email: str, subject: str, message: str) -> bool:
    """Send a broadcast/announcement email."""
    if DEV_MODE:
        print("\n" + "="*60)
        print("📢 BROADCAST EMAIL (DEV MODE)")
        print("="*60)
        print(f"To:      {to_email}")
        print(f"Subject: {subject}")
        print(f"Message: {message}")
        print("="*60 + "\n")
        return True

    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;background:#0f172a;color:#DCDDDE;border-radius:12px;">
      <h2 style="color:#38bdf8;">StudyRPG Announcement</h2>
      <p>{message}</p>
      <p style="color:#72767D;font-size:0.85rem;margin-top:2rem;">— The StudyRPG Team</p>
    </div>
    """
    return await _send_via_resend(to_email, subject, html)


async def send_email_unified(to_email: str, subject: str, body: str) -> bool:
    """Generic email sender."""
    html = f"""<div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;background:#0f172a;color:#DCDDDE;border-radius:12px;"><p>{body}</p></div>"""
    return await _send_via_resend(to_email, subject, html)
