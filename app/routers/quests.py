from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.database import get_async_session
from app.auth_deps import get_current_user
from app import schemas, models, crud
from sqlalchemy.orm import selectinload
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

quests_router = APIRouter(prefix="", tags=["quests"])

@quests_router.get("/templates", response_model=list[schemas.QuestRead])
async def get_quest_templates(db: AsyncSession = Depends(get_async_session), user: models.User = Depends(get_current_user)):
    logger.info(f"User {user.id} fetched quest templates")
    return [{
        "id": 1,
        "title": "Sample Quest",
        "description": "A sample quest template",
        "user_id": user.id,
        "quest_type": "daily",
        "difficulty": 1,
        "reward_xp": 100,
        "reward_skill_points": 10,
        "is_completed": False,
        "xp_earned": 0,
        "created_at": datetime.utcnow().isoformat()
    }]

@quests_router.get("/", response_model=list[schemas.QuestRead])
async def get_quests(db: AsyncSession = Depends(get_async_session), user: models.User = Depends(get_current_user)):
    quests = await crud.get_user_quests(db, user.id)
    logger.info(f"User {user.id} fetched {len(quests)} quests")
    return [schemas.QuestRead.model_validate(quest) for quest in quests]

@quests_router.post("/", response_model=schemas.QuestRead)
async def create_quest(quest: schemas.QuestCreate, db: AsyncSession = Depends(get_async_session), user: models.User = Depends(get_current_user)):
    db_quest = await crud.create_quest(db, quest, user.id)
    logger.info(f"User {user.id} created quest {db_quest.id}")
    return schemas.QuestRead.model_validate(db_quest)

@quests_router.get("/{quest_id}", response_model=schemas.QuestRead)
async def get_quest(quest_id: int, db: AsyncSession = Depends(get_async_session), user: models.User = Depends(get_current_user)):
    result = await db.execute(select(models.Quest).where(models.Quest.id == quest_id, models.Quest.user_id == user.id))
    quest = result.scalars().first()
    if not quest:
        logger.warning(f"Quest {quest_id} not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Quest not found")
    logger.info(f"User {user.id} fetched quest {quest_id}")
    return schemas.QuestRead.model_validate(quest)

@quests_router.put("/{quest_id}", response_model=schemas.QuestRead)
async def update_quest(quest_id: int, quest_update: schemas.QuestCreate, db: AsyncSession = Depends(get_async_session), user: models.User = Depends(get_current_user)):
    result = await db.execute(select(models.Quest).where(models.Quest.id == quest_id, models.Quest.user_id == user.id))
    quest = result.scalars().first()
    if not quest:
        logger.warning(f"Quest {quest_id} not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Quest not found")
    for key, value in quest_update.dict(exclude_unset=True).items():
        setattr(quest, key, value)
    db.add(quest)
    await db.commit()
    await db.refresh(quest)
    logger.info(f"User {user.id} updated quest {quest_id}")
    return schemas.QuestRead.model_validate(quest)

@quests_router.delete("/{quest_id}", response_model=dict)
async def delete_quest(quest_id: int, db: AsyncSession = Depends(get_async_session), user: models.User = Depends(get_current_user)):
    result = await db.execute(select(models.Quest).where(models.Quest.id == quest_id, models.Quest.user_id == user.id))
    quest = result.scalars().first()
    if not quest:
        logger.warning(f"Quest {quest_id} not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Quest not found")
    await db.execute(delete(models.Quest).where(models.Quest.id == quest_id))
    await db.commit()
    logger.info(f"User {user.id} deleted quest {quest_id}")
    return {"detail": "Quest deleted"}

@quests_router.post("/{quest_id}/complete", response_model=schemas.QuestRead)
async def complete_quest(
    quest_id: int, 
    db: AsyncSession = Depends(get_async_session), 
    current_user: models.User = Depends(get_current_user)
):
    # FIX: Get fresh user object from session
    result = await db.execute(
        select(models.User)
        .where(models.User.id == current_user.id)
        .options(selectinload(models.User.quests))
    )
    user = result.scalars().first()
    
    result = await db.execute(
        select(models.Quest)
        .where(
            models.Quest.id == quest_id,
            models.Quest.user_id == user.id
        )
    )
    quest = result.scalars().first()
    
    if not quest:
        logger.warning(f"Quest {quest_id} not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Quest not found")
    
    if quest.is_completed:
        logger.warning(f"Quest {quest_id} already completed by user {user.id}")
        raise HTTPException(status_code=400, detail="Quest already completed")
    
    quest.is_completed = True
    quest.xp_earned = quest.reward_xp
    quest.completed_at = datetime.utcnow()
    
    # FIX: Update user through session
    user.xp += quest.reward_xp
    user.skill_points += quest.reward_skill_points
    
    await db.commit()
    await db.refresh(quest)
    
    logger.info(f"User {user.id} completed quest {quest_id}")
    return schemas.QuestRead.model_validate(quest)