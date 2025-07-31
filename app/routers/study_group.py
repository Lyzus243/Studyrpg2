from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload  # Ensure this is imported
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user
from app.connection_manager import ConnectionManager
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

study_groups_router = APIRouter(prefix="", tags=["study_groups"])
manager = ConnectionManager()

@study_groups_router.post("/", response_model=schemas.StudyGroupRead)
async def create_study_group(
    group: schemas.StudyGroupCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to create study group")
            raise HTTPException(status_code=401, detail="Authentication required")
        if not group.name:
            logger.warning(f"Invalid group name by user {current_user.id}")
            raise HTTPException(status_code=400, detail="Group name is required")
        
        # Create group without transaction context
        db_group = await crud.create_study_group(db, group, current_user.id)
        await crud.add_user_to_group(db, db_group.id, current_user.id)
        await db.commit()
        
        # FIX: Properly reload with relationships using selectinload
        result = await db.execute(
            select(models.StudyGroup)
            .where(models.StudyGroup.id == db_group.id)
            .options(
                selectinload(models.StudyGroup.members),
                selectinload(models.StudyGroup.creator)
            )
        )
        db_group = result.scalars().first()
        
        logger.info(f"Created study group {db_group.id} by user {current_user.id}")
        return schemas.StudyGroupRead.model_validate(db_group)
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in create_study_group for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create study group: {str(e)}")
    
    

@study_groups_router.get("/", response_model=list[schemas.StudyGroupRead])
async def get_user_study_groups(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to list study groups")
            raise HTTPException(status_code=401, detail="Authentication required")
        groups = await crud.get_user_study_groups(db, current_user.id)
        logger.info(f"Fetched {len(groups)} study groups for user {current_user.id}")
        return [schemas.StudyGroupRead.model_validate(group) for group in groups]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user_study_groups for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list study groups: {str(e)}")

@study_groups_router.post("/{group_id}/join", response_model=schemas.StudyGroupRead)
async def join_study_group(
    group_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to join study group")
            raise HTTPException(status_code=401, detail="Authentication required")
        async with db.begin():
            group = await crud.get_study_group(db, group_id)
            if not group:
                logger.warning(f"Study group {group_id} not found for user {current_user.id}")
                raise HTTPException(status_code=404, detail="Study group not found")
            result = await db.execute(
                select(models.UserStudyGroup).where(
                    models.UserStudyGroup.group_id == group_id,
                    models.UserStudyGroup.user_id == current_user.id
                )
            )
            if result.scalars().first():
                logger.warning(f"User {current_user.id} already in study group {group_id}")
                raise HTTPException(status_code=400, detail="User already in group")
            await crud.add_user_to_group(db, group_id, current_user.id)
            await db.refresh(group)
        await manager.broadcast_to_group(
            json.dumps({
                "type": "user_joined_group",
                "group_id": group_id,
                "user_id": current_user.id,
                "timestamp": datetime.utcnow().isoformat()
            }),
            f"group_{group_id}"
        )
        logger.info(f"User {current_user.id} joined study group {group_id}")
        return schemas.StudyGroupRead.model_validate(group)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in join_study_group for group {group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to join study group: {str(e)}")

@study_groups_router.post("/{group_id}/leave", response_model=dict)
async def leave_study_group(
    group_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to leave study group")
            raise HTTPException(status_code=401, detail="Authentication required")
        async with db.begin():
            group = await crud.get_study_group(db, group_id)
            if not group:
                logger.warning(f"Study group {group_id} not found for user {current_user.id}")
                raise HTTPException(status_code=404, detail="Study group not found")
            success = await crud.remove_user_from_group(db, group_id, current_user.id)
            if not success:
                logger.warning(f"User {current_user.id} not in study group {group_id}")
                raise HTTPException(status_code=400, detail="User not in group")
        await manager.broadcast_to_group(
            json.dumps({
                "type": "user_left_group",
                "group_id": group_id,
                "user_id": current_user.id,
                "timestamp": datetime.utcnow().isoformat()
            }),
            f"group_{group_id}"
        )
        logger.info(f"User {current_user.id} left study group {group_id}")
        return {"message": "Left study group successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in leave_study_group for group {group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to leave study group: {str(e)}")

@study_groups_router.websocket("/{group_id}/ws")
async def websocket_study_group(
    group_id: int,
    websocket: WebSocket,
    token: str,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        user = await get_current_user(token=token, db=db)
        if not user:
            logger.warning(f"Invalid token for study group WebSocket, group_id: {group_id}")
            await websocket.close(code=1008, reason="Invalid token")
            return
        async with db.begin():
            group = await crud.get_study_group(db, group_id)
            if not group:
                logger.warning(f"Study group {group_id} not found for WebSocket")
                await websocket.close(code=1008, reason="Study group not found")
                return
            result = await db.execute(
                select(models.UserStudyGroup).where(
                    models.UserStudyGroup.group_id == group_id,
                    models.UserStudyGroup.user_id == user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {user.id} not in study group {group_id} for WebSocket")
                await websocket.close(code=1008, reason="Not a group member")
                return
        await manager.connect(websocket, f"group_{group_id}")
        try:
            while True:
                data = await websocket.receive_json()
                await manager.broadcast_to_group(
                    json.dumps({
                        "type": "group_update",
                        "group_id": group_id,
                        "user_id": user.id,
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    f"group_{group_id}"
                )
                logger.debug(f"Broadcast group update for group {group_id}")
        except WebSocketDisconnect:
            manager.disconnect(websocket, f"group_{group_id}")
            logger.info(f"WebSocket disconnected for study group {group_id}")
        except Exception as e:
            logger.error(f"Error in websocket_study_group for group {group_id}: {str(e)}")
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close(code=1003)
    except Exception as e:
        logger.error(f"Error in websocket_study_group setup for group {group_id}: {str(e)}")
        await websocket.close(code=1008, reason="Authentication failed")