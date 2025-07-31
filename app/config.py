from fastapi_mail import ConnectionConfig
import os
from typing import Optional
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class FastMailConfig(ConnectionConfig):
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "your_username")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "your_password")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "olanirano961@gmail.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", 587))
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_FROM_NAME: Optional[str] = os.getenv("MAIL_FROM_NAME", "StudyRPG")
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

class AppConfig:
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")

conf = FastMailConfig()
app_conf = AppConfig()

# Debug log to verify .env loading (comment out after verification)
logger.info(f"MAIL_USERNAME: {conf.MAIL_USERNAME}")