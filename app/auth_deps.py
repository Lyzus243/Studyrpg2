from sqlalchemy import select
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.init_db import get_async_session
import os
from dotenv import load_dotenv
import os
load_dotenv()

# Use environment variables for security
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Prefer header token if present, else cookie
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Add token expiration check
        expire = payload.get("exp")
        if expire is not None:
            current_time = datetime.utcnow()
            expire_time = datetime.utcfromtimestamp(expire)
            if current_time > expire_time:
                raise credentials_exception

    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    await db.refresh(user)
    return user



async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> Optional[User]:
    try:
        user = await get_current_user(request, None, db)  # credentials None triggers cookie/header lookup
        return user
    except HTTPException:
        return None
