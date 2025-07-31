from sqlalchemy import select
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.init_db import get_async_session
import os

# Use environment variables for security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secure-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
) -> User:
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
            
        # Add token expiration check
        expire = payload.get("exp")
        if expire is None:
            raise credentials_exception
            
        current_time = datetime.utcnow()
        expire_time = datetime.utcfromtimestamp(expire)
        
        if current_time > expire_time:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    # FIXED: Use a new query instead of reusing the same object
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    # FIXED: Refresh the object to ensure it's bound to the current session
    await db.refresh(user)
    return user

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
) -> Optional[User]:
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None