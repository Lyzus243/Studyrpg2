from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal

# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: Optional[str] = Field(default="user")  # Allow role specification during creation

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None

class UserRead(UserBase):
    id: int
    is_verified: bool
    xp: int = Field(alias="xp")  # Match admin's experience_points field
    skill_points: int
    streak: int
    avatar_url: Optional[str]
    level: int
    currency: int
    last_active: Optional[datetime]
    role: str  # Include role for admin functionality
    is_active: bool  # Include is_active for admin functionality
    is_banned: bool  # Include is_banned for admin functionality

    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both 'xp' and 'experience_points'

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class RefreshToken(BaseModel):
    refresh_token: str

# Password Reset Schemas
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class PasswordReset(BaseModel):
    password: str = Field(..., min_length=8)

# Study Group Schemas
class StudyGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class StudyGroupCreate(StudyGroupBase):
    pass

class StudyGroupRead(StudyGroupBase):
    id: int
    creator_id: int
    created_at: datetime
    members: List[UserRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

# Group Message Schemas
class GroupMessageBase(BaseModel):
    content: str = Field(..., min_length=1)

class GroupMessageCreate(GroupMessageBase):
    pass

class GroupMessageRead(GroupMessageBase):
    id: int
    group_id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# ===========================
# SHOP ITEM SCHEMAS
# ===========================
class ShopItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float

class ShopItemCreate(ShopItemBase):
    pass

class ShopItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None

class ShopItemRead(ShopItemBase):
    id: int

    class Config:
        from_attributes = True

# ===========================
# QUEST SCHEMAS
# ===========================
class QuestBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    quest_type: str = Field(..., min_length=1, max_length=50)
    difficulty: int = Field(..., ge=1, le=10)
    reward_xp: int = Field(..., ge=0)
    reward_skill_points: int = Field(..., ge=0)

class QuestCreate(QuestBase):
    user_id: Optional[int] = None  # Allow admin to create quests without specific user

class QuestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    quest_type: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=10)
    reward_xp: Optional[int] = Field(None, ge=0)
    reward_skill_points: Optional[int] = Field(None, ge=0)
    is_completed: Optional[bool] = None

class QuestRead(QuestBase):
    id: int
    user_id: Optional[int]
    is_completed: bool
    xp_earned: int
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

# ===========================
# BOSS BATTLE SCHEMAS
# ===========================
class BossBattleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    difficulty: int = Field(..., ge=1, le=10)
    current_health: int = Field(..., ge=0)
    max_health: int = Field(..., ge=1)
    health: int = Field(..., ge=0)  # Admin uses 'health' field
    reward_xp: int = Field(..., ge=0)
    reward_skill_points: int = Field(..., ge=0)
    reward_items: Optional[str] = None

class BossBattleCreate(BossBattleBase):
    user_id: Optional[int] = None  # Allow admin to create boss battles without specific user

class BossBattleUpdate(BaseModel):
    name: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=10)
    current_health: Optional[int] = Field(None, ge=0)
    max_health: Optional[int] = Field(None, ge=1)
    health: Optional[int] = Field(None, ge=0)
    reward_xp: Optional[int] = Field(None, ge=0)
    reward_skill_points: Optional[int] = Field(None, ge=0)
    reward_items: Optional[str] = None
    is_active: Optional[bool] = None

class BossBattleRead(BossBattleBase):
    id: int
    user_id: Optional[int]
    is_completed: bool
    is_active: bool
    passed: Optional[bool]

    class Config:
        from_attributes = True

# Group Boss Battle Schemas
class BossAttack(BaseModel):
    damage: int = Field(..., ge=1)

class GroupBossBattleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    difficulty: int = Field(..., ge=1, le=10)
    current_health: int = Field(..., ge=0)
    group_health: int = Field(..., ge=1)
    score: int = Field(..., ge=0)
    reward_xp: int = Field(..., ge=0)
    reward_skill_points: int = Field(..., ge=0)
    reward_items: Optional[str] = None

class GroupBossBattleCreate(GroupBossBattleBase):
    group_id: int

