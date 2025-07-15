from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime, timedelta

# Helper/link tables first
class GroupMember(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="studygroup.id", primary_key=True)
    role: str = Field(default="member")
    joined_at: datetime = Field(default_factory=datetime.utcnow)

class UserGroupBossBattle(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_boss_battle_id: int = Field(foreign_key="groupbossbattle.id", primary_key=True)
    joined_at: datetime = Field(default_factory=datetime.utcnow)

class UserSkill(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    skill_id: int = Field(foreign_key="skill.id", primary_key=True)
    unlocked_at: datetime = Field(default_factory=datetime.utcnow)

# Independent models next
class Skill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    users: List["User"] = Relationship(back_populates="skills", link_model=UserSkill)

class Flashcard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deck_id: int = Field(foreign_key="flashcarddeck.id")
    question: str
    answer: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deck: Optional["FlashcardDeck"] = Relationship(back_populates="flashcards")

class FlashcardDeck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: str = Field(index=True)
    topic: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="flashcard_decks")
    flashcards: List["Flashcard"] = Relationship(back_populates="deck")

# User-related models
class UserAnalytics(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    metric: str
    value: float
    date: datetime
    user: Optional["User"] = Relationship(back_populates="analytics")

class MemoryTrainingSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    content: str
    score: int
    is_ai_generated: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="memory_trainings")

class PomodoroSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    start_time: datetime
    duration: int
    completed: bool = Field(default=False)
    user: Optional["User"] = Relationship(back_populates="pomodoro_sessions")

class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: str = Field(index=True)
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    user: Optional["User"] = Relationship(back_populates="items")

class PasswordReset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))

class Quest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    title: str
    description: str
    quest_type: Optional[str] = None
    xp_reward: int
    completed: bool = Field(default=False)
    recurring: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="quests")

class BossBattle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    title: str
    description: Optional[str] = None
    difficulty: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    score: Optional[int] = None
    passed: bool = Field(default=False)
    current_health: Optional[int] = None
    max_health: Optional[int] = None
    is_active: bool = Field(default=True)
    is_completed: bool = Field(default=False)
    reward_xp: Optional[int] = None
    reward_items: Optional[str] = None
    user: Optional["User"] = Relationship(back_populates="boss_battles")

# Study Group related models
class GroupMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    group_id: int = Field(foreign_key="studygroup.id")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="messages")
    group: Optional["StudyGroup"] = Relationship(back_populates="messages")

class GroupQuest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="studygroup.id")
    user_id: int = Field(foreign_key="user.id")
    title: str
    description: Optional[str] = None
    xp_reward: int
    completed: bool = Field(default=False)
    user: Optional["User"] = Relationship(back_populates="group_quests")
    group: Optional["StudyGroup"] = Relationship(back_populates="group_quests")

class GroupBossBattle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="studygroup.id")
    title: str
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    current_health: int
    max_health: int
    group_health: int
    score: int
    phase: int = Field(default=1)
    is_active: bool = Field(default=True)
    is_completed: bool = Field(default=False)
    passed: bool = Field(default=False)
    reward_xp: int
    reward_skill_points: int
    reward_items: Optional[str] = None
    participants: List["User"] = Relationship(
        back_populates="participated_boss_battles", 
        link_model=UserGroupBossBattle
    )
    group: Optional["StudyGroup"] = Relationship(back_populates="group_boss_battles")

class StudyGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, index=True)
    description: Optional[str] = Field(max_length=200)
    is_public: bool = Field(default=True)
    max_members: int = Field(default=10)
    creator_id: int = Field(foreign_key="user.id")
    current_members: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    members: List["User"] = Relationship(
        back_populates="groups", 
        link_model=GroupMember
    )
    group_quests: List["GroupQuest"] = Relationship(back_populates="group")
    group_boss_battles: List["GroupBossBattle"] = Relationship(back_populates="group")
    messages: List["GroupMessage"] = Relationship(back_populates="group")

# Course materials
class CourseMaterial(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="materials")
    test_attempts: List["MaterialTestAttempt"] = Relationship(back_populates="material")

class MaterialTestAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    material_id: int = Field(foreign_key="coursematerial.id")
    test_type: str
    time_limit: Optional[int] = None
    time_remaining: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: Optional[int] = None
    responses: Optional[str] = None
    generated_questions: Optional[str] = None
    user: Optional["User"] = Relationship(back_populates="test_attempts")
    material: Optional["CourseMaterial"] = Relationship(back_populates="test_attempts")

# Main User model
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    avatar_url: Optional[str] = None
    interests: Optional[str] = None
    xp: int = Field(default=0)
    level: int = Field(default=1)
    skill_points: int = Field(default=0)
    memory: int = Field(default=0)
    focus: int = Field(default=0)
    comprehension: int = Field(default=0)
    speed: int = Field(default=0)
    streak: int = Field(default=0)
    last_login: Optional[datetime] = None
    is_verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    analytics: List["UserAnalytics"] = Relationship(back_populates="user")
    memory_trainings: List["MemoryTrainingSession"] = Relationship(back_populates="user")
    pomodoro_sessions: List["PomodoroSession"] = Relationship(back_populates="user")
    quests: List["Quest"] = Relationship(back_populates="user")
    boss_battles: List["BossBattle"] = Relationship(back_populates="user")
    group_quests: List["GroupQuest"] = Relationship(back_populates="user")
    participated_boss_battles: List["GroupBossBattle"] = Relationship(
        back_populates="participants", 
        link_model=UserGroupBossBattle
    )
    materials: List["CourseMaterial"] = Relationship(back_populates="user")
    test_attempts: List["MaterialTestAttempt"] = Relationship(back_populates="user")
    flashcard_decks: List["FlashcardDeck"] = Relationship(back_populates="user")
    groups: List["StudyGroup"] = Relationship(
        back_populates="members", 
        link_model=GroupMember
    )
    skills: List["Skill"] = Relationship(
        back_populates="users", 
        link_model=UserSkill
    )
    items: List["Item"] = Relationship(back_populates="user")
    messages: List["GroupMessage"] = Relationship(back_populates="user")

# Resolve forward references at the end
User.model_rebuild()
StudyGroup.model_rebuild()
GroupBossBattle.model_rebuild()
Skill.model_rebuild()
FlashcardDeck.model_rebuild()