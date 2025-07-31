from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from typing import List, Optional
from datetime import datetime

# --------------------------
# SCHEMAS (Pydantic Models)
# --------------------------

class UserRead(SQLModel):
    id: int
    username: str
    email: str
    xp: int
    skill_points: int
    streak: int
    avatar_url: Optional[str] = None
    level: int
    currency: int

class UserCreate(SQLModel):
    username: str
    email: str
    password: str

class UserUpdate(SQLModel):
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    xp: Optional[int] = None
    skill_points: Optional[int] = None
    streak: Optional[int] = None
    level: Optional[int] = None
    currency: Optional[int] = None

class MemorySessionRead(SQLModel):
    id: int
    user_id: int
    start_time: datetime
    duration: int
    score: int
    sequence_length: int
    is_completed: bool
    is_correct: Optional[bool] = None
    xp_earned: int

class MemorySessionCreate(SQLModel):
    sequence_length: int

class MemorySessionSubmission(SQLModel):
    user_sequence: List[int]

# --------------------------
# DATABASE MODELS (SQLModel)
# --------------------------

class User(SQLModel, table=True):
    __tablename__ = "user"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_verified: bool = Field(default=False)
    xp: int = Field(default=0)  # Single XP field now
    skill_points: int = Field(default=0)
    streak: int = Field(default=0)
    avatar_url: Optional[str] = Field(default=None)
    level: int = Field(default=1)
    last_active: Optional[datetime] = Field(default=None)
    currency: int = Field(default=100)
    password_resets: List["PasswordReset"] = Relationship(back_populates="user")
    pomodoro_sessions: List["PomodoroSession"] = Relationship(back_populates="user")
    quests: List["Quest"] = Relationship(back_populates="user")
    boss_battles: List["BossBattle"] = Relationship(back_populates="user")
    study_groups: List["StudyGroup"] = Relationship(back_populates="members", sa_relationship_kwargs={"secondary": "user_study_group"})
    group_messages: List["GroupMessage"] = Relationship(back_populates="user")
    flashcards: List["Flashcard"] = Relationship(back_populates="user")
    user_flashcards: List["UserFlashcard"] = Relationship(back_populates="user")
    memory_sessions: List["MemorySession"] = Relationship(back_populates="user")
    skills: List["Skill"] = Relationship(back_populates="users", sa_relationship_kwargs={"secondary": "user_skill"})
    items: List["Item"] = Relationship(back_populates="users", sa_relationship_kwargs={"secondary": "user_item"})
    group_boss_battles: List["GroupBossBattle"] = Relationship(back_populates="users", sa_relationship_kwargs={"secondary": "user_group_boss_battle"})
    materials: List["Material"] = Relationship(back_populates="user")
    tests: List["Test"] = Relationship(back_populates="user")

class PasswordReset(SQLModel, table=True):
    __tablename__ = "password_reset"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token: str = Field(index=True)
    expires_at: datetime
    user: Optional["User"] = Relationship(back_populates="password_resets")

class StudyGroup(SQLModel, table=True):
    __tablename__ = "study_group"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = Field(default=None)
    creator_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    creator: Optional["User"] = Relationship()
    members: List["User"] = Relationship(back_populates="study_groups", sa_relationship_kwargs={"secondary": "user_study_group"})
    messages: List["GroupMessage"] = Relationship(back_populates="group")
    group_boss_battles: List["GroupBossBattle"] = Relationship(back_populates="group")

class UserStudyGroup(SQLModel, table=True):
    __tablename__ = "user_study_group"
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="study_group.id", primary_key=True)

class GroupMessage(SQLModel, table=True):
    __tablename__ = "group_message"
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="study_group.id")
    user_id: int = Field(foreign_key="user.id")
    content: str = Field(sa_column=Column(Text))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    group: Optional["StudyGroup"] = Relationship(back_populates="messages")
    user: Optional["User"] = Relationship(back_populates="group_messages")

class Quest(SQLModel, table=True):
    __tablename__ = "quest"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    title: str
    description: Optional[str] = Field(default=None)
    quest_type: str
    difficulty: int
    reward_xp: int
    reward_skill_points: int
    is_completed: bool = Field(default=False)
    xp_earned: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    user: Optional["User"] = Relationship(back_populates="quests")

