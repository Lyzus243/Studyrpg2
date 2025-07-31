from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from app.database import get_async_session
from app import models
import logging
import os

logger = logging.getLogger(__name__)

# FIX: Removed prefix from router since it's already added in main.py
auth_router = APIRouter(tags=["auth"])
security = HTTPBearer()

# Password hashing with reduced rounds for Windows compatibility
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto",
    bcrypt__rounds=4  # Lower rounds for faster hashing in development
)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secure-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Models
class Token(BaseModel):
    access_token: str
    token_type: str

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str
    confirm_password: str

class UserRead(UserBase):
    id: int
    is_verified: bool
    xp: int
    skill_points: int
    streak: int
    avatar_url: Optional[str] = None  # Added default value
    level: int
    currency: int

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        expire = payload.get("exp")
        if expire is None or datetime.utcnow() > datetime.fromtimestamp(expire):
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWT validation failed: {str(e)}")
        raise credentials_exception
    
    try:
        result = await db.execute(select(models.User).where(models.User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        return user
    except Exception as e:
        logger.error(f"Database error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
        )

@auth_router.post("/register", response_model=UserRead)
async def register_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        # Validate password
        if len(user.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters"
            )
        
        if user.password != user.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )

        # Check for existing user
        result = await db.execute(
            select(models.User).where(
                or_(
                    models.User.username == user.username,
                    models.User.email == user.email
                )
            )
        )
        existing_user = result.scalars().first()
        
        if existing_user:
            if existing_user.username == user.username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
                )

        # Create new user
        db_user = models.User(
            username=user.username,
            email=user.email,
            hashed_password=get_password_hash(user.password),
            is_verified=True,
            last_active=datetime.utcnow(),
            xp=0,
            skill_points=100,
            streak=0,
            level=1,
            currency=100,
            avatar_url=None  # Explicitly set to None
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        
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
            currency=db_user.currency
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"  # More detailed error
        )

@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session)
):
    try:
        result = await db.execute(
            select(models.User).where(models.User.username == form_data.username)
        )
        user = result.scalars().first()
        
        if not user or not verify_password(form_data.password, user.hashed_password):
            logger.warning(f"Failed login attempt for {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token({"sub": user.username})
        user.last_active = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)