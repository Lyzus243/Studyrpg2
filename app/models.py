from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Float, Text, JSON, UniqueConstraint, Integer
)
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column

Base = declarative_base()

# --------------------------
# Association Models
# --------------------------


class UserActivity(Base):
    __tablename__ = "user_activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="activities")

class UserStudyGroup(Base):
    __tablename__ = "user_study_group"
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("study_group.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="group_links")
    group: Mapped["StudyGroup"] = relationship(back_populates="user_links")


class UserSkill(Base):
    __tablename__ = "user_skill"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skill.id"))
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="user_skill_uc"),)

    user: Mapped["User"] = relationship(back_populates="skill_links")
    skill: Mapped["Skill"] = relationship(back_populates="user_links")


class UserItem(Base):
    __tablename__ = "user_item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="item_links")
    item: Mapped["Item"] = relationship(back_populates="user_links")


class UserGroupBossBattle(Base):
    __tablename__ = "user_group_boss_battle"
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    group_boss_battle_id: Mapped[int] = mapped_column(ForeignKey("group_boss_battle.id"), primary_key=True)

    user: Mapped["User"] = relationship(back_populates="group_boss_battle_links")
    group_boss_battle: Mapped["GroupBossBattle"] = relationship(back_populates="user_links")


class GroupQuest(Base):
    __tablename__ = "group_quest"
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quest.id"), primary_key=True)

# --------------------------
# Core Models
# --------------------------

class Material(Base):
    __tablename__ = "material"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    user: Mapped["User"] = relationship("User", back_populates="materials")
    tests: Mapped[List["Test"]] = relationship(back_populates="material")  # Added tests relationship

class ShopItem(Base):
    __tablename__ = "shop_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float, nullable=False)


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)

    members: Mapped[List["User"]] = relationship(back_populates="group")


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String)
    verification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    skill_points: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    currency: Mapped[int] = mapped_column(Integer, default=100)

    avatar_url: Mapped[Optional[str]] = mapped_column(String)
    last_active: Mapped[Optional[datetime]] = mapped_column(DateTime)
    role: Mapped[str] = mapped_column(String, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)

    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id"))
    group: Mapped[Optional["Group"]] = relationship(back_populates="members")

    password_resets: Mapped[List["PasswordReset"]] = relationship(back_populates="user")
    pomodoro_sessions: Mapped[List["PomodoroSession"]] = relationship(back_populates="user")
    quests: Mapped[List["Quest"]] = relationship(back_populates="user")
    boss_battles: Mapped[List["BossBattle"]] = relationship(back_populates="user")
    group_messages: Mapped[List["GroupMessage"]] = relationship(back_populates="user")
    flashcards: Mapped[List["Flashcard"]] = relationship(back_populates="user")
    user_flashcards: Mapped[List["UserFlashcard"]] = relationship(back_populates="user")
    memory_sessions: Mapped[List["MemorySession"]] = relationship(back_populates="user")
    materials: Mapped[List["Material"]] = relationship("Material", back_populates="user")  # Uncommented and fixed
    tests: Mapped[List["Test"]] = relationship(back_populates="user")

    group_links: Mapped[List["UserStudyGroup"]] = relationship(back_populates="user")
    study_groups: Mapped[List["StudyGroup"]] = relationship(secondary="user_study_group", back_populates="members")

    skill_links: Mapped[List["UserSkill"]] = relationship(back_populates="user")
    skills: Mapped[List["Skill"]] = relationship(secondary="user_skill", back_populates="users")
    activities: Mapped[List["UserActivity"]] = relationship(back_populates="user")
    item_links: Mapped[List["UserItem"]] = relationship(back_populates="user")
    items: Mapped[List["Item"]] = relationship(secondary="user_item", back_populates="users")
    # Add to User model in models.py
    group_boss_battle_links: Mapped[List["UserGroupBossBattle"]] = relationship(back_populates="user")
    group_boss_battles: Mapped[List["GroupBossBattle"]] = relationship(secondary="user_group_boss_battle", back_populates="users")


class PasswordReset(Base):
    __tablename__ = "password_reset"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    token: Mapped[str] = mapped_column(String, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship(back_populates="password_resets")


class StudyGroup(Base):
    __tablename__ = "study_group"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    creator_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator: Mapped["User"] = relationship()
    messages: Mapped[List["GroupMessage"]] = relationship(back_populates="group")
    group_boss_battles: Mapped[List["GroupBossBattle"]] = relationship(back_populates="group")
    user_links: Mapped[List["UserStudyGroup"]] = relationship(back_populates="group")
    members: Mapped[List["User"]] = relationship(secondary="user_study_group", back_populates="study_groups")


class GroupMessage(Base):
    __tablename__ = "group_message"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("study_group.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped["StudyGroup"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="group_messages")


class Quest(Base):
    __tablename__ = "quest"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    quest_type: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_skill_points: Mapped[int] = mapped_column(Integer, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="quests")
    groups: Mapped[List["Group"]] = relationship(secondary="group_quest")


class BossBattle(Base):
    __tablename__ = "boss_battle"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    current_health: Mapped[int] = mapped_column(Integer, nullable=False)
    max_health: Mapped[int] = mapped_column(Integer, nullable=False)
    health: Mapped[int] = mapped_column(Integer, default=100)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_skill_points: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_items: Mapped[Optional[str]] = mapped_column(String)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)

    user: Mapped["User"] = relationship(back_populates="boss_battles")

class GroupBossBattle(Base):
    __tablename__ = "group_boss_battle"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("study_group.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    current_health: Mapped[int] = mapped_column(Integer, nullable=False)
    group_health: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_skill_points: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_items: Mapped[Optional[str]] = mapped_column(String)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped["StudyGroup"] = relationship(back_populates="group_boss_battles")
    user_links: Mapped[List["UserGroupBossBattle"]] = relationship(back_populates="group_boss_battle")
    users: Mapped[List["User"]] = relationship(secondary="user_group_boss_battle", back_populates="group_boss_battles")


class PomodoroSession(Base):
    __tablename__ = "pomodoro_session"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="pomodoro_sessions")


class Flashcard(Base):
    __tablename__ = "flashcard"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    question: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="flashcards")


class UserFlashcard(Base):
    __tablename__ = "user_flashcard"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    flashcard_id: Mapped[int] = mapped_column(ForeignKey("flashcard.id"))
    proficiency: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped["User"] = relationship(back_populates="user_flashcards")
    flashcard: Mapped["Flashcard"] = relationship()


class MemorySession(Base):
    __tablename__ = "memory_session"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_length: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="memory_sessions")


class Skill(Base):
    __tablename__ = "skill"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)

    user_links: Mapped[List["UserSkill"]] = relationship(back_populates="skill")
    users: Mapped[List["User"]] = relationship(secondary="user_skill", back_populates="skills")


class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)

    user_links: Mapped[List["UserItem"]] = relationship(back_populates="item")
    users: Mapped[List["User"]] = relationship(secondary="user_item", back_populates="items")

class Test(Base):
    __tablename__ = "test"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"))
    is_timed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration: Mapped[Optional[int]] = mapped_column(Integer)
    questions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="tests")
    material: Mapped["Material"] = relationship(back_populates="tests")  # Fixed back_populates


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    date_earned: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Inventory(Base):
    __tablename__ = "inventory"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class Event(Base):
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


