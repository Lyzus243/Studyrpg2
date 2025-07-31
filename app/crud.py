from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app import models, schemas
from datetime import datetime
from typing import List, Optional
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession
from app import models
from app.schemas import SkillCreate, ItemBase

async def create_skill(db: AsyncSession, skill: SkillCreate):
    db_skill = models.Skill(**skill.dict())
    db.add(db_skill)
    await db.commit()
    await db.refresh(db_skill)
    return db_skill

async def create_item(db: AsyncSession, item: ItemBase):
    db_item = models.Item(**item.dict())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def create_user(db: AsyncSession, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=user.hashed_password,
        is_verified=False,
        xp=0,
        skill_points=100,  # Changed from 0 to 100
        streak=0,
        level=1,
        currency=100
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    logger.info(f"Created user {db_user.id}")
    return db_user

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.username == username))
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalars().first()

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    return result.scalars().first()

async def update_user(db: AsyncSession, user: models.User, user_update: schemas.UserUpdate) -> models.User:
    if user_update.username:
        user.username = user_update.username
    if user_update.email:
        user.email = user_update.email
    if user_update.avatar_url:
        user.avatar_url = user_update.avatar_url
    user.last_active = datetime.utcnow()
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Updated user {user.id}")
    return user

async def create_study_group(db: AsyncSession, group: schemas.StudyGroupCreate, creator_id: int) -> models.StudyGroup:
    db_group = models.StudyGroup(
        name=group.name,
        description=group.description,
        creator_id=creator_id,
        created_at=datetime.utcnow()
    )
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    logger.info(f"Created study group {db_group.id}")
    return db_group

async def add_user_to_group(db: AsyncSession, group_id: int, user_id: int) -> models.UserStudyGroup:
    db_user_group = models.UserStudyGroup(user_id=user_id, group_id=group_id)
    db.add(db_user_group)
    await db.commit()
    logger.info(f"Added user {user_id} to study group {group_id}")
    return db_user_group

async def acquire_skill(db: AsyncSession, skill_id: int, user_id: int) -> models.UserSkill:
    """Create a new user-skill association"""
    db_user_skill = models.UserSkill(
        user_id=user_id,
        skill_id=skill_id,
        acquired_at=datetime.utcnow()
    )
    db.add(db_user_skill)
    await db.commit()
    await db.refresh(db_user_skill)
    logger.info(f"User {user_id} acquired skill {skill_id}")
    return db_user_skill

async def remove_user_from_group(db: AsyncSession, group_id: int, user_id: int) -> bool:
    result = await db.execute(
        delete(models.UserStudyGroup).where(
            models.UserStudyGroup.group_id == group_id,
            models.UserStudyGroup.user_id == user_id
        )
    )
    await db.commit()
    success = result.rowcount > 0
    if success:
        logger.info(f"Removed user {user_id} from study group {group_id}")
    return success

async def get_study_group(db: AsyncSession, group_id: int) -> Optional[models.StudyGroup]:
    result = await db.execute(
        select(models.StudyGroup)
        .where(models.StudyGroup.id == group_id)
        .options(selectinload(models.StudyGroup.members))
    )
    return result.scalars().first()

async def get_user_study_groups(db: AsyncSession, user_id: int) -> List[models.StudyGroup]:
    result = await db.execute(
        select(models.StudyGroup)
        .join(models.UserStudyGroup)
        .where(models.UserStudyGroup.user_id == user_id)
        .options(selectinload(models.StudyGroup.members))
    )
    return result.scalars().all()

