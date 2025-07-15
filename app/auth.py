from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from app.models import User, PasswordReset
from app.schemas import UserCreate, UserRead, UserUpdate
from app.crud import create_user, authenticate_user, get_user_by_email, generate_reset_token, validate_reset_token, update_user_password
from app.database import get_async_session
import bcrypt
import os
auth_router = APIRouter(prefix="/auth", tags=["auth"])

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")# Replace with a secure key in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_session)) -> UserRead:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    return UserRead.from_orm(user)

@auth_router.post("/signup", response_model=UserRead)
async def signup(user: UserCreate, db: AsyncSession = Depends(get_async_session)):
    """
    Register a new user.
    """
    db_user = await create_user(db, user)
    return UserRead.from_orm(db_user)

@auth_router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_async_session)):
    """
    Authenticate user and return JWT token.
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/reset-password")
async def reset_password(email: str, db: AsyncSession = Depends(get_async_session)):
    """
    Generate a password reset token for the user.
    """
    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    token = await generate_reset_token(db, user.id)
    # In production, send token via email (not implemented here)
    return {"message": "Password reset token generated", "token": token}

@auth_router.post("/verify-reset-token")
async def verify_reset_token(token: str, new_password: str, db: AsyncSession = Depends(get_async_session)):
    """
    Verify reset token and update password.
    """
    user_id = await validate_reset_token(db, token)
    await update_user_password(db, user_id, new_password)
    return {"message": "Password updated successfully"}