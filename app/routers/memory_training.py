from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user
from app.routers.leveling_router import award_xp
import logging
import random
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Changed prefix to match test routes
# ... existing imports ...

memory_router = APIRouter(prefix="", tags=["memory_training"])

@memory_router.post("/start", response_model=schemas.MemorySessionRead)
async def start_memory_training_session(
    session: schemas.MemorySessionCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # ... validation code ...

        sequence = [random.randint(1, 9) for _ in range(session.sequence_length)]
        db_session = models.MemorySession(
            user_id=current_user.id,
            sequence_length=session.sequence_length,
            sequence=json.dumps(sequence),
            start_time=datetime.utcnow(),
            duration=0,
            score=0,
            is_completed=False
        )
        
        # FIX: Remove transaction context manager
        db.add(db_session)
        await db.commit()
        await db.refresh(db_session)  # Now safe outside of context manager
            
        logger.info(f"Started memory training session {db_session.id} for user {current_user.id}")
        return schemas.MemorySessionRead.from_orm(db_session)
        
    except Exception as e:
        # ... error handling ...
        return e

@memory_router.post("/{session_id}/submit", response_model=schemas.MemorySessionRead)
async def submit_memory_training_session(
    session_id: int,
    submission: schemas.MemorySessionSubmission,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # ... validation code ...

        # FIX: Remove transaction context manager
        result = await db.execute(
            select(models.MemorySession).where(
                models.MemorySession.id == session_id,
                models.MemorySession.user_id == current_user.id,
                models.MemorySession.is_completed == False
            )
        )
        db_session = result.scalars().first()
        
        if not db_session:
            # ... error handling ...
            
            correct_sequence = json.loads(db_session.sequence)
            db_session.is_completed = True
            db_session.is_correct = correct_sequence == submission.user_sequence
            db_session.end_time = datetime.utcnow()
            db_session.duration = int((db_session.end_time - db_session.start_time).total_seconds())
            db_session.score = db_session.sequence_length if db_session.is_correct else 0
        
        if db_session.is_correct:
            xp_reward = db_session.sequence_length * 10
            await award_xp(db, current_user.id, xp_reward)
            db_session.xp_earned = xp_reward
            
        await db.commit()  # Single commit at the end
        await db.refresh(db_session)
            
        logger.info(f"Submitted session {session_id} for user {current_user.id}")
        return schemas.MemorySessionRead.from_orm(db_session)
        
    except Exception as e:
        # ... error handling ...

# ... get_memory_training_history remains unchanged ...
        logger.error(f"Error fetching history for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")