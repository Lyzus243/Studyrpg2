import os
import smtplib
import asyncio
from email.message import EmailMessage
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

# ========================================================================
# CONFIGURATION SECTION - EASILY SWITCH BETWEEN PORTS BY COMMENTING BLOCKS
# ========================================================================

# Option 1: PORT 465 Configuration (Uncomment this block for port 465)
# ------------------------------------------------------------------------
'''
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.sendgrid.net").strip()
SMTP_PORT = 465
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "your_email@example.com").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000").strip()
USE_SSL = True  # Required for port 465
'''
# Option 2: PORT 587 Configuration (Uncomment this block for port 587)
# ------------------------------------------------------------------------

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.sendgrid.net").strip()
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "your_email@example.com").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000").strip()
USE_SSL = False  # STARTTLS will be used instead


# Debug configuration
logger.info(f"SMTP Configuration: Host='{SMTP_HOST}', Port={SMTP_PORT}, SSL={USE_SSL}, User={'***' if SMTP_USER else 'None'}")

# ========================================================================
# EMAIL FUNCTIONS (REMAIN THE SAME FOR BOTH PORTS)
# ========================================================================

async def send_verification_email(to_email: str, username: str, token: str):
    """Send email verification email to user"""
    subject = "Verify your StudyRPG email"
    verify_link = f"{FRONTEND_URL}/auth/verify-email?token={token}"
    body = (
        f"Hi {username},\n\n"
        f"Please verify your email by clicking the link below:\n"
        f"{verify_link}\n\n"
        "If you did not sign up for StudyRPG, please ignore this message.\n\n"
        "Thanks,\n"
        "The StudyRPG Team"
    )
    return await _send_email(to_email, subject, body, debug_level=1)

async def send_broadcast_email(to_email: str, subject: str, message: str):
    """Send broadcast email to a user"""
    body = f"""Hello StudyRPG User,

{message}

Best regards,
The StudyRPG Team"""
    return await _send_email(to_email, subject, body, debug_level=0)

async def _send_email(to_email: str, subject: str, body: str, debug_level: int = 0):
    """Internal email sending function with port configuration"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(body)

    def _send():
        """Synchronous email sending function"""
        logger.info(f"Attempting to send email to {to_email} via port {SMTP_PORT}")
        
        # Validate configuration
        if not SMTP_HOST or SMTP_HOST.lower() in ("localhost", "example.com"):
            raise ValueError(f"Invalid SMTP_HOST: '{SMTP_HOST}'")
        if not SMTP_USER or not SMTP_PASS:
            raise ValueError("SMTP credentials not configured")
        
        try:
            # PORT 465 (Implicit SSL)
            if USE_SSL:
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                    server.set_debuglevel(debug_level)
                    server.login(SMTP_USER, SMTP_PASS)
                    server.send_message(msg)
                    logger.info(f"Email sent successfully via port {SMTP_PORT}")
                    
            # PORT 587 (Explicit STARTTLS)
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                    server.set_debuglevel(debug_level)
                    server.starttls()  # Enable encryption
                    server.login(SMTP_USER, SMTP_PASS)
                    server.send_message(msg)
                    logger.info(f"Email sent successfully via port {SMTP_PORT}")
                    
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}")
            raise
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipient refused: {e}")
            raise
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            raise

    try:
        await asyncio.to_thread(_send)
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

async def test_smtp_connection():
    """Test SMTP connection - useful for debugging"""
    try:
        logger.info(f"Testing SMTP connection to {SMTP_HOST}:{SMTP_PORT}...")
        
        if not SMTP_HOST or SMTP_HOST.lower() in ("localhost", "example.com"):
            logger.error("SMTP_HOST not configured")
            return False
        if not SMTP_USER or not SMTP_PASS:
            logger.error("SMTP credentials not configured")
            return False
        
        def _test():
            # PORT 465 (Implicit SSL)
            if USE_SSL:
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                    server.set_debuglevel(1)
                    server.login(SMTP_USER, SMTP_PASS)
                    logger.info("SMTP connection test successful!")
                    
            # PORT 587 (Explicit STARTTLS)
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                    server.set_debuglevel(1)
                    server.starttls()  # Enable encryption
                    server.login(SMTP_USER, SMTP_PASS)
                    logger.info("SMTP connection test successful!")
                
        await asyncio.to_thread(_test)
        return True
        
    except Exception as e:
        logger.error(f"SMTP connection test failed: {e}")
        return False