import hashlib
from datetime import datetime
from jose import jwt
from app.config import conf
from datetime import timedelta
def hash_password(password: str) -> str:
    """
    Simple password hashing using SHA256.
    WARNING: SHA256 is NOT secure for production use. Use bcrypt or a similar strong hashing algorithm.
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def format_datetime(dt: datetime) -> str:
    """
    Format datetime for display.
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_current_time() -> datetime:
    return datetime.utcnow()

def create_access_token(data: dict, expires_delta: timedelta) -> str:
    """
    Create a JWT access token with the provided data and expiration time.
    """
    to_encode = data.copy()
    expire = get_current_time() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, conf.SECRET_KEY, algorithm=conf.ALGORITHM)
    return encoded_jwt

def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default