class BossBattle(SQLModel, table=True):
    __tablename__ = "boss_battle"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: str
    difficulty: int
    current_health: int
    max_health: int
    reward_xp: int
    reward_skill_points: int
    reward_items: Optional[str] = Field(default=None)
    is_completed: bool = Field(default=False)
    passed: Optional[bool] = Field(default=None)
    user: Optional["User"] = Relationship(back_populates="boss_battles")

class GroupBossBattle(SQLModel, table=True):
    __tablename__ = "group_boss_battle"
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="study_group.id")
    name: str
    difficulty: int
    current_health: int
    group_health: int
    score: int
    reward_xp: int
    reward_skill_points: int
    reward_items: Optional[str] = Field(default=None)
    is_completed: bool = Field(default=False)
    passed: Optional[bool] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    group: Optional["StudyGroup"] = Relationship(back_populates="group_boss_battles")
    users: List["User"] = Relationship(back_populates="group_boss_battles", sa_relationship_kwargs={"secondary": "user_group_boss_battle"})

class UserGroupBossBattle(SQLModel, table=True):
    __tablename__ = "user_group_boss_battle"
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_boss_battle_id: int = Field(foreign_key="group_boss_battle.id", primary_key=True)

class PomodoroSession(SQLModel, table=True):
    __tablename__ = "pomodoro_session"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    start_time: datetime
    duration: int
    is_completed: bool = Field(default=False)
    xp_earned: int = Field(default=0)
    end_time: Optional[datetime] = Field(default=None)
    user: Optional["User"] = Relationship(back_populates="pomodoro_sessions")

class Flashcard(SQLModel, table=True):
    __tablename__ = "flashcard"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    question: str
    answer: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="flashcards")

class UserFlashcard(SQLModel, table=True):
    __tablename__ = "user_flashcard"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    flashcard_id: int = Field(foreign_key="flashcard.id")
    proficiency: int
    user: Optional["User"] = Relationship(back_populates="user_flashcards")
    flashcard: Optional["Flashcard"] = Relationship()

class MemorySession(SQLModel, table=True):
    __tablename__ = "memory_session"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    start_time: datetime
    duration: int
    score: int
    sequence_length: int
    sequence: str = Field(sa_column=Column(String))
    is_completed: bool = Field(default=False)
    is_correct: Optional[bool] = Field(default=None)
    xp_earned: int = Field(default=0)
    end_time: Optional[datetime] = Field(default=None)
    user: Optional["User"] = Relationship(back_populates="memory_sessions")

class Skill(SQLModel, table=True):
    __tablename__ = "skill"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = Field(default=None)
    cost: int
    users: List["User"] = Relationship(back_populates="skills", sa_relationship_kwargs={"secondary": "user_skill"})
class UserSkill(SQLModel, table=True):
    __tablename__ = "user_skill"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    skill_id: int = Field(foreign_key="skill.id")
    acquired_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Add relationship to Skill
    skill: Optional["Skill"] = Relationship()
    
    # Add unique constraint
    __table_args__ = (UniqueConstraint('user_id', 'skill_id', name='user_skill_uc'),)


class UserItem(SQLModel, table=True):
    __tablename__ = "user_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    item_id: int = Field(foreign_key="item.id")
    is_used: bool = Field(default=False)
    used_at: Optional[datetime] = Field(default=None)
    # FIX: Add purchased_at field with current timestamp as default
    purchased_at: datetime = Field(default_factory=datetime.utcnow)

class Item(SQLModel, table=True):
    __tablename__ = "item"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: int
    description: Optional[str] = Field(default=None)
    users: List["User"] = Relationship(back_populates="items", sa_relationship_kwargs={"secondary": "user_item"})

class Material(SQLModel, table=True):
    __tablename__ = "material"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    content: str
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="materials")
    tests: List["Test"] = Relationship(back_populates="material")

class Test(SQLModel, table=True):
    __tablename__ = "test"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    material_id: int = Field(foreign_key="material.id")
    is_timed: bool
    duration: Optional[int] = Field(default=None)
    questions: str = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="tests")
    material: Optional["Material"] = Relationship(back_populates="tests")