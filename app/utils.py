import hashlib
from datetime import datetime

def hash_password(password: str) -> str:
    """
    Simple password hashing using SHA256.
    In production, use a stronger hashing algorithm (e.g., bcrypt).
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

def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default