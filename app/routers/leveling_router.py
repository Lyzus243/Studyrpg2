from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from app.database import get_async_session
from app.auth_deps import get_current_user
from app import models
import logging

logger = logging.getLogger(__name__)

# Pydantic models
class XPAwardRequest(BaseModel):
    xp: int

class LevelProgressResponse(BaseModel):
    level: int
    current_xp: int
    xp_for_current_level: int
    xp_for_next_level: int
    progress_percentage: float
    total_xp: int
    debug_info: dict = {}

class XPAwardResponse(BaseModel):
    message: str
    awarded_xp: int
    new_total_xp: int
    old_level: int
    new_level: int
    level_up: bool
    debug_info: dict = {}

# Improved XP system with better progression
def calculate_xp_for_level(level: int) -> int:
    """Calculate total XP required to reach a specific level"""
    if level <= 1:
        return 0
    return (level - 1) * 100

def get_level_from_xp(total_xp: int) -> int:
    """Calculate level based on total XP"""
    if total_xp < 0:
        return 1
    # Calculate level based on cumulative XP
    level = 1
    while total_xp >= calculate_xp_for_level(level + 1):
        level += 1
    return level

async def get_user_xp(db: AsyncSession, user_id: int) -> int:
    """Get user's total XP"""
    try:
        query = select(models.User).where(models.User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user.xp
            
    except Exception as e:
        logger.error(f"Error getting user XP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get user XP: {str(e)}")

async def update_user_xp_and_level(db: AsyncSession, user_id: int, new_xp: int) -> bool:
    """Update user's XP and calculate new level"""
    try:
        new_level = get_level_from_xp(new_xp)
        update_query = update(models.User).where(
            models.User.id == user_id
        ).values(xp=new_xp, level=new_level)
        await db.execute(update_query)
        await db.commit()
        logger.info(f"Updated XP to {new_xp}, level to {new_level}")
        return True
    except Exception as e:
        logger.error(f"Error updating user XP and level: {str(e)}")
        await db.rollback()
        return False

async def calculate_level_and_progress(db: AsyncSession, user_id: int) -> LevelProgressResponse:
    """Calculate current level and progress"""
    try:
        total_xp = await get_user_xp(db, user_id)
        current_level = get_level_from_xp(total_xp)
        xp_for_current_level = calculate_xp_for_level(current_level)
        xp_for_next_level = calculate_xp_for_level(current_level + 1)
        
        current_level_xp = total_xp - xp_for_current_level
        xp_needed_for_next = xp_for_next_level - xp_for_current_level
        
        progress_percentage = (current_level_xp / xp_needed_for_next) * 100 if xp_needed_for_next > 0 else 0
        
        debug_info = {
            "total_xp": total_xp,
            "current_level": current_level,
            "xp_for_current_level": xp_for_current_level,
            "xp_for_next_level": xp_for_next_level,
            "current_level_xp": current_level_xp,
            "xp_needed_for_next": xp_needed_for_next,
        }
        
        return LevelProgressResponse(
            level=current_level,
            current_xp=current_level_xp,
            xp_for_current_level=xp_for_current_level,
            xp_for_next_level=xp_for_next_level,
            progress_percentage=round(progress_percentage, 2),
            total_xp=total_xp,
            debug_info=debug_info
        )
    except Exception as e:
        logger.error(f"Error calculating level progress: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate level progress: {str(e)}")

async def award_xp(db: AsyncSession, user_id: int, xp_amount: int) -> XPAwardResponse:
    """Award XP to user and update level"""
    try:
        if xp_amount <= 0:
            raise HTTPException(status_code=400, detail="XP amount must be positive")
        
        old_total_xp = await get_user_xp(db, user_id)
        old_level = get_level_from_xp(old_total_xp)
        new_total_xp = old_total_xp + xp_amount
        new_level = get_level_from_xp(new_total_xp)
        
        # Update XP and level
        db_updated = await update_user_xp_and_level(db, user_id, new_total_xp)
        
        level_up = new_level > old_level
        
        if level_up:
            logger.info(f"User {user_id} leveled up from {old_level} to {new_level}!")
        
        message = f"Awarded {xp_amount} XP"
        if level_up:
            message += f" and leveled up to {new_level}!"
        
        debug_info = {
            "old_total_xp": old_total_xp,
            "new_total_xp": new_total_xp,
            "old_level": old_level,
            "new_level": new_level,
            "database_updated": db_updated,
        }
        
        return XPAwardResponse(
            message=message,
            awarded_xp=xp_amount,
            new_total_xp=new_total_xp,
            old_level=old_level,
            new_level=new_level,
            level_up=level_up,
            debug_info=debug_info
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error awarding XP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to award XP: {str(e)}")

# Router setup
leveling_router = APIRouter(prefix="", tags=["leveling"])

@leveling_router.get("/progress", response_model=LevelProgressResponse)
async def get_level_progress(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get current user's level progress"""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        progress = await calculate_level_and_progress(db, current_user.id)
        logger.info(
            f"Level progress for user {current_user.id}: "
            f"Level {progress.level}, XP: {progress.current_xp}/{progress.xp_for_next_level}, "
            f"Total XP: {progress.total_xp}"
        )
        return progress
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Level progress error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get level progress")

@leveling_router.post("/award", response_model=XPAwardResponse)
async def award_user_xp(
    xp_data: XPAwardRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Award XP to the current user"""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        result = await award_xp(db, current_user.id, xp_data.xp)
        logger.info(
            f"Awarded {xp_data.xp} XP to user {current_user.id}. "
            f"New total: {result.new_total_xp}, Level: {result.new_level}"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"XP award error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to award XP")

@leveling_router.get("/debug/{user_id}")
async def debug_user_xp(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Debug endpoint to check XP system state"""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get user from database
        query = select(models.User).where(models.User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        calculated_level = get_level_from_xp(user.xp)
        
        # Check XP and level
        debug_data = {
            "user_id": user_id,
            "user_exists": True,
            "xp_value": user.xp,
            "level_value": user.level,
            "calculated_level": calculated_level,
            "level_match": user.level == calculated_level
        }
        
        return debug_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")