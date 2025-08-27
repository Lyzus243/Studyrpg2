from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request, Depends
from jose import jwt, JWTError
from app.database import get_async_session
from app import models

# -------------------------------------------------------------------------
# Config & setup
# -------------------------------------------------------------------------
from dotenv import load_dotenv
# import os

load_dotenv()
logger = logging.getLogger("app.routers.auth")
logger.setLevel(logging.INFO)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGO", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MIN", "30"))

# Create a settings object that tests can import
class Settings:
    SECRET_KEY = SECRET_KEY
    ALGORITHM = ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES = ACCESS_TOKEN_EXPIRE_MINUTES

# Make settings available at module level for test imports
settings = Settings()

# Password hashing with secure bcrypt rounds
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Secure for production
)

# Security schemes for different authentication methods
security = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Template configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "static" / "templates")

# Router setup
auth_router = APIRouter(prefix="", tags=["auth"])

# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    confirm_password: str

class UserRead(BaseModel):
    id: int
    username: str
    email: str
    is_verified: bool
    xp: int
    skill_points: int
    streak: int
    avatar_url: Optional[str] = None
    level: int
    currency: int

# -------------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------------





def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    
    # Ensure sub is always a string (standard JWT practice)
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def authenticate_user(username: str, password: str) -> str:
    """Helper function for testing - returns username if valid."""
    return username

# -------------------------------------------------------------------------
# Authentication Dependencies
# -------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session),
) -> models.User:
    """
    Strict authentication that accepts token from Authorization header OR
    from the "access_token" cookie. Raises if missing/invalid.
    """
    token: Optional[str] = None

    # 1) Authorization header via HTTPBearer
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        token = credentials.credentials

    # 2) Fallback to cookie for browser-based navigation
    if not token:
        token = request.cookies.get("access_token")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
        # Optional: check expiry if present (jose raises if expired when "exp" is set)
    except JWTError:
        raise credentials_exception

    try:
        result = await db.execute(select(models.User).where(models.User.username == username))
        user = result.scalar_one_or_none()
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

    if not user:
        raise credentials_exception

    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> Optional[models.User]:
    """
    Optional authentication that checks both Authorization header and cookies.
    Returns user or None without raising exceptions.
    Used for HTML pages that should gracefully handle unauthenticated users.
    """
    token = None
    
    logger.info("get_current_user_optional called")
    
    # First, try Authorization header (for API requests)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        logger.info(f"Found token in Authorization header: {token[:20]}...")
    
    # If no header token, try cookie (for HTML page requests)
    if not token:
        token = request.cookies.get("access_token")
        if token:
            logger.info(f"Found token in cookie: {token[:20]}...")
        else:
            logger.info("No token found in Authorization header or cookies")
    
    if not token:
        logger.info("No authentication token available")
        return None

    try:
        # Reuse the strict authentication logic from auth.py
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(creds, db)
        logger.info(f"Optional auth successful for user: {user.username}")
        return user
    except HTTPException as e:
        # Invalid or expired token => treat as guest
        logger.info(f"Optional auth failed with HTTPException: {e.detail}")
        return None
    except Exception as e:
        logger.debug(f"Optional auth error: {e}")
        return None
# -------------------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------------------

async def get_current_user_from_cookie(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(models.User).where(models.User.id == int(user_id)))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@auth_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Register a new user account."""
    try:
        # Password validation
        if len(user.password) < 12:
            raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
        
        # Password complexity checks
        if not any(c.isupper() for c in user.password):
            raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter")
        if not any(c.islower() for c in user.password):
            raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in user.password):
            raise HTTPException(status_code=400, detail="Password must contain at least one number")

        if user.password != user.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")

        # Input validation and sanitization
        username = user.username.strip()
        email = user.email.strip().lower()
        
        if not username or len(username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="Invalid email format")

        # Check if user already exists
        exists_stmt = select(models.User).where(
            or_(models.User.email == email, models.User.username == username)
        )
        result = await db.execute(exists_stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            if existing.username == username:
                raise HTTPException(status_code=400, detail="Username already exists")
            raise HTTPException(status_code=400, detail="Email already exists")

        # Create new user
        hashed = get_password_hash(user.password)
        current_time = datetime.now(timezone.utc)
        
        db_user = models.User(
            username=username,
            email=email,
            hashed_password=hashed,
            is_verified=False,
            xp=0,
            skill_points=100,
            streak=0,
            level=1,
            currency=100,
            last_active=current_time,
            avatar_url=None,
        )

        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        # Generate email verification token
        token = secrets.token_urlsafe(32)
        db_user.email_verification_token = token
        db_user.verification_sent_at = current_time
        await db.commit()
        await db.refresh(db_user)

        # Send verification email
        try:
            from app.email_utils import send_verification_email
            await send_verification_email(db_user.email, db_user.username, token)
        except Exception:
            logger.exception("Failed to send verification email")

        logger.info("User registered: %s", db_user.id)

        return UserRead(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            is_verified=db_user.is_verified,
            xp=db_user.xp,
            skill_points=db_user.skill_points,
            streak=db_user.streak,
            avatar_url=db_user.avatar_url,
            level=db_user.level,
            currency=db_user.currency,
        )

    except HTTPException:
        raise
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("Registration DB error")
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception:
        await db.rollback()
        logger.exception("Registration error")
        raise HTTPException(status_code=500, detail="Internal server error")

@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Login endpoint that returns JWT token and sets authentication cookie.
    Now creates tokens with username instead of user ID.
    Supports both API clients (via JSON response) and web browsers (via cookie).
    """
    username = (form_data.username or "").strip()
    password = form_data.password or ""
    
    # Log the login attempt
    logger.info(f"Login attempt for username: {username}")
    
    try:
        # Find user by username
        result = await db.execute(
            select(models.User).where(models.User.username == username)
        )
        user = result.scalar_one_or_none()

    except SQLAlchemyError as e:
        logger.exception(f"DB error during login for username: {username}")
        raise HTTPException(status_code=500, detail="Internal server error")

    # Check if user exists
    if user is None:
        logger.warning(f"Login failed: User '{username}' not found in database")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check password
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Login failed: Invalid password for user '{username}' (ID: {user.id})")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check email verification
    if not user.is_verified:
        logger.warning(f"Login failed: User '{username}' (ID: {user.id}) is not email verified. is_verified={user.is_verified}")
        raise HTTPException(status_code=401, detail="Email not verified. Please check your email.")

    logger.info(f"Login successful for user '{username}' (ID: {user.id})")

    # Update last active time
    user.last_active = datetime.now(timezone.utc)
    await db.commit()

    # Create access token with username instead of user ID
    access_token = create_access_token(data={"sub": user.username})
    
    # Set HTTP-only cookie for HTML page authentication
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access (security)
        secure=False,   # Set to True in production with HTTPS
        samesite="lax", # CSRF protection
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Same as JWT expiry
        path="/"
    )
    
    logger.info("Token created and cookie set for user: %s", user.username)
    return Token(access_token=access_token)