class GroupBossBattleRead(GroupBossBattleBase):
    id: int
    group_id: int
    is_completed: bool
    passed: Optional[bool]
    created_at: datetime
    users: List[UserRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

# ===========================
# ADMIN-SPECIFIC SCHEMAS
# ===========================
class UserRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(user|admin|moderator)$")

class XPUpdate(BaseModel):
    xp: int = Field(..., description="XP points to add (can be negative)")

class BroadcastMessage(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)

class AdminStats(BaseModel):
    users: int
    quests: int
    shop_items: int
    boss_battles: int

# Pomodoro Session Schemas
class PomodoroSessionBase(BaseModel):
    duration: int = Field(..., ge=1, le=120)

class PomodoroSessionCreate(PomodoroSessionBase):
    pass

class PomodoroSessionRead(PomodoroSessionBase):
    id: int
    user_id: int
    start_time: datetime
    is_completed: bool
    xp_earned: int
    end_time: Optional[datetime]

    class Config:
        from_attributes = True

class PomodoroStats(BaseModel):
    total_sessions: int
    total_duration: int
    average_duration: Decimal
    total_xp_earned: int

# Flashcard Schemas
class FlashcardBase(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)

class FlashcardCreate(FlashcardBase):
    pass

class FlashcardRead(FlashcardBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# User Flashcard Schemas
class UserFlashcardBase(BaseModel):
    proficiency: int = Field(..., ge=0, le=100)

class UserFlashcardCreate(UserFlashcardBase):
    flashcard_id: int

class UserFlashcardUpdate(BaseModel):
    proficiency: Optional[int] = Field(None, ge=0, le=100)

class UserFlashcardRead(UserFlashcardBase):
    id: int
    user_id: int
    flashcard_id: int
    flashcard: Optional[FlashcardRead] = None

    class Config:
        from_attributes = True

# Memory Session Schemas
class MemorySessionBase(BaseModel):
    sequence_length: int = Field(..., ge=1, le=20)

class MemorySessionCreate(MemorySessionBase):
    pass

class MemorySessionSubmission(BaseModel):
    user_sequence: List[int]

class MemorySessionRead(MemorySessionBase):
    id: int
    user_id: int
    start_time: datetime
    duration: int
    score: int
    sequence: str
    is_completed: bool
    is_correct: Optional[bool]
    xp_earned: int
    end_time: Optional[datetime]

    class Config:
        from_attributes = True

# Skill Schemas
class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    cost: int = Field(..., ge=0)

class SkillCreate(SkillBase):
    pass

class SkillRead(SkillBase):
    id: int

    class Config:
        from_attributes = True

# Item Schemas
class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: int = Field(..., ge=0)
    description: Optional[str] = None

class ItemCreate(ItemBase):
    pass

class ItemRead(ItemBase):
    id: int

    class Config:
        from_attributes = True

# User Item Schemas
class UserItemBase(BaseModel):
    is_used: bool = False
    used_at: Optional[datetime] = None

class UserItemCreate(BaseModel):
    item_id: int

class UserItemRead(UserItemBase):
    id: int
    user_id: int
    item_id: int
    item: Optional[ItemRead] = None
    purchased_at: datetime

    class Config:
        from_attributes = True

# Purchase Schemas
class PurchaseCreate(BaseModel):
    item_id: int = Field(..., ge=1)

# Analytics Schemas
class AnalyticsTimeRange(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    compare: Optional[bool] = False

class UserAnalyticsResponse(BaseModel):
    start_date: date
    end_date: date
    compare: Optional[bool]
    total_pomodoro_sessions: int
    total_pomodoro_minutes: int
    total_quests_completed: int
    total_xp_earned: int
    average_pomodoro_duration: Optional[float]

    class Config:
        from_attributes = True

# AI Test Generation Schemas
class TestGenerationRequest(BaseModel):
    material_id: int
    duration: int = Field(..., ge=1, le=180)  # Duration in minutes
    
class UserSkillRead(BaseModel):
    id: int
    user_id: int
    skill_id: int
    acquired_at: datetime
    skill: SkillRead

    class Config:
        from_attributes = True

# Material Schemas
class MaterialBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)

class MaterialCreate(MaterialBase):
    pass

class MaterialRead(MaterialBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Test Schemas
class TestBase(BaseModel):
    is_timed: bool
    duration: Optional[int] = Field(None, ge=1, le=300)
    questions: Optional[Dict[str, Any]] = None

class TestCreate(TestBase):
    material_id: int

class TestRead(TestBase):
    id: int
    user_id: int
    material_id: int
    created_at: datetime

    class Config:
        from_attributes = True