async def create_group_message(db: AsyncSession, message: schemas.GroupMessageCreate, group_id: int, user_id: int) -> models.GroupMessage:
    db_message = models.GroupMessage(
        group_id=group_id,
        user_id=user_id,
        content=message.content,
        timestamp=datetime.utcnow()
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    logger.info(f"Created group message {db_message.id} in group {group_id}")
    return db_message

async def create_quest(db: AsyncSession, quest: schemas.QuestCreate, user_id: int) -> models.Quest:
    db_quest = models.Quest(
        user_id=user_id,
        title=quest.title,
        description=quest.description,
        quest_type=quest.quest_type,
        difficulty=quest.difficulty,
        reward_xp=quest.reward_xp,
        reward_skill_points=quest.reward_skill_points,
        created_at=datetime.utcnow()
    )
    db.add(db_quest)
    await db.commit()
    await db.refresh(db_quest)
    logger.info(f"Created quest {db_quest.id} for user {user_id}")
    return db_quest

async def get_user_quests(db: AsyncSession, user_id: int, completed: Optional[bool] = None) -> List[models.Quest]:
    query = select(models.Quest).where(models.Quest.user_id == user_id)
    if completed is not None:
        query = query.where(models.Quest.is_completed == completed)
    result = await db.execute(query.order_by(models.Quest.created_at.desc()).limit(50))
    return result.scalars().all()

async def create_boss_battle(db: AsyncSession, battle: schemas.BossBattleCreate, user_id: int) -> models.BossBattle:
    db_battle = models.BossBattle(
        user_id=user_id,
        name=battle.name,
        difficulty=battle.difficulty,
        current_health=battle.current_health,
        max_health=battle.max_health,
        reward_xp=battle.reward_xp,
        reward_skill_points=battle.reward_skill_points,
        reward_items=battle.reward_items
    )
    db.add(db_battle)
    await db.commit()
    await db.refresh(db_battle)
    logger.info(f"Created boss battle {db_battle.id} for user {user_id}")
    return db_battle

async def create_group_boss_battle(db: AsyncSession, battle: schemas.GroupBossBattleCreate, group_id: int) -> models.GroupBossBattle:
    db_battle = models.GroupBossBattle(
        group_id=group_id,
        name=battle.name,
        difficulty=battle.difficulty,
        current_health=battle.current_health,
        group_health=battle.group_health,
        score=battle.score,
        reward_xp=battle.reward_xp,
        reward_skill_points=battle.reward_skill_points,
        reward_items=battle.reward_items,
        created_at=datetime.utcnow()
    )
    db.add(db_battle)
    await db.commit()
    await db.refresh(db_battle)
    logger.info(f"Created group boss battle {db_battle.id} for group {group_id}")
    return db_battle

async def join_group_boss_battle(db: AsyncSession, battle_id: int, user_id: int) -> models.UserGroupBossBattle:
    db_user_battle = models.UserGroupBossBattle(
        group_boss_battle_id=battle_id,
        user_id=user_id
    )
    db.add(db_user_battle)
    await db.commit()
    logger.info(f"User {user_id} joined group boss battle {battle_id}")
    return db_user_battle

async def get_group_boss_battles(db: AsyncSession, group_id: int) -> List[models.GroupBossBattle]:
    result = await db.execute(
        select(models.GroupBossBattle)
        .where(models.GroupBossBattle.group_id == group_id)
        .options(selectinload(models.GroupBossBattle.users))
        .order_by(models.GroupBossBattle.created_at.desc())
    )
    return result.scalars().all()

async def create_pomodoro_session(db: AsyncSession, session: schemas.PomodoroSessionCreate, user_id: int) -> models.PomodoroSession:
    db_session = models.PomodoroSession(
        user_id=user_id,
        start_time=datetime.utcnow(),
        duration=session.duration
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    logger.info(f"Created pomodoro session {db_session.id} for user {user_id}")
    return db_session

async def get_pomodoro_sessions(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 50) -> List[models.PomodoroSession]:
    result = await db.execute(
        select(models.PomodoroSession)
        .where(models.PomodoroSession.user_id == user_id)
        .order_by(models.PomodoroSession.start_time.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_pomodoro_stats(db: AsyncSession, user_id: int, start_date: datetime, end_date: datetime) -> dict:
    from sqlalchemy.sql import func
    result = await db.execute(
        select(
            func.count(models.PomodoroSession.id).label("total_sessions"),
            func.sum(models.PomodoroSession.duration).label("total_minutes"),
            func.avg(models.PomodoroSession.duration).label("average_duration"),
            func.sum(models.PomodoroSession.xp_earned).label("total_xp")
        )
        .where(
            models.PomodoroSession.user_id == user_id,
            models.PomodoroSession.start_time >= start_date,
            models.PomodoroSession.start_time <= end_date,
            models.PomodoroSession.is_completed == True
        )
    )
    stats = result.first()
    return {
        "total_sessions": stats.total_sessions or 0,
        "total_duration": stats.total_minutes or 0,
        "average_duration": float(stats.average_duration or 0),
        "total_xp_earned": stats.total_xp or 0
    }

async def create_flashcard(db: AsyncSession, flashcard: schemas.FlashcardCreate, user_id: int) -> models.Flashcard:
    db_flashcard = models.Flashcard(
        user_id=user_id,
        question=flashcard.question,
        answer=flashcard.answer,
        created_at=datetime.utcnow()
    )
    db.add(db_flashcard)
    await db.commit()
    await db.refresh(db_flashcard)
    logger.info(f"Created flashcard {db_flashcard.id} for user {user_id}")
    return db_flashcard

async def create_user_flashcard(db: AsyncSession, user_flashcard: schemas.UserFlashcardCreate, user_id: int) -> models.UserFlashcard:
    db_user_flashcard = models.UserFlashcard(
        user_id=user_id,
        flashcard_id=user_flashcard.flashcard_id,
        proficiency=user_flashcard.proficiency
    )
    db.add(db_user_flashcard)
    await db.commit()
    await db.refresh(db_user_flashcard)
    logger.info(f"Created user flashcard {db_user_flashcard.id} for user {user_id}")
    return db_user_flashcard

async def get_flashcard_progress(db: AsyncSession, user_id: int) -> List[models.UserFlashcard]:
    result = await db.execute(
        select(models.UserFlashcard)
        .where(models.UserFlashcard.user_id == user_id)
        .options(selectinload(models.UserFlashcard.flashcard))
    )
    return result.scalars().all()

async def create_memory_session(db: AsyncSession, session: schemas.MemorySessionCreate, user_id: int, sequence: List[int]) -> models.MemorySession:
    db_session = models.MemorySession(
        user_id=user_id,
        sequence_length=session.sequence_length,
        sequence=json.dumps(sequence),
        start_time=datetime.utcnow(),
        duration=0,
        score=0
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    logger.info(f"Created memory session {db_session.id} for user {user_id}")
    return db_session

async def create_skill(db: AsyncSession, skill: schemas.SkillCreate) -> models.Skill:
    db_skill = models.Skill(
        name=skill.name,
        description=skill.description,
        cost=skill.cost
    )
    db.add(db_skill)
    await db.commit()
    await db.refresh(db_skill)
    logger.info(f"Created skill {db_skill.id}")
    return db_skill

async def create_item(db: AsyncSession, item: schemas.ItemCreate) -> models.Item:
    db_item = models.Item(
        name=item.name,
        price=item.price,
        description=item.description
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    logger.info(f"Created item {db_item.id}")
    return db_item

async def purchase_item(db: AsyncSession, item_id: int, user_id: int) -> models.UserItem:
    db_user_item = models.UserItem(
        user_id=user_id,
        item_id=item_id,
        is_used=False
    )
    db.add(db_user_item)
    await db.commit()
    await db.refresh(db_user_item)
    logger.info(f"User {user_id} purchased item {item_id}")
    return db_user_item

async def create_password_reset(db: AsyncSession, user_id: int, token: str, expires_at: datetime) -> models.PasswordReset:
    db_reset = models.PasswordReset(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_reset)
    await db.commit()
    await db.refresh(db_reset)
    logger.info(f"Created password reset for user {user_id}")
    return db_reset

async def get_password_reset(db: AsyncSession, token: str) -> Optional[models.PasswordReset]:
    result = await db.execute(
        select(models.PasswordReset).where(models.PasswordReset.token == token)
    )
    return result.scalars().first()

async def get_material(db: AsyncSession, material_id: int) -> Optional[models.Material]:
    result = await db.execute(select(models.Material).where(models.Material.id == material_id))
    return result.scalars().first()

async def get_boss_battles(db: AsyncSession, user_id: int) -> List[models.BossBattle]:
    result = await db.execute(
        select(models.BossBattle)
        .where(models.BossBattle.user_id == user_id)
        .order_by(models.BossBattle.created_at.desc())
    )
    return result.scalars().all()
