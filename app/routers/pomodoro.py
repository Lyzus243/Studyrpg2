from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user
from app.connection_manager import ConnectionManager
import logging
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pomodoro_router = APIRouter(prefix="", tags=["pomodoro"])
manager = ConnectionManager()

@pomodoro_router.post("/start", response_model=schemas.PomodoroSessionRead)
async def start_pomodoro_session(
    session: schemas.PomodoroSessionCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to start Pomodoro session")
            raise HTTPException(status_code=401, detail="Authentication required")
        if session.duration < 1 or session.duration > 120:
            logger.warning(f"Invalid duration {session.duration} by user {current_user.id}")
            raise HTTPException(status_code=400, detail="Duration must be between 1 and 120 minutes")
        
        # Create session directly
        db_session = models.PomodoroSession(
            user_id=current_user.id,
            duration=session.duration,
            start_time=datetime.utcnow(),
            is_completed=False
        )
        
        db.add(db_session)
        await db.commit()
        await db.refresh(db_session)
        
        await manager.broadcast_to_group(
            json.dumps({
                "type": "pomodoro_started",
                "session_id": db_session.id,
                "user_id": current_user.id,
                "duration": session.duration
            }),
            f"pomodoro_{current_user.id}"
        )
        logger.info(f"Started Pomodoro session {db_session.id} for user {current_user.id}")
        return schemas.PomodoroSessionRead.from_orm(db_session)
    except Exception as e:
        logger.error(f"Error in start_pomodoro_session for user {current_user.id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start Pomodoro session: {str(e)}")

@pomodoro_router.post("/{session_id}/complete", response_model=schemas.PomodoroSessionRead)
async def complete_pomodoro_session(
    session_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to complete Pomodoro session")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Reload the user in the current session
        user = await db.get(models.User, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await db.execute(
            select(models.PomodoroSession).where(
                models.PomodoroSession.id == session_id,
                models.PomodoroSession.user_id == user.id,
                models.PomodoroSession.is_completed == False
            )
        )
        db_session = result.scalars().first()
        if not db_session:
            logger.warning(f"Pomodoro session {session_id} not found or already completed for user {user.id}")
            raise HTTPException(status_code=404, detail="Session not found or already completed")
        
        db_session.is_completed = True
        db_session.end_time = datetime.utcnow()
        xp_reward = db_session.duration * 5
        
        # Update the reloaded user object
        user.xp += xp_reward
        db.add(user)
        
        db_session.xp_earned = xp_reward
        await db.commit()
        await db.refresh(db_session)
        
        await manager.broadcast_to_group(
            json.dumps({
                "type": "pomodoro_completed",
                "session_id": session_id,
                "user_id": user.id,
                "xp_earned": xp_reward
            }),
            f"pomodoro_{user.id}"
        )
        logger.info(f"Completed Pomodoro session {session_id} for user {user.id}, awarded {xp_reward} XP")
        return schemas.PomodoroSessionRead.from_orm(db_session)
    except Exception as e:
        logger.error(f"Error in complete_pomodoro_session for session {session_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to complete Pomodoro session: {str(e)}")







@pomodoro_router.get("/history", response_model=List[schemas.PomodoroSessionRead])
async def get_pomodoro_history(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to get Pomodoro history")
            raise HTTPException(status_code=401, detail="Authentication required")
        sessions = await crud.get_pomodoro_sessions(db, current_user.id, skip=0, limit=50)
        logger.info(f"Fetched {len(sessions)} Pomodoro sessions for user {current_user.id}")
        return [schemas.PomodoroSessionRead.from_orm(session) for session in sessions]
    except Exception as e:
        logger.error(f"Error in get_pomodoro_history for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Pomodoro history: {str(e)}")

@pomodoro_router.get("/stats", response_model=schemas.PomodoroStats)
async def get_pomodoro_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to get Pomodoro stats")
            raise HTTPException(status_code=401, detail="Authentication required")
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        stats = await crud.get_pomodoro_stats(db, current_user.id, start_date, end_date)
        logger.info(f"Fetched Pomodoro stats for user {current_user.id}")
        return schemas.PomodoroStats(**stats)
    except Exception as e:
        logger.error(f"Error in get_pomodoro_stats for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Pomodoro stats: {str(e)}")

@pomodoro_router.websocket("/{user_id}/ws")
async def websocket_pomodoro(
    user_id: int,
    websocket: WebSocket,
    token: str,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        user = await get_current_user(token=token, db=db)
        if not user or user.id != user_id:
            logger.warning(f"Invalid token or user mismatch for Pomodoro WebSocket, user_id: {user_id}")
            await websocket.close(code=1008, reason="Invalid token or user mismatch")
            return
        await manager.connect(websocket, f"pomodoro_{user_id}")
        try:
            while True:
                data = await websocket.receive_json()
                await manager.broadcast(
                    json.dumps({
                        "type": "pomodoro_update",
                        "user_id": user_id,
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    f"pomodoro_{user_id}",
                    sender=websocket
                )
                logger.debug(f"Broadcast Pomodoro update for user {user_id}")
        except WebSocketDisconnect:
            manager.disconnect(websocket, f"pomodoro_{user_id}")
            logger.info(f"WebSocket disconnected for Pomodoro user {user_id}")
        except Exception as e:
            logger.error(f"Error in websocket_pomodoro for user {user_id}: {str(e)}")
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close(code=1003)
    except Exception as e:
        logger.error(f"Error in websocket_pomodoro setup for user {user_id}: {str(e)}")
        await websocket.close(code=1008, reason="Authentication failed")