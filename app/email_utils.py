import os
import asyncio
import aiohttp
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

# ========================================================================
# CONFIGURATION SECTION
# ========================================================================

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "your_email@example.com").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000").strip()

# Development mode - ALWAYS print tokens to console
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

# Debug configuration
logger.info(f"SendGrid API Configuration: API Key={'***' if SENDGRID_API_KEY else 'None'}, From='{EMAIL_FROM}'")
logger.info(f"Development Mode: {DEV_MODE}")

# ========================================================================
# EMAIL FUNCTIONS - WITH CONSOLE OUTPUT FOR DEVELOPMENT
# ========================================================================

async def send_verification_email(to_email: str, username: str, token: str):
    """Send email verification email to user - PRINTS TO CONSOLE IN DEV MODE"""
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
    
    # ALWAYS PRINT TOKEN TO CONSOLE IN DEV MODE
    if DEV_MODE:
        print("\n" + "="*70)
        print("🔥 EMAIL VERIFICATION TOKEN (DEV MODE) 🔥")
        print("="*70)
        print(f"👤 User: {username}")
        print(f"📧 Email: {to_email}")
        print(f"🎫 Token: {token}")
        print(f"🔗 Verification Link:")
        print(f"   {verify_link}")
        print("="*70)
        print("📋 COPY THIS LINK TO VERIFY THE USER:")
        print(f"   {verify_link}")
        print("="*70 + "\n")
        logger.info(f"✅ Verification token printed to console for {username} ({to_email})")
        return True
    else:
        # Only try actual email sending if DEV_MODE is off
        return await _send_email_via_api(to_email, subject, body)

async def send_broadcast_email(to_email: str, subject: str, message: str):
    """Send broadcast email to a user"""
    body = f"""Hello StudyRPG User,

{message}

Best regards,
The StudyRPG Team"""
    
    # Print email content to console in development mode
    if DEV_MODE:
        print("\n" + "="*70)
        print("📢 BROADCAST EMAIL (DEV MODE)")
        print("="*70)
        print(f"📧 To: {to_email}")
        print(f"📝 Subject: {subject}")
        print(f"💬 Message:")
        print(body)
        print("="*70 + "\n")
        logger.info(f"✅ Broadcast email printed to console for {to_email}")
        return True
    else:
        return await _send_email_via_api(to_email, subject, body)

