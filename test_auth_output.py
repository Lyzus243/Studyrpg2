import asyncio
import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_gmail_smtp():
    """Test Gmail SMTP as fallback"""
    
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    
    print("=== Gmail SMTP Test ===")
    print(f"Gmail User: {gmail_user}")
    print(f"Gmail App Password: {'✓ Found' if gmail_pass else '✗ Missing'}")
    
    if not gmail_user or not gmail_pass:
        print("❌ Gmail credentials not configured!")
        return False
    
    # Test sending email via Gmail
    try:
        print(f"\n📧 Sending test email via Gmail to {gmail_user}...")
        
        def _send_gmail():
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
                server.starttls()
                server.login(gmail_user, gmail_pass)
                
                msg = EmailMessage()
                msg["Subject"] = "StudyRPG Gmail Test - SUCCESS!"
                msg["From"] = gmail_user
                msg["To"] = gmail_user
                msg.set_content("""🎉 Great news! Your Gmail fallback is working!

This email was sent using Gmail SMTP as a backup to SendGrid.

✅ Gmail SMTP is connected
✅ Your app password is working
✅ Emails can be sent via Gmail

Your StudyRPG app can now send verification emails using Gmail when SendGrid credits are exhausted.

- StudyRPG Team""")
                
                server.send_message(msg)
        
        await asyncio.to_thread(_send_gmail)
        print("✅ Gmail test email sent successfully!")
        print(f"📬 Check your Gmail inbox at {gmail_user}")
        return True
        
    except Exception as e:
        print(f"❌ Gmail SMTP failed: {e}")
        return False

async def main():
    print("StudyRPG Gmail Fallback Test\n")
    
    gmail_working = await test_gmail_smtp()
    
    print("\n" + "="*50)
    if gmail_working:
        print("🎉 Gmail fallback is working!")
        print("Your app can send emails via Gmail when SendGrid is out of credits.")
    else:
        print("❌ Gmail fallback needs configuration.")

if __name__ == "__main__":
    asyncio.run(main())