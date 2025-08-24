from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
from app import models, schemas, crud
from app.database import get_async_session
from app.routers.auth import get_current_user_optional
from app.connection_manager import ConnectionManager
from app.routers.leveling_router import award_xp
import logging
import json
from datetime import datetime
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

group_boss_battles_router = APIRouter(prefix="", tags=["group_boss_battles"])
manager = ConnectionManager()
templates = Jinja2Templates(directory="templates")

async def verify_group_member(user_id: int, group_id: int, db: AsyncSession) -> bool:
    """Verify that user is a member of the specified group"""
    try:
        result = await db.execute(
            select(models.UserStudyGroup).where(
                models.UserStudyGroup.group_id == group_id,
                models.UserStudyGroup.user_id == user_id
            )
        )
        return result.scalars().first() is not None
    except Exception as e:
        logger.error(f"Error verifying group membership for user {user_id} in group {group_id}: {str(e)}")
        return False

async def check_user_has_groups(user: models.User, db: AsyncSession) -> bool:
    """Check if user is a member of any study group"""
    try:
        result = await db.execute(
            select(models.UserStudyGroup).where(
                models.UserStudyGroup.user_id == user.id
            )
        )
        user_groups = result.scalars().all()
        return len(user_groups) > 0
    except Exception as e:
        logger.error(f"Error checking user groups for user {user.id}: {str(e)}")
        return False

