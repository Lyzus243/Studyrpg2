from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from app import models, schemas
from app.database import get_async_session
from app.auth_deps import get_current_user
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flashcard_router = APIRouter(prefix="", tags=["flashcards"])
@flashcard_router.post("/", response_model=schemas.FlashcardRead)
async def create_flashcard(
    flashcard: schemas.FlashcardCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to create flashcard")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Removed context manager
        db_flashcard = models.Flashcard(
            question=flashcard.question,
            answer=flashcard.answer,
            user_id=current_user.id,
            created_at=datetime.utcnow()
        )
        db.add(db_flashcard)
        await db.commit()
        await db.refresh(db_flashcard)
        
        logger.info(f"User {current_user.username} created flashcard {db_flashcard.id}")
        return schemas.FlashcardRead.model_validate(db_flashcard)
    except SQLAlchemyError as e:
        logger.error(f"Database error creating flashcard for user {current_user.username}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create flashcard: Database error")
    except Exception as e:
        logger.error(f"Unexpected error creating flashcard for user {current_user.username}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create flashcard: {str(e)}")

@flashcard_router.post("/user", response_model=schemas.UserFlashcardRead)
async def assign_flashcard(
    user_flashcard: schemas.UserFlashcardCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to assign flashcard")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Removed context manager
        result = await db.execute(
            select(models.Flashcard).where(models.Flashcard.id == user_flashcard.flashcard_id)
        )
        flashcard = result.scalars().first()
        if not flashcard:
            logger.warning(f"Flashcard {user_flashcard.flashcard_id} not found for user {current_user.username}")
            raise HTTPException(status_code=404, detail="Flashcard not found")
        
        db_user_flashcard = models.UserFlashcard(
            user_id=current_user.id,
            flashcard_id=user_flashcard.flashcard_id,
            proficiency=user_flashcard.proficiency
        )
        db.add(db_user_flashcard)
        await db.commit()
        await db.refresh(db_user_flashcard)
        
        logger.info(f"User {current_user.username} assigned flashcard {user_flashcard.flashcard_id}")
        return schemas.UserFlashcardRead.model_validate(db_user_flashcard)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error assigning flashcard for user {current_user.username}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to assign flashcard: Database error")
    except Exception as e:
        logger.error(f"Unexpected error assigning flashcard for user {current_user.username}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign flashcard: {str(e)}")

@flashcard_router.put("/user/{user_flashcard_id}", response_model=schemas.UserFlashcardRead)
async def update_user_flashcard(
    user_flashcard_id: int,
    proficiency: schemas.UserFlashcardUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to update flashcard proficiency")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Removed context manager
        result = await db.execute(
            select(models.UserFlashcard).where(
                models.UserFlashcard.id == user_flashcard_id,
                models.UserFlashcard.user_id == current_user.username
            )
        )
        user_flashcard = result.scalars().first()
        if not user_flashcard:
            logger.warning(f"UserFlashcard {user_flashcard_id} not found for user {current_user.username}")
            raise HTTPException(status_code=404, detail="User flashcard not found")
        
        if proficiency.proficiency is not None:
            user_flashcard.proficiency = proficiency.proficiency
        
        db.add(user_flashcard)
        await db.commit()
        await db.refresh(user_flashcard)
        
        logger.info(f"User {current_user.username} updated proficiency for user_flashcard {user_flashcard_id}")
        return schemas.UserFlashcardRead.model_validate(user_flashcard)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error updating user_flashcard {user_flashcard_id} for user {current_user.username}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update flashcard proficiency: Database error")
    except Exception as e:
        logger.error(f"Unexpected error updating user_flashcard {user_flashcard_id} for user {current_user.username}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update flashcard proficiency: {str(e)}")