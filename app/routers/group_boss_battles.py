from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user
from app.connection_manager import ConnectionManager
from app.routers.leveling_router import award_xp
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

group_boss_battles_router = APIRouter(prefix="", tags=["group_boss_battles"])
manager = ConnectionManager()

@group_boss_battles_router.post("/", response_model=schemas.GroupBossBattleRead)
async def create_group_boss_battle(
    battle: schemas.GroupBossBattleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to create group boss battle")
            raise HTTPException(status_code=401, detail="Authentication required")
        async with db.begin():
            result = await db.execute(
                select(models.StudyGroup).where(models.StudyGroup.id == battle.group_id)
            )
            group = result.scalars().first()
            if not group:
                logger.warning(f"Group {battle.group_id} not found for user {current_user.id}")
                raise HTTPException(status_code=404, detail="Study group not found")
            result = await db.execute(
                select(models.UserStudyGroup).where(
                    models.UserStudyGroup.group_id == battle.group_id,
                    models.UserStudyGroup.user_id == current_user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {current_user.id} not authorized for group {battle.group_id}")
                raise HTTPException(status_code=403, detail="Not a group member")
            if battle.difficulty < 1 or battle.difficulty > 10:
                logger.warning(f"Invalid difficulty {battle.difficulty} for group boss battle by user {current_user.id}")
                raise HTTPException(status_code=400, detail="Difficulty must be between 1 and 10")
            db_battle = await crud.create_group_boss_battle(db, battle, battle.group_id)
        await manager.broadcast_to_group(
            json.dumps({
                "type": "battle_created",
                "battle_id": db_battle.id,
                "group_id": battle.group_id,
                "timestamp": datetime.utcnow().isoformat()
            }),
            f"group_{battle.group_id}"
        )
        logger.info(f"Created group boss battle {db_battle.id} for group {battle.group_id}")
        return schemas.GroupBossBattleRead.from_orm(db_battle)
    except Exception as e:
        logger.error(f"Error in create_group_boss_battle for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group boss battle: {str(e)}")

@group_boss_battles_router.get("/group/{group_id}", response_model=List[schemas.GroupBossBattleRead])
async def get_group_boss_battles(
    group_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to list group boss battles")
            raise HTTPException(status_code=401, detail="Authentication required")
        async with db.begin():
            result = await db.execute(
                select(models.StudyGroup).where(models.StudyGroup.id == group_id)
            )
            group = result.scalars().first()
            if not group:
                logger.warning(f"Group {group_id} not found for user {current_user.id}")
                raise HTTPException(status_code=404, detail="Study group not found")
            result = await db.execute(
                select(models.UserStudyGroup).where(
                    models.UserStudyGroup.group_id == group_id,
                    models.UserStudyGroup.user_id == current_user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {current_user.id} not authorized for group {group_id}")
                raise HTTPException(status_code=403, detail="Not a group member")
            result = await db.execute(
                select(models.GroupBossBattle).where(
                    models.GroupBossBattle.group_id == group_id
                ).order_by(models.GroupBossBattle.created_at.desc())
            )
            battles = result.scalars().all()
        logger.info(f"Fetched {len(battles)} group boss battles for group {group_id}")
        return [schemas.GroupBossBattleRead.from_orm(battle) for battle in battles]
    except Exception as e:
        logger.error(f"Error in get_group_boss_battles for group {group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list group boss battles: {str(e)}")

@group_boss_battles_router.post("/{battle_id}/join", response_model=dict)
async def join_group_boss_battle(
    battle_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to join group boss battle")
            raise HTTPException(status_code=401, detail="Authentication required")
        async with db.begin():
            result = await db.execute(
                select(models.GroupBossBattle).where(models.GroupBossBattle.id == battle_id)
            )
            battle = result.scalars().first()
            if not battle:
                logger.warning(f"Group boss battle {battle_id} not found")
                raise HTTPException(status_code=404, detail="Battle not found")
            result = await db.execute(
                select(models.UserStudyGroup).where(
                    models.UserStudyGroup.group_id == battle.group_id,
                    models.UserStudyGroup.user_id == current_user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {current_user.id} not authorized for group {battle.group_id}")
                raise HTTPException(status_code=403, detail="Not a group member")
            result = await db.execute(
                select(models.UserGroupBossBattle).where(
                    models.UserGroupBossBattle.group_boss_battle_id == battle_id,
                    models.UserGroupBossBattle.user_id == current_user.id
                )
            )
            if result.scalars().first():
                logger.warning(f"User {current_user.id} already joined battle {battle_id}")
                raise HTTPException(status_code=400, detail="Already joined battle")
            await crud.join_group_boss_battle(db, battle_id, current_user.id)
        await manager.broadcast_to_group(
            json.dumps({
                "type": "user_joined_battle",
                "battle_id": battle_id,
                "user_id": current_user.id,
                "timestamp": datetime.utcnow().isoformat()
            }),
            f"group_{battle.group_id}"
        )
        logger.info(f"User {current_user.id} joined group boss battle {battle_id}")
        return {"message": "Joined battle successfully"}
    except Exception as e:
        logger.error(f"Error in join_group_boss_battle for battle {battle_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to join group boss battle: {str(e)}")

@group_boss_battles_router.post("/{battle_id}/attack", response_model=schemas.GroupBossBattleRead)
async def attack_group_boss(
    battle_id: int,
    attack: schemas.BossAttack,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to attack group boss")
            raise HTTPException(status_code=401, detail="Authentication required")
        async with db.begin():
            result = await db.execute(
                select(models.GroupBossBattle).where(
                    models.GroupBossBattle.id == battle_id,
                    models.GroupBossBattle.is_completed == False
                )
            )
            battle = result.scalars().first()
            if not battle:
                logger.warning(f"Group boss battle {battle_id} not found or already completed")
                raise HTTPException(status_code=404, detail="Battle not found or already completed")
            result = await db.execute(
                select(models.UserStudyGroup).where(
                    models.UserStudyGroup.group_id == battle.group_id,
                    models.UserStudyGroup.user_id == current_user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {current_user.id} not authorized for group {battle.group_id}")
                raise HTTPException(status_code=403, detail="Not a group member")
            result = await db.execute(
                select(models.UserGroupBossBattle).where(
                    models.UserGroupBossBattle.group_boss_battle_id == battle_id,
                    models.UserGroupBossBattle.user_id == current_user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {current_user.id} not joined battle {battle_id}")
                raise HTTPException(status_code=403, detail="Not a battle participant")
            battle.current_health -= attack.damage
            battle.score += attack.damage
            if battle.current_health <= 0:
                battle.is_completed = True
                battle.passed = True
                battle.current_health = 0
                result = await db.execute(
                    select(models.UserGroupBossBattle).where(
                        models.UserGroupBossBattle.group_boss_battle_id == battle_id
                    )
                )
                for user_battle in result.scalars().all():
                    await award_xp(db, user_battle.user_id, battle.reward_xp)
                    user = await db.execute(
                        select(models.User).where(models.User.id == user_battle.user_id)
                    )
                    user = user.scalars().first()
                    user.skill_points += battle.reward_skill_points
                    db.add(user)
            db.add(battle)
            await db.commit()
            await db.refresh(battle)
        await manager.broadcast_to_group(
            json.dumps({
                "type": "battle_update",
                "battle_id": battle_id,
                "current_health": battle.current_health,
                "score": battle.score,
                "is_completed": battle.is_completed,
                "passed": battle.passed,
                "timestamp": datetime.utcnow().isoformat()
            }),
            f"group_{battle.group_id}"
        )
        logger.info(f"User {current_user.id} attacked group boss battle {battle_id}, dealt {attack.damage} damage")
        return schemas.GroupBossBattleRead.from_orm(battle)
    except Exception as e:
        logger.error(f"Error in attack_group_boss for battle {battle_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to attack group boss: {str(e)}")

@group_boss_battles_router.websocket("/{battle_id}/ws")
async def websocket_group_boss_battle(
    battle_id: int,
    websocket: WebSocket,
    token: str,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        user = await get_current_user(token=token, db=db)
        if not user:
            logger.warning(f"Invalid token for group boss battle WebSocket, battle_id: {battle_id}")
            await websocket.close(code=1008, reason="Invalid token")
            return
        async with db.begin():
            result = await db.execute(
                select(models.GroupBossBattle).where(models.GroupBossBattle.id == battle_id)
            )
            battle = result.scalars().first()
            if not battle:
                logger.warning(f"Group boss battle {battle_id} not found for WebSocket")
                await websocket.close(code=1008, reason="Battle not found")
                return
            result = await db.execute(
                select(models.UserStudyGroup).where(
                    models.UserStudyGroup.group_id == battle.group_id,
                    models.UserStudyGroup.user_id == user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {user.id} not authorized for group {battle.group_id} WebSocket")
                await websocket.close(code=1008, reason="Not a group member")
                return
            result = await db.execute(
                select(models.UserGroupBossBattle).where(
                    models.UserGroupBossBattle.group_boss_battle_id == battle_id,
                    models.UserGroupBossBattle.user_id == user.id
                )
            )
            if not result.scalars().first():
                logger.warning(f"User {user.id} not joined battle {battle_id} for WebSocket")
                await websocket.close(code=1008, reason="Not a battle participant")
                return
        await manager.connect(websocket, f"battle_{battle_id}")
        try:
            while True:
                data = await websocket.receive_json()
                await manager.broadcast_to_group(
                    json.dumps({
                        "type": "battle_update",
                        "battle_id": battle_id,
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    f"battle_{battle_id}",
                    sender=websocket
                )
                logger.debug(f"Broadcast battle update for battle {battle_id}")
        except WebSocketDisconnect:
            manager.disconnect(websocket, f"battle_{battle_id}")
            logger.info(f"WebSocket disconnected for battle {battle_id}")
        except Exception as e:
            logger.error(f"Error in websocket_group_boss_battle for battle {battle_id}: {str(e)}")
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close(code=1003)
    except Exception as e:
        logger.error(f"Error in websocket_group_boss_battle setup for battle {battle_id}: {str(e)}")
        await websocket.close(code=1008, reason="Authentication failed")