from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app import models, schemas
from app.database import get_async_session
from app.auth_deps import get_current_user
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

skills_router = APIRouter(prefix="", tags=["skills"])

@skills_router.get("/available", response_model=List[schemas.SkillRead])
async def get_available_skills(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to list available skills")
            raise HTTPException(status_code=401, detail="Authentication required")
        result = await db.execute(
            select(models.Skill).order_by(models.Skill.cost.asc())
        )
        skills = result.scalars().all()
        logger.info(f"Fetched {len(skills)} available skills for user {current_user.id}")
        return skills
    except Exception as e:
        logger.error(f"Error in get_available_skills for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list available skills: {str(e)}")
    
    
@skills_router.post("/acquire/{skill_id}", response_model=schemas.UserSkillRead)
async def acquire_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to acquire skill")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get the skill
        result = await db.execute(
            select(models.Skill).where(models.Skill.id == skill_id)
        )
        skill = result.scalars().first()
        if not skill:
            logger.warning(f"Skill {skill_id} not found for acquisition by user {current_user.id}")
            raise HTTPException(status_code=404, detail="Skill not found")
            
        # Check if skill is already acquired
        result = await db.execute(
            select(models.UserSkill).where(
                models.UserSkill.user_id == current_user.id,
                models.UserSkill.skill_id == skill_id
            )
        )
        existing_user_skill = result.scalars().first()
        if existing_user_skill:
            logger.warning(f"Skill {skill_id} already acquired by user {current_user.id}")
            raise HTTPException(status_code=400, detail="Skill already acquired")
            
        # Get fresh user object
        user = await db.get(models.User, current_user.id)
        if not user:
            logger.error(f"User {current_user.id} not found in session")
            raise HTTPException(status_code=404, detail="User not found")
            
        if user.skill_points < skill.cost:
            logger.warning(f"Insufficient skill points for user {user.id} to acquire skill {skill_id}")
            raise HTTPException(status_code=400, detail="Insufficient skill points")
        
        # Create new UserSkill
        user_skill = models.UserSkill(
            user_id=user.id,
            skill_id=skill_id
        )
        db.add(user_skill)
        
        # Update user's skill points
        user.skill_points -= skill.cost
        
        # Flush to generate ID
        await db.flush()
        
        # Commit transaction
        await db.commit()
        
        # Re-query with relationship loaded
        result = await db.execute(
            select(models.UserSkill)
            .where(models.UserSkill.id == user_skill.id)
            .options(selectinload(models.UserSkill.skill))
        )
        user_skill = result.scalars().first()
        
        logger.info(f"User {user.id} acquired skill {skill_id}")
        return user_skill
    except Exception as e:
        logger.error(f"Error in acquire_skill for skill {skill_id} by user {current_user.id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to acquire skill: {str(e)}")

@skills_router.get("/acquired", response_model=List[schemas.UserSkillRead])
async def get_acquired_skills(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to get acquired skills")
            raise HTTPException(status_code=401, detail="Authentication required")
        result = await db.execute(
            select(models.UserSkill)
            .where(models.UserSkill.user_id == current_user.id)
            .options(selectinload(models.UserSkill.skill))
        )
        user_skills = result.scalars().all()
        logger.info(f"Fetched {len(user_skills)} acquired skills for user {current_user.id}")
        return user_skills
    except Exception as e:
        logger.error(f"Error in get_acquired_skills for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get acquired skills: {str(e)}")