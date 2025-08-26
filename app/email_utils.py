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
# CONFIGURATION SECTION - AUTOMATIC PORT DETECTION
# ========================================================================

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.sendgrid.net").strip()
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "your_email@example.com").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000").strip()

# Define port configurations to try (in order of preference)
PORT_CONFIGS = [
    (465, True),   # Port 465 with SSL
    (587, False)   # Port 587 with STARTTLS
]

# Debug configuration
logger.info(f"SMTP Configuration: Host='{SMTP_HOST}', User={'***' if SMTP_USER else 'None'}")

# ========================================================================
# EMAIL FUNCTIONS WITH AUTOMATIC PORT DETECTION
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
    """Internal email sending function with automatic port detection"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(body)

    def _send():
        """Synchronous email sending function with automatic port selection"""
        # Validate configuration
        if not SMTP_HOST or SMTP_HOST.lower() in ("localhost", "example.com"):
            raise ValueError(f"Invalid SMTP_HOST: '{SMTP_HOST}'")
        if not SMTP_USER or not SMTP_PASS:
            raise ValueError("SMTP credentials not configured")
        
        last_exception = None
        
        # Try each port configuration in order
        for port, use_ssl in PORT_CONFIGS:
            try:
                logger.info(f"Attempting to send email to {to_email} via port {port} (SSL: {use_ssl})")
                
                if use_ssl:
                    # PORT 465 (Implicit SSL)
                    with smtplib.SMTP_SSL(SMTP_HOST, port, timeout=30) as server:
                        server.set_debuglevel(debug_level)
                        server.login(SMTP_USER, SMTP_PASS)
                        server.send_message(msg)
                        logger.info(f"Email sent successfully via port {port}")
                        return True
                else:
                    # PORT 587 (Explicit STARTTLS)
                    with smtplib.SMTP(SMTP_HOST, port, timeout=30) as server:
                        server.set_debuglevel(debug_level)
                        server.starttls()  # Enable encryption
                        server.login(SMTP_USER, SMTP_PASS)
                        server.send_message(msg)
                        logger.info(f"Email sent successfully via port {port}")
                        return True
                        
            except Exception as e:
                last_exception = e
                logger.warning(f"Failed to send via port {port}: {e}")
                continue
        
        # If all port configurations failed
        if last_exception:
            logger.error(f"All SMTP port configurations failed. Last error: {last_exception}")
            raise last_exception

    try:
        await asyncio.to_thread(_send)
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

async def test_smtp_connection():
    """Test SMTP connection with automatic port detection"""
    try:
        # Validate configuration
        if not SMTP_HOST or SMTP_HOST.lower() in ("localhost", "example.com"):
            logger.error("SMTP_HOST not configured")
            return False
        if not SMTP_USER or not SMTP_PASS:
            logger.error("SMTP credentials not configured")
            return False
        
        last_exception = None
        
        # Try each port configuration in order
        for port, use_ssl in PORT_CONFIGS:
            try:
                logger.info(f"Testing SMTP connection to {SMTP_HOST}:{port}...")
                
                def _test():
                    if use_ssl:
                        with smtplib.SMTP_SSL(SMTP_HOST, port, timeout=30) as server:
                            server.set_debuglevel(1)
                            server.login(SMTP_USER, SMTP_PASS)
                    else:
                        with smtplib.SMTP(SMTP_HOST, port, timeout=30) as server:
                            server.set_debuglevel(1)
                            server.starttls()
                            server.login(SMTP_USER, SMTP_PASS)
                
                await asyncio.to_thread(_test)
                logger.info(f"SMTP connection test successful via port {port}!")
                return True
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Connection test failed for port {port}: {e}")
                continue
        
        # If all port configurations failed
        if last_exception:
            logger.error(f"All SMTP connection tests failed. Last error: {last_exception}")
            return False
            
    except Exception as e:
        logger.error(f"SMTP connection test failed: {e}")
        return False