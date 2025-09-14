import asyncio
import logging
from email_utils import debug_email_config, send_email_unified, test_sendgrid_api

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Debug email configuration and test sending"""
    
    print("🔍 Starting email configuration debug...")
    
    # Debug configuration
    await debug_email_config()
    
    print("\n" + "="*50)
    print("🧪 Testing email sending...")
    
    # Test email sending
    test_email = "your-test-email@example.com"  # Replace with your email
    test_subject = "Test Email from StudyRPG"
    test_body = "This is a test email to verify the email system is working."
    
    try:
        result = await send_email_unified(test_email, test_subject, test_body)
        if result:
            print("✅ Email sent successfully!")
        else:
            print("❌ Email failed to send")
            
            # Additional troubleshooting
            print("\n🔧 Troubleshooting suggestions:")
            print("1. Check your .env file for correct SENDGRID_API_KEY")
            print("2. Verify EMAIL_FROM is authenticated in SendGrid")
            print("3. Ensure SendGrid API key has 'Mail Send' permissions")
            print("4. Check SendGrid account limits and usage")
            print("5. Try the SMTP fallback (see Gmail setup below)")
            
    except Exception as e:
        print(f"❌ Error during email test: {e}")
        logger.exception("Detailed error information:")

if __name__ == "__main__":
    asyncio.run(main())