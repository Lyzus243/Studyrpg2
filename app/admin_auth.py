# app/admin_auth.py
from fastapi import HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from jose import JWTError, jwt
import os
import logging
from app.database import get_async_session
from app.models import User

logger = logging.getLogger(__name__)

# Admin credentials from .env
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Lyzus308")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234567")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "pumlezerti@necub.com")

# JWT settings (should match your auth settings)
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGO", "HS256")

# 🔍 DEBUG: Log loaded values on startup
logger.info(f"🔍 Admin Auth Module Loaded:")
logger.info(f"   ADMIN_USERNAME: {ADMIN_USERNAME}")
logger.info(f"   ADMIN_PASSWORD: {'SET' if ADMIN_PASSWORD else 'NOT SET'}")
logger.info(f"   SECRET_KEY: {'SET' if SECRET_KEY else 'NOT SET'}")
logger.info(f"   ALGORITHM: {ALGORITHM}")

async def verify_admin_token(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Shared function to verify admin JWT token from either Authorization header or cookie.
    Works for both API requests and browser-based admin UI routes.
    """
    logger.info("🔍 verify_admin_token called")
    
    auth_header = request.headers.get("Authorization")
    token = None

    # 1. Try to extract from "Authorization: Bearer <token>"
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        logger.info("🔍 Token found in Authorization header")
    else:
        # 2. Fallback to cookie (for browser-based admin UI)
        token = request.cookies.get("admin_token")
        if token:
            logger.info("🔍 Token found in cookie")
        else:
            logger.warning("❌ No token in header or cookie")

    if not token:
        logger.info("No admin token found in header or cookies")
        raise HTTPException(status_code=401, detail="Not authenticated")

    # 3. Decode and validate the JWT
    try:
        logger.info(f"🔍 Attempting to decode token with SECRET_KEY: {'SET' if SECRET_KEY else 'NOT SET'}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        logger.info(f"🔍 Token decoded successfully")
        logger.info(f"🔍 Username from token: {username}")
        logger.info(f"🔍 Expected admin username: {ADMIN_USERNAME}")

        if not username:
            logger.warning("Invalid token payload (no username)")
            raise HTTPException(status_code=401, detail="Invalid token payload")

        # 4. Lookup the user in DB
        logger.info(f"🔍 Looking up user in database: {username}")
        result = await db.execute(
            select(User).where(func.lower(User.username) == str(username).lower())
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"❌ No user found in database for: {username}")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        logger.info(f"🔍 User found in database: {user.username}")

        # 5. Ensure user is the configured admin
        logger.info(f"🔍 Comparing: user.username.lower()={user.username.lower()} vs ADMIN_USERNAME.lower()={ADMIN_USERNAME.lower()}")
        
        if user.username.lower() != ADMIN_USERNAME.lower():
            logger.warning(f"❌ User {user.username} is not admin (expected {ADMIN_USERNAME})")
            raise HTTPException(status_code=403, detail="Admin access only")

        logger.info(f"✅ Admin verified by username match: {user.username}")
        return user

    except JWTError as e:
        logger.warning(f"❌ JWT decode failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error verifying admin token: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def require_admin(user: User):
    """Check if user is admin based on .env credentials"""
    if not user:
        logger.warning("No user provided to admin check")
        raise HTTPException(status_code=403, detail="Admin access only")
    
    # Check if username matches admin username from .env (case-insensitive)
    if user.username.lower() != ADMIN_USERNAME.lower():
        logger.warning(f"Admin access denied for user: {user.username} (expected: {ADMIN_USERNAME})")
        raise HTTPException(status_code=403, detail="Admin access only")
    
    logger.info(f"✅ Admin access granted for user: {user.username}")
    return True