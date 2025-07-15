

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import User
from bcrypt import checkpw
from sqlmodel import Session, select
from app.models import User, PasswordReset, StudyGroup, GroupMember, GroupQuest, GroupBossBattle, Quest, Skill, UserSkill, MemoryTrainingSession, PomodoroSession, UserAnalytics, CourseMaterial, MaterialTestAttempt, BossBattle, FlashcardDeck, Flashcard, GroupMessage
from app.schemas import UserCreate, StudyGroupCreate, QuestCreate, QuestUpdate, BossBattleCreate, GroupBossBattleCreate, SkillCreate, FlashcardCreate
from fastapi import HTTPException
from datetime import datetime, timedelta, date
from typing import List, Optional
from app.database import engine
from bcrypt import hashpw, checkpw, gensalt
import json

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import User
from app.schemas import UserCreate
from bcrypt import hashpw, gensalt
from datetime import datetime

async def create_user(db: AsyncSession, user: UserCreate):
    """Create a new user with hashed password."""
    hashed_password = hashpw(user.password.encode('utf-8'), gensalt()).decode('utf-8')
    db_user = User(
        username=user.username,
        email=user.email.lower(),
        hashed_password=hashed_password,
        avatar_url=user.avatar_url or None,
        created_at=datetime.utcnow(),
        is_verified=False,
        is_active=True
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

def record_user_activity(db: Session, user_id: int):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    today = datetime.utcnow().date()
    if user.last_login:
        last_login_date = user.last_login.date()
        if last_login_date == today:
            pass
        elif last_login_date == today - timedelta(days=1):
            user.streak += 1
        else:
            user.streak = 1
    else:
        user.streak = 1
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

async def reset_inactive_streaks(db: Session):
    users = db.execute(select(User).where(User.last_login < datetime.utcnow() - timedelta(days=1))).all()
    for user in users:
        user.streak = 0
    db.commit()

def get_user(db: Session, user_id: int):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def get_user_by_email(db: Session, email: str):
    return db.execute(select(User).where(User.email == email.lower())).first()

async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()

async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = await get_user_by_username(db, username)
    if not user or not checkpw(password.encode('utf-8'), user.hashed_password.encode('utf-8')):
        return None
    return user
def get_password_hash(password: str) -> str:
    return hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')

def create_user(db: Session, user: UserCreate):
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    user_db = User(
        username=user.username,
        email=user.email.lower(),
        hashed_password=hashed_password,
        avatar_url=user.avatar_url
    )
    db.add(user_db)
    db.commit()
    db.refresh(user_db)
    return user_db

def update_user(db: Session, user_id: int, user_data: dict):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for key, value in user_data.items():
        if value is not None:
            if key == "password":
                value = get_password_hash(value)
            setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_study_group(db: Session, group_id: int):
    group = db.get(StudyGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Study group not found")
    return group

def create_study_group(db: Session, group: StudyGroupCreate, creator_id: int):
    group_db = StudyGroup(**group.dict(), creator_id=creator_id, current_members=1)
    db.add(group_db)
    db.commit()
    db.refresh(group_db)
    db.add(GroupMember(user_id=creator_id, group_id=group_db.id, role="creator"))
    db.commit()
    return group_db

def update_study_group(db: Session, group_id: int, group_data: dict):
    group = db.get(StudyGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Study group not found")
    for key, value in group_data.items():
        if value is not None:
            setattr(group, key, value)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

def add_group_member(db: Session, group_id: int, user_id: int, role: str = "member"):
    group = db.get(StudyGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Study group not found")
    if group.current_members >= group.max_members:
        raise HTTPException(status_code=400, detail="Group is full")
    if db.execute(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)).first():
        raise HTTPException(status_code=400, detail="User already in group")
    member = GroupMember(user_id=user_id, group_id=group_id, role=role)
    group.current_members += 1
    db.add(member)
    db.add(group)
    db.commit()
    return member

def get_study_groups(db: Session, user_id: int, query: Optional[str] = None, group_id: Optional[int] = None) -> List[StudyGroup]:
    statement = select(StudyGroup).join(GroupMember).where(GroupMember.user_id == user_id)
    if group_id:
        statement = select(StudyGroup).where(StudyGroup.id == group_id)
    elif query:
        statement = select(StudyGroup).where(StudyGroup.name.ilike(f"%{query}%") | StudyGroup.description.ilike(f"%{query}%"))
    groups = db.execute(statement).all()
    for group in groups:
        last_seen = db.execute(select(GroupMember.joined_at).where(GroupMember.group_id == group.id, GroupMember.user_id == user_id)).scalar() or datetime.min
        group.unread_count = db.execute(select(GroupMessage).where(GroupMessage.group_id == group.id, GroupMessage.timestamp > last_seen)).count()
    return groups


from sqlmodel import Session
from app.models import User
import uuid
def generate_reset_token(db: Session, user_id: int):
    token = str(uuid.uuid4())
    reset = PasswordReset(
        user_id=user_id,
        token=token,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(reset)
    db.commit()
    db.refresh(reset)
    return token

def validate_reset_token(db: Session, token: str):
    reset = db.execute(
        select(PasswordReset).where(
            PasswordReset.token == token,
            PasswordReset.expires_at > datetime.utcnow()
        )
    ).first()
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    return reset.user_id


def update_user_password(db: Session, user_id: int, new_password: str):
    return update_user(db, user_id, {"password": new_password})

def get_quest(db: Session, quest_id: int):
    quest = db.get(Quest, quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quest

def create_quest(db: Session, quest: QuestCreate, user_id: int) -> Quest:
    quest_db = Quest(
        user_id=user_id,
        title=quest.title,
        description=quest.description,
        quest_type=quest.quest_type,
        recurring=quest.recurring,
        xp_reward=quest.xp_reward or 100
    )
    db.add(quest_db)
    db.commit()
    db.refresh(quest_db)
    return quest_db

def update_quest(db: Session, quest_id: int, quest: QuestUpdate, user_id: int) -> Quest:
    quest_db = db.execute(select(Quest).where(Quest.id == quest_id, Quest.user_id == user_id)).first()
    if not quest_db:
        raise HTTPException(status_code=404, detail="Quest not found")
    for key, value in quest.dict(exclude_unset=True).items():
        setattr(quest_db, key, value)
    db.commit()
    db.refresh(quest_db)
    return quest_db

def complete_quest(db: Session, quest_id: int, user_id: int) -> Quest:
    quest = db.execute(select(Quest).where(Quest.id == quest_id, Quest.user_id == user_id)).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    if quest.completed and not quest.recurring:
        raise HTTPException(status_code=400, detail="Quest already completed")
    quest.completed = False if quest.recurring else True
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.xp += quest.xp_reward
    db.commit()
    db.refresh(quest)
    return quest

def delete_quest(db: Session, quest_id: int, user_id: int):
    quest = db.execute(select(Quest).where(Quest.id == quest_id, Quest.user_id == user_id)).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    db.delete(quest)
    db.commit()
    return {"message": "Quest deleted"}

def get_group_quest(db: Session, group_quest_id: int):
    quest = db.get(GroupQuest, group_quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Group quest not found")
    return quest

def create_group_quest(db: Session, quest_data: dict, group_id: int, user_id: int):
    quest = GroupQuest(**quest_data, group_id=group_id, user_id=user_id)
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest

def create_group_boss_battle(db: Session, battle: GroupBossBattleCreate, group_id: int, user_id: int):
    battle_db = GroupBossBattle(
        **battle.dict(),
        group_id=group_id,
        created_by=user_id,
        current_health=battle.max_health,
        score=0
    )
    db.add(battle_db)
    db.commit()
    db.refresh(battle_db)
    return battle_db

def get_group_boss_battles(db: Session, group_id: int) -> List[GroupBossBattle]:
    return db.execute(select(GroupBossBattle).where(GroupBossBattle.group_id == group_id)).all()

def get_boss_battle(db: Session, battle_id: int):
    battle = db.get(BossBattle, battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="Boss battle not found")
    return battle

def has_passed_boss(db: Session, user_id: int, battle_id: int):
    battle = db.get(BossBattle, battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="Boss battle not found")
    return battle.passed

def create_boss_battle(db: Session, battle: BossBattleCreate, user_id: int):
    battle_db = BossBattle(
        **battle.dict(),
        user_id=user_id,
        current_health=battle.max_health
    )
    db.add(battle_db)
    db.commit()
    db.refresh(battle_db)
    return battle_db

def get_boss_battles(db: Session, user_id: int) -> List[BossBattle]:
    return db.execute(select(BossBattle).where(BossBattle.user_id == user_id)).all()

def get_skill(db: Session, skill_id: int):
    skill = db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill

def create_skill(db: Session, skill: SkillCreate):
    skill_db = Skill(**skill.dict())
    db.add(skill_db)
    db.commit()
    db.refresh(skill_db)
    return skill_db

def unlock_skill(db: Session, user_id: int, skill_id: int):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if not db.get(Skill, skill_id):
        raise HTTPException(status_code=404, detail="Skill not found")
    if db.execute(select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.skill_id == skill_id)).first():
        raise HTTPException(status_code=400, detail="Skill already unlocked")
    user_skill = UserSkill(user_id=user_id, skill_id=skill_id)
    db.add(user_skill)
    db.commit()
    return user_skill

def get_user_skills(db: Session, user_id: int):
    return db.execute(select(Skill).join(UserSkill).where(UserSkill.user_id == user_id)).all()

def get_unlocked_skills(db: Session, user_id: int):
    return db.execute(select(Skill).join(UserSkill).where(UserSkill.user_id == user_id)).all()

def create_pomodoro_session(db: Session, user_id: int, duration: int):
    session = PomodoroSession(user_id=user_id, start_time=datetime.utcnow(), duration=duration)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_pomodoro_history(db: Session, user_id: int):
    return db.execute(select(PomodoroSession).where(PomodoroSession.user_id == user_id).order_by(PomodoroSession.start_time.desc())).all()

def get_todays_stats(db: Session, user_id: int):
    today = datetime.utcnow().date()
    sessions = db.execute(
        select(PomodoroSession).where(
            PomodoroSession.user_id == user_id,
            PomodoroSession.start_time >= today,
            PomodoroSession.start_time < today + timedelta(days=1)
        )
    ).all()
    total_duration = sum(session.duration for session in sessions if session.completed)
    completed_sessions = len([s for s in sessions if s.completed])
    return {"total_duration": total_duration, "completed_sessions": completed_sessions}

def create_memory_session(db: Session, user_id: int, content: str, score: int, is_ai_generated: bool):
    session = MemoryTrainingSession(user_id=user_id, content=content, score=score, is_ai_generated=is_ai_generated)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_memory_sessions(db: Session, user_id: int):
    return db.execute(select(MemoryTrainingSession).where(MemoryTrainingSession.user_id == user_id)).all()

def evaluate_memory_session(db: Session, session_id: int, score: int):
    session = db.get(MemoryTrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Memory session not found")
    session.score = score
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_analytics_data(db: Session, user_id: int, start_date: date, end_date: date):
    return db.execute(
        select(UserAnalytics).where(
            UserAnalytics.user_id == user_id,
            UserAnalytics.date >= start_date,
            UserAnalytics.date <= end_date
        )
    ).all()

def get_chart_data(db: Session, user_id: int):
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    analytics = get_analytics_data(db, user_id, start_date, end_date)
    labels = [(start_date + timedelta(days=i)).isoformat() for i in range(7)]
    values = [0] * 7
    for record in analytics:
        day_index = (record.date.date() - start_date).days
        if 0 <= day_index < 7:
            values[day_index] += record.value
    return labels, values

def create_flashcard_deck(db: Session, deck_data: dict):
    deck = FlashcardDeck(**deck_data)
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return deck

def get_flashcards(db: Session, deck_id: int):
    return db.execute(select(Flashcard).where(Flashcard.deck_id == deck_id)).all()

def create_user_flashcard(db: Session, user_flashcard: FlashcardCreate, user_id: int):
    deck = db.get(FlashcardDeck, user_flashcard.deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Flashcard deck not found")
    if deck.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    flashcard = Flashcard(
        deck_id=user_flashcard.deck_id,
        question=user_flashcard.question,
        answer=user_flashcard.answer,
        created_at=datetime.utcnow()
    )
    db.add(flashcard)
    db.commit()
    db.refresh(flashcard)
    return flashcard

def get_flashcard_progress(db: Session, user_id: int):
    return db.execute(
        select(Flashcard).join(FlashcardDeck).where(FlashcardDeck.user_id == user_id)
    ).all()