@auth_router.post("/logout")
async def logout(response: Response):
    """Logout by clearing the authentication cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Successfully logged out"}

@auth_router.get("/verify-email")
async def verify_email(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """Verify user email using verification token."""
    try:
        # Token validation
        if not token or len(token) < 10:
            raise HTTPException(status_code=400, detail="Invalid token format")
            
        # Find user with verification token
        stmt = select(models.User).where(models.User.email_verification_token == token)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        current_time = datetime.now(timezone.utc)
        
        # Check token expiry (48 hours)
        if user.verification_sent_at:
            verification_sent_at = user.verification_sent_at
            if verification_sent_at.tzinfo is None:
                verification_sent_at = verification_sent_at.replace(tzinfo=timezone.utc)
            
            if current_time - verification_sent_at > timedelta(hours=48):
                # Clean up expired token
                user.email_verification_token = None
                user.verification_sent_at = None
                await db.commit()
                raise HTTPException(status_code=400, detail="Verification token has expired. Please request a new one.")

        # Mark user as verified
        user.is_verified = True
        user.email_verification_token = None
        user.verification_sent_at = None
        await db.commit()

        message = "Your email has been verified successfully. You can now login."
        return templates.TemplateResponse(
            request=request,
            name="email_verified.html",
            context={"message": message, "user": user}
        )

    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Email verification DB error")
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception:
        logger.exception("Email verification error")
        raise HTTPException(status_code=500, detail="Verification failed")

@auth_router.get("/me", response_model=UserRead)
async def read_users_me(
    current_user: models.User = Depends(get_current_user),
):
    """Get current user information."""
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_verified=current_user.is_verified,
        xp=current_user.xp,
        skill_points=current_user.skill_points,
        streak=current_user.streak,
        avatar_url=current_user.avatar_url,
        level=current_user.level,
        currency=current_user.currency,
    )

@auth_router.get("/verify")
async def verify_token(
    current_user: models.User = Depends(get_current_user),
):
    """
    Verify if the current token is valid and return user info.
    Returns JSON with valid=False if token is invalid or expired.
    """
    return {
        "valid": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_verified": current_user.is_verified
        }
    }


@auth_router.post("/refresh")
async def refresh_token(
    response: Response,
    current_user: models.User = Depends(get_current_user),
):
    """
    Refresh the access token for the current user.
    Now creates new token with username instead of user ID.
    If token is invalid/expired, returns 401 JSON response.
    """
    # Update last active time
    current_user.last_active = datetime.now(timezone.utc)

    # Create new token with username instead of user ID
    access_token = create_access_token(data={"sub": current_user.username})

    # Update cookie with new token
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # True in production
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )

    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/resend-verification")
async def resend_verification_email(
    username: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Resend verification email for unverified users."""
    try:
        result = await db.execute(
            select(models.User).where(models.User.username == username.strip())
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal if user exists or not (security)
            return {"message": "If the username exists and is unverified, a new verification email has been sent."}
        
        if user.is_verified:
            return {"message": "Account is already verified."}
        
        # Generate new verification token
        token = secrets.token_urlsafe(32)
        user.email_verification_token = token
        user.verification_sent_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Send verification email
        try:
            from app.email_utils import send_verification_email
            await send_verification_email(user.email, user.username, token)
        except Exception:
            logger.exception("Failed to resend verification email")
        
        return {"message": "If the username exists and is unverified, a new verification email has been sent."}
        
    except SQLAlchemyError:
        logger.exception("DB error during resend verification")
        raise HTTPException(status_code=500, detail="Internal server error")