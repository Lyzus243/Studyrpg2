from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user  # Updated import
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_router = APIRouter(prefix="", tags=["users"])

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