from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user  # Updated import
import logging
import os
import uuid
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_router = APIRouter(prefix="", tags=["users"])

# Custom profile pictures are saved under static/ so they're servable at
# /static/uploads/avatars/<file> without a separate StaticFiles mount.
AVATAR_DIR = os.path.join("static", "uploads", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)
ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB

@user_router.get("/me", response_model=schemas.UserRead)
async def get_current_user_profile(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get current user profile - COMPLETELY SESSION-SAFE VERSION"""
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to get user profile")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # SOLUTION: Re-query the user in the current session to avoid conflicts
        stmt = select(models.User).where(models.User.id == current_user.id)
        result = await db.execute(stmt)
        fresh_user = result.scalar_one_or_none()
        
        if not fresh_user:
            logger.error(f"User {current_user.id} not found in database")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update last_active on the fresh user object
        fresh_user.last_active = datetime.utcnow()
        await db.commit()
        await db.refresh(fresh_user)
        
        logger.info(f"Retrieved profile for user {fresh_user.id}")
        return schemas.UserRead.from_orm(fresh_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_user_profile: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to get user profile: {str(e)}")

@user_router.put("/me", response_model=schemas.UserRead)
async def update_user_profile(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update user profile - COMPLETELY SESSION-SAFE VERSION"""
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to update user profile")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # SOLUTION: Re-query the user in the current session
        stmt = select(models.User).where(models.User.id == current_user.id)
        result = await db.execute(stmt)
        fresh_user = result.scalar_one_or_none()
        
        if not fresh_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check for username conflicts
        if user_update.username and user_update.username != fresh_user.username:
            result = await db.execute(
                select(models.User).where(
                    models.User.username == user_update.username,
                    models.User.id != fresh_user.id
                )
            )
            if result.scalars().first():
                logger.warning(f"Username {user_update.username} already taken")
                raise HTTPException(status_code=400, detail="Username already exists")
            fresh_user.username = user_update.username
            
        # Check for email conflicts
        if user_update.email and user_update.email != fresh_user.email:
            result = await db.execute(
                select(models.User).where(
                    models.User.email == user_update.email,
                    models.User.id != fresh_user.id
                )
            )
            if result.scalars().first():
                logger.warning(f"Email {user_update.email} already taken")
                raise HTTPException(status_code=400, detail="Email already exists")
            fresh_user.email = user_update.email
            
        if user_update.avatar_url:
            fresh_user.avatar_url = user_update.avatar_url
            
        fresh_user.last_active = datetime.utcnow()
        await db.commit()
        await db.refresh(fresh_user)
        
        logger.info(f"Updated profile for user {fresh_user.id}")
        return schemas.UserRead.from_orm(fresh_user)
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error in update_user_profile: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")

@user_router.post("/me/avatar", response_model=schemas.UserRead)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Upload a custom profile picture. Replaces any previous custom avatar."""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_AVATAR_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Unsupported image type. Please upload a PNG, JPEG, WEBP, or GIF."
            )

        raw = await file.read()
        if len(raw) > MAX_AVATAR_BYTES:
            raise HTTPException(status_code=400, detail="Image must be smaller than 5 MB.")
        if len(raw) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        stmt = select(models.User).where(models.User.id == current_user.id)
        result = await db.execute(stmt)
        fresh_user = result.scalar_one_or_none()
        if not fresh_user:
            raise HTTPException(status_code=404, detail="User not found")

        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}[content_type]
        filename = f"user{fresh_user.id}_{uuid.uuid4().hex[:10]}.{ext}"
        file_path = os.path.join(AVATAR_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(raw)

        # Best-effort cleanup of the previous custom avatar file (ignore URLs/defaults)
        old_url = fresh_user.avatar_url or ""
        if old_url.startswith("/static/uploads/avatars/"):
            old_path = old_url.lstrip("/")
            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

        fresh_user.avatar_url = f"/static/uploads/avatars/{filename}"
        fresh_user.last_active = datetime.utcnow()
        await db.commit()
        await db.refresh(fresh_user)

        logger.info(f"Updated avatar for user {fresh_user.id}: {fresh_user.avatar_url}")
        return schemas.UserRead.from_orm(fresh_user)

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error in upload_avatar: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {str(e)}")

@user_router.get("/me/streak", response_model=int)
async def get_user_streak(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get user streak - COMPLETELY SESSION-SAFE VERSION"""
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to get user streak")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # SOLUTION: Re-query the user in the current session
        stmt = select(models.User.streak).where(models.User.id == current_user.id)
        result = await db.execute(stmt)
        streak = result.scalar_one_or_none()
        
        if streak is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"Retrieved streak {streak} for user {current_user.id}")
        return streak
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user_streak: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get streak: {str(e)}")