@group_boss_battles_router.get("/", response_class=HTMLResponse)
async def get_boss_battles_page(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user_optional)
):
    try:
        if not current_user:
            logger.warning("Unauthorized access attempt to boss battles page")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Check if user is in any study groups
        has_groups = await check_user_has_groups(current_user, db)
        if not has_groups:
            logger.warning(f"User {current_user.id} attempted to access boss battles without being in a study group")
            raise HTTPException(
                status_code=403, 
                detail="Boss battles are only available to study group members. Join a study group first!"
            )
        
        # Get group ID from user's first group
        result = await db.execute(
            select(models.UserStudyGroup.group_id).where(
                models.UserStudyGroup.user_id == current_user.id
            ).limit(1)
        )
        group_id = result.scalar_one_or_none()
        
        if not group_id:
            raise HTTPException(status_code=404, detail="User has no study groups")
        
        # Get battles for the group
        result = await db.execute(
            select(models.GroupBossBattle).where(
                models.GroupBossBattle.group_id == group_id
            ).order_by(models.GroupBossBattle.created_at.desc())
        )
        battles = result.scalars().all()
        
        logger.info(f"Fetched {len(battles)} group boss battles for user {current_user.id}")
        return templates.TemplateResponse(
            "boss_battles.html",
            {"request": request, "battles": battles, "user": current_user, "group_id": group_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_boss_battles_page for user {current_user.id if current_user else 'unknown'}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch boss battles: {str(e)}")

@group_boss_battles_router.get("/check-access", response_model=dict)
async def check_boss_battle_access(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user_optional)
):
    """Check if user has access to boss battles"""
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to check boss battle access")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        has_groups = await check_user_has_groups(current_user, db)
        
        # Get user's groups for additional info
        result = await db.execute(
            select(models.UserStudyGroup)
            .join(models.StudyGroup)
            .where(models.UserStudyGroup.user_id == current_user.id)
        )
        user_groups = result.scalars().all()
        
        logger.info(f"Checked boss battle access for user {current_user.id}: {has_groups}")
        return {
            'has_access': has_groups,
            'group_count': len(user_groups),
            'message': 'Access granted' if has_groups else 'You must be a member of a study group to access boss battles'
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking boss battle access for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check access: {str(e)}")

@group_boss_battles_router.post("/", response_model=schemas.GroupBossBattleRead)
async def create_group_boss_battle(
    battle: schemas.GroupBossBattleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user_optional)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to create group boss battle")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Verify group exists
        result = await db.execute(
            select(models.StudyGroup).where(models.StudyGroup.id == battle.group_id)
        )
        group = result.scalars().first()
        if not group:
            logger.warning(f"Group {battle.group_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail="Study group not found")
        
        # Verify user is a member of the group
        is_member = await verify_group_member(current_user.id, battle.group_id, db)
        if not is_member:
            logger.warning(f"User {current_user.id} not authorized for group {battle.group_id}")
            raise HTTPException(status_code=403, detail="You must be a member of this study group to create group boss battles")
        
        if battle.difficulty < 1 or battle.difficulty > 10:
            logger.warning(f"Invalid difficulty {battle.difficulty} for group boss battle by user {current_user.id}")
            raise HTTPException(status_code=400, detail="Difficulty must be between 1 and 10")
        
        # Create the battle
        db_battle = await crud.create_group_boss_battle(db, battle, battle.group_id)
        
        # Broadcast battle creation to group members
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_group_boss_battle for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group boss battle: {str(e)}")

@group_boss_battles_router.get("/{battle_id}", response_model=schemas.GroupBossBattleRead)
async def get_group_boss_battle(
    battle_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user_optional)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to get group boss battle")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get battle and verify it exists
        result = await db.execute(
            select(models.GroupBossBattle).where(models.GroupBossBattle.id == battle_id)
        )
        battle = result.scalars().first()
        if not battle:
            logger.warning(f"Group boss battle {battle_id} not found")
            raise HTTPException(status_code=404, detail="Battle not found")
        
        # Verify user is a member of the group
        is_member = await verify_group_member(current_user.id, battle.group_id, db)
        if not is_member:
            logger.warning(f"User {current_user.id} not authorized for group {battle.group_id}")
            raise HTTPException(status_code=403, detail="You must be a member of this study group to view group boss battles")
        
        logger.info(f"Retrieved group boss battle {battle_id} for user {current_user.id}")
        return schemas.GroupBossBattleRead.from_orm(battle)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_group_boss_battle for battle {battle_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group boss battle: {str(e)}")

@group_boss_battles_router.get("/group/{group_id}", response_model=List[schemas.GroupBossBattleRead])
async def get_group_boss_battles(
    group_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user_optional)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to list group boss battles")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Verify group exists
        result = await db.execute(
            select(models.StudyGroup).where(models.StudyGroup.id == group_id)
        )
        group = result.scalars().first()
        if not group:
            logger.warning(f"Group {group_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail="Study group not found")
        
        # Verify user is a member of the group
        is_member = await verify_group_member(current_user.id, group_id, db)
        if not is_member:
            logger.warning(f"User {current_user.id} not authorized for group {group_id}")
            raise HTTPException(status_code=403, detail="You must be a member of this study group to view group boss battles")
        
        # Get battles for the group
        result = await db.execute(
            select(models.GroupBossBattle).where(
                models.GroupBossBattle.group_id == group_id
            ).order_by(models.GroupBossBattle.created_at.desc())
        )
        battles = result.scalars().all()
        
        logger.info(f"Fetched {len(battles)} group boss battles for group {group_id}")
        return [schemas.GroupBossBattleRead.from_orm(battle) for battle in battles]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_group_boss_battles for group {group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list group boss battles: {str(e)}")

@group_boss_battles_router.post("/{battle_id}/join", response_model=dict)
async def join_group_boss_battle(
    battle_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user_optional)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to join group boss battle")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get battle and verify it exists
        result = await db.execute(
            select(models.GroupBossBattle).where(models.GroupBossBattle.id == battle_id)
        )
        battle = result.scalars().first()
        if not battle:
            logger.warning(f"Group boss battle {battle_id} not found")
            raise HTTPException(status_code=404, detail="Battle not found")
        
        # Verify user is a member of the group
        is_member = await verify_group_member(current_user.id, battle.group_id, db)
        if not is_member:
            logger.warning(f"User {current_user.id} not authorized for group {battle.group_id}")
            raise HTTPException(status_code=403, detail="You must be a member of this study group to join group boss battles")
        
        # Check if battle is still active
        if battle.is_completed:
            logger.warning(f"Battle {battle_id} already completed")
            raise HTTPException(status_code=400, detail="Battle is already completed")
        
        # Check if user already joined
        result = await db.execute(
            select(models.UserGroupBossBattle).where(
                models.UserGroupBossBattle.group_boss_battle_id == battle_id,
                models.UserGroupBossBattle.user_id == current_user.id
            )
        )
        if result.scalars().first():
            logger.warning(f"User {current_user.id} already joined battle {battle_id}")
            raise HTTPException(status_code=400, detail="Already joined battle")
        
        # Join the battle
        await crud.join_group_boss_battle(db, battle_id, current_user.id)
        
        # Broadcast user joined to group members
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in join_group_boss_battle for battle {battle_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to join group boss battle: {str(e)}")

@group_boss_battles_router.post("/{battle_id}/attack", response_model=schemas.GroupBossBattleRead)
async def attack_group_boss(
    battle_id: int,
    attack: schemas.BossAttack,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user_optional)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to attack group boss")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get battle and verify it exists and is not completed
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
        
        # Verify user is a member of the group
        is_member = await verify_group_member(current_user.id, battle.group_id, db)
        if not is_member:
            logger.warning(f"User {current_user.id} not authorized for group {battle.group_id}")
            raise HTTPException(status_code=403, detail="You must be a member of this study group to attack in group boss battles")
        
        # Verify user is a participant in the battle
        result = await db.execute(
            select(models.UserGroupBossBattle).where(
                models.UserGroupBossBattle.group_boss_battle_id == battle_id,
                models.UserGroupBossBattle.user_id == current_user.id
            )
        )
        if not result.scalars().first():
            logger.warning(f"User {current_user.id} not joined battle {battle_id}")
            raise HTTPException(status_code=403, detail="You must join the battle first to attack")
        
        # Process the attack
        async with db.begin():
            battle.current_health -= attack.damage
            battle.score += attack.damage
            
            if battle.current_health <= 0:
                battle.is_completed = True
                battle.passed = True
                battle.current_health = 0
                
                # Award rewards to all participants
                result = await db.execute(
                    select(models.UserGroupBossBattle).where(
                        models.UserGroupBossBattle.group_boss_battle_id == battle_id
                    )
                )
                for user_battle in result.scalars().all():
                    await award_xp(db, user_battle.user_id, battle.reward_xp)
                    user_result = await db.execute(
                        select(models.User).where(models.User.id == user_battle.user_id)
                    )
                    user = user_result.scalars().first()
                    if user:
                        user.skill_points += battle.reward_skill_points
                        db.add(user)
            
            db.add(battle)
            await db.commit()
            await db.refresh(battle)
        
        # Broadcast battle update to group members
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
    except HTTPException:
        raise
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
        user = await get_current_user_optional(token=token, db=db)
        if not user:
            logger.warning(f"Invalid token for group boss battle WebSocket, battle_id: {battle_id}")
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Get battle and verify it exists
        result = await db.execute(
            select(models.GroupBossBattle).where(models.GroupBossBattle.id == battle_id)
        )
        battle = result.scalars().first()
        if not battle:
            logger.warning(f"Group boss battle {battle_id} not found for WebSocket")
            await websocket.close(code=1008, reason="Battle not found")
            return
        
        # Verify user is a member of the group
        is_member = await verify_group_member(user.id, battle.group_id, db)
        if not is_member:
            logger.warning(f"User {user.id} not authorized for group {battle.group_id} WebSocket")
            await websocket.close(code=1008, reason="Not a group member")
            return
        
        # Verify user is a participant in the battle
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
        logger.info(f"WebSocket connected for user {user.id} to battle {battle_id}")
        
        try:
            while True:
                data = await websocket.receive_json()
                
                # Handle chat messages
                if data.get("type") == "chat_message":
                    await manager.broadcast_to_group(
                        json.dumps({
                            "type": "chat_message",
                            "battle_id": battle_id,
                            "user_id": user.id,
                            "username": user.username,
                            "content": data.get("content", ""),
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        f"battle_{battle_id}"
                    )
                else:
                    # Handle other battle updates
                    await manager.broadcast_to_group(
                        json.dumps({
                            "type": "battle_update",
                            "battle_id": battle_id,
                            "user_id": user.id,
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
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except:
                pass
            await websocket.close(code=1003)
    except Exception as e:
        logger.error(f"Error in websocket_group_boss_battle setup for battle {battle_id}: {str(e)}")
        try:
            await websocket.close(code=1008, reason="Authentication failed")
        except:
            pass