async def _send_email_via_api(to_email: str, subject: str, body: str):
    """Send email using SendGrid Web API (more reliable than SMTP)"""
    
    # Validate configuration
    if not SENDGRID_API_KEY or SENDGRID_API_KEY.startswith("your_"):
        logger.warning("SendGrid API key not configured, falling back to SMTP")
        return await _send_email_via_smtp_fallback(to_email, subject, body)
    
    if not EMAIL_FROM or "@" not in EMAIL_FROM:
        logger.error(f"Invalid sender email: {EMAIL_FROM}")
        return False
    
    if not to_email or "@" not in to_email:
        logger.error(f"Invalid recipient email: {to_email}")
        return False
    
    # Prepare the email payload
    payload = {
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": subject
            }
        ],
        "from": {"email": EMAIL_FROM},
        "content": [
            {
                "type": "text/plain",
                "value": body
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Sending email via SendGrid API to {to_email}...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers=headers
            ) as response:
                
                if response.status == 202:  # SendGrid returns 202 for success
                    logger.info("Email sent successfully via SendGrid API!")
                    return True
                elif response.status == 401:
                    error_text = await response.text()
                    logger.warning(f"SendGrid API credits/auth issue {response.status}: {error_text}")
                    logger.info("Falling back to Gmail SMTP...")
                    return await _send_email_via_smtp_fallback(to_email, subject, body)
                else:
                    error_text = await response.text()
                    logger.error(f"SendGrid API error {response.status}: {error_text}")
                    return False
                    
    except aiohttp.ClientError as e:
        logger.warning(f"SendGrid API network error: {e}, falling back to SMTP")
        return await _send_email_via_smtp_fallback(to_email, subject, body)
    except Exception as e:
        logger.warning(f"SendGrid API unexpected error: {e}, falling back to SMTP")
        return await _send_email_via_smtp_fallback(to_email, subject, body)

async def test_sendgrid_api():
    """Test SendGrid API connection"""
    try:
        logger.info("Testing SendGrid API connection...")
        
        # Validate configuration
        if not SENDGRID_API_KEY or SENDGRID_API_KEY.startswith("your_"):
            logger.error("SendGrid API key not configured")
            return False
        
        if not EMAIL_FROM or "@" not in EMAIL_FROM:
            logger.error("EMAIL_FROM not configured properly")
            return False
        
        # Test with a simple API call (get user account info)
        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(
                "https://api.sendgrid.com/v3/user/account",
                headers=headers
            ) as response:
                
                if response.status == 200:
                    logger.info("✅ SendGrid API connection successful!")
                    return True
                elif response.status == 401:
                    logger.error("❌ SendGrid API authentication failed - check your API key")
                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ SendGrid API error {response.status}: {error_text}")
                    return False
                    
    except aiohttp.ClientError as e:
        logger.error(f"❌ Network error testing SendGrid API: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error testing SendGrid API: {e}")
        return False

# ========================================================================
# FALLBACK SMTP IMPLEMENTATION (for development/backup)
# ========================================================================

import smtplib
from email.message import EmailMessage

async def _send_email_via_smtp_fallback(to_email: str, subject: str, body: str):
    """Fallback SMTP implementation with better Windows support"""
    
    # Try localhost first (for development with MailHog/similar)
    try:
        logger.info("Trying localhost SMTP (development mode)...")
        
        def _send_local():
            with smtplib.SMTP('localhost', 1025, timeout=10) as server:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = EMAIL_FROM
                msg["To"] = to_email
                msg.set_content(body)
                server.send_message(msg)
        
        await asyncio.to_thread(_send_local)
        logger.info("Email sent via localhost SMTP!")
        return True
        
    except Exception as e:
        logger.warning(f"Localhost SMTP failed: {e}")
    
    # Try Gmail SMTP (if user configures it)
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    
    if gmail_user and gmail_pass:
        try:
            logger.info("Trying Gmail SMTP...")
            
            def _send_gmail():
                with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
                    server.starttls()
                    server.login(gmail_user, gmail_pass)
                    msg = EmailMessage()
                    msg["Subject"] = subject
                    msg["From"] = gmail_user
                    msg["To"] = to_email
                    msg.set_content(body)
                    server.send_message(msg)
            
            await asyncio.to_thread(_send_gmail)
            logger.info("Email sent via Gmail SMTP!")
            return True
            
        except Exception as e:
            logger.warning(f"Gmail SMTP failed: {e}")
    
    return False

# ========================================================================
# UNIFIED EMAIL FUNCTION
# ========================================================================

async def send_email_unified(to_email: str, subject: str, body: str):
    """Try SendGrid API first, fallback to SMTP - OR print to console in DEV MODE"""
    
    # In development mode, just print to console
    if DEV_MODE:
        print("\n" + "="*70)
        print("📧 EMAIL (DEV MODE)")
        print("="*70)
        print(f"📧 To: {to_email}")
        print(f"📝 Subject: {subject}")
        print(f"💬 Body:")
        print(body)
        print("="*70 + "\n")
        logger.info(f"✅ Email printed to console for {to_email}")
        return True
    
    # Production mode - try actual email sending
    # First try SendGrid API
    if SENDGRID_API_KEY and not SENDGRID_API_KEY.startswith("your_"):
        success = await _send_email_via_api(to_email, subject, body)
        if success:
            return True
    
    # Fallback to SMTP
    logger.info("Falling back to SMTP...")
    return await _send_email_via_smtp_fallback(to_email, subject, body)

# ========================================================================
# DEBUGGING HELPER
# ========================================================================

async def debug_email_config():
    """Debug email configuration and test connectivity"""
    logger.info("=== EMAIL CONFIGURATION DEBUG ===")
    logger.info(f"DEV_MODE: {DEV_MODE}")
    logger.info(f"SENDGRID_API_KEY: {'*' * len(SENDGRID_API_KEY) if SENDGRID_API_KEY else 'None'} (length: {len(SENDGRID_API_KEY)})")
    logger.info(f"EMAIL_FROM: '{EMAIL_FROM}'")
    logger.info(f"FRONTEND_URL: '{FRONTEND_URL}'")
    
    if DEV_MODE:
        logger.info("✅ Running in development mode - emails will be printed to console")
        print("\n🔥 DEV MODE ACTIVE - TOKENS WILL BE PRINTED TO CONSOLE 🔥\n")
        return True
    
    # Test SendGrid API
    if SENDGRID_API_KEY and not SENDGRID_API_KEY.startswith("your_"):
        api_result = await test_sendgrid_api()
        logger.info(f"SendGrid API test: {'PASSED' if api_result else 'FAILED'}")
    else:
        logger.warning("SendGrid API key not configured")
        api_result = False
    
    logger.info("=== END DEBUG ===")
    return api_result

# ========================================================================
# CONVENIENCE FUNCTIONS FOR TESTING
# ========================================================================

def print_verification_token(username: str, email: str, token: str):
    """Standalone function to print verification token (for manual testing)"""
    verify_link = f"{FRONTEND_URL}/auth/verify-email?token={token}"
    print("\n" + "="*70)
    print("🔥 EMAIL VERIFICATION TOKEN 🔥")
    print("="*70)
    print(f"👤 User: {username}")
    print(f"📧 Email: {email}")
    print(f"🎫 Token: {token}")
    print(f"🔗 Verification Link:")
    print(f"   {verify_link}")
    print("="*70)
    print("📋 COPY THIS LINK TO VERIFY THE USER:")
    print(f"   {verify_link}")
    print("="*70 + "\n")

# ========================================================================
# FORCE DEV MODE FUNCTIONS (for guaranteed console output)
# ========================================================================

async def force_print_verification_email(to_email: str, username: str, token: str):
    """ALWAYS print verification email to console regardless of DEV_MODE"""
    verify_link = f"{FRONTEND_URL}/auth/verify-email?token={token}"
    print("\n" + "="*70)
    print("🔥 FORCED EMAIL VERIFICATION TOKEN 🔥")
    print("="*70)
    print(f"👤 User: {username}")
    print(f"📧 Email: {to_email}")
    print(f"🎫 Token: {token}")
    print(f"🔗 Verification Link:")
    print(f"   {verify_link}")
    print("="*70)
    print("📋 COPY THIS LINK TO VERIFY THE USER:")
    print(f"   {verify_link}")
    print("="*70 + "\n")
    logger.info(f"✅ FORCED verification token printed for {username} ({to_email})")
    return True

# Test function to verify everything works
async def test_dev_mode():
    """Test the dev mode functionality"""
    print("🧪 Testing DEV MODE functionality...")
    
    # Test verification email
    await send_verification_email("test@example.com", "testuser", "test_token_123")
    
    # Test broadcast email
    await send_broadcast_email("test@example.com", "Test Subject", "Test message content")
    
    print("✅ DEV MODE test complete!")

if __name__ == "__main__":
    # Quick test
    asyncio.run(test_dev_mode())