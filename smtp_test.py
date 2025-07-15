import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("MAIL_USERNAME", "apikey")  # must be 'apikey'
PASSWORD = os.getenv("MAIL_PASSWORD")         # actual API key
SMTP_SERVER = os.getenv("MAIL_SERVER", "smtp.sendgrid.net")
SMTP_PORT = int(os.getenv("MAIL_PORT", 587))

print("SMTP_SERVER:", SMTP_SERVER)
print("MAIL_USERNAME:", EMAIL)

if not SMTP_SERVER or not PASSWORD:
    print("❌ MAIL_SERVER or MAIL_PASSWORD not set.")
    exit(1)

try:
    print(f"🔌 Connecting to {SMTP_SERVER}:{SMTP_PORT} as {EMAIL}...")
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.ehlo()
    server.starttls()
    server.login(EMAIL, PASSWORD)
    print("✅ Logged in successfully — SMTP connection works!")
    server.quit()
except Exception as e:
    print("❌ SMTP test failed:", e)
