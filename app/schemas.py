from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime, date
from enum import Enum

class GroupRole(str, Enum):
    member = "member"
    admin = "admin"
    creator = "creator"

# Authentication models
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# User models
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    avatar_url: Optional[str] = None
    interests: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserRead(UserBase):
    id: int
    xp: int = Field(..., ge=0)
    level: int = Field(..., ge=1)
    skill_points: int = Field(..., ge=0)
    streak: int = Field(..., ge=0)
    last_login: Optional[datetime]
    is_verified: bool
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    interests: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    class Config:
        from_attributes = True

# Analytics models
class AnalyticsTimeRange(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    compare: Optional[bool] = False
    class Config:
        from_attributes = True

class UserAnalyticsResponse(BaseModel):
    start_date: date
    end_date: date
    compare: bool = False
    daily_xp: Dict[str, float]
    efficiency: float
    nba_style: Dict[str, float]
    class Config:
        from_attributes = True

# StudyGroup models
class StudyGroupBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    is_public: bool = True
    max_members: int = Field(default=10, ge=2, le=50)

    @validator('name')
    def name_no_special_chars(cls, v):
        if not all(char.isalnum() or char.isspace() for char in v):
            raise ValueError("Group name can only contain letters, numbers, and spaces")
        return v

class StudyGroupCreate(StudyGroupBase):
    pass

class StudyGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    is_public: Optional[bool] = None
    max_members: Optional[int] = Field(None, ge=2, le=50)

class StudyGroupRead(StudyGroupBase):
    id: int
    created_at: datetime
    creator_id: int
    current_members: int
    members: List[UserRead] = []
    unread_count: Optional[int] = 0
    class Config:
        from_attributes = True

# GroupMember models
class GroupMemberBase(BaseModel):
    user_id: int
    group_id: int
    role: GroupRole = GroupRole.member

class GroupMemberCreate(GroupMemberBase):
    pass

class GroupMemberUpdate(BaseModel):
    role: Optional[GroupRole] = None

class GroupMemberRead(GroupMemberBase):
    joined_at: datetime
    user: UserRead
    class Config:
        from_attributes = True

# Other models
class GroupInviteCreate(BaseModel):
    email: str
    message: Optional[str] = Field(None, max_length=100)

class TestGenerationRequest(BaseModel):
    material_id: int
    duration: int = 30

class TestQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: int
    explanation: Optional[str] = None

class TestAttemptBase(BaseModel):
    test_type: str
    time_limit: Optional[int] = None

class TestAttemptCreate(TestAttemptBase):
    material_id: int
    user_id: int

class TestAttempt(TestAttemptBase):
    id: int
    user_id: int
    material_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    is_completed: bool = False
    score: Optional[int] = None
    responses: Optional[Dict] = None
    class Config:
        from_attributes = True

class CourseMaterialBase(BaseModel):
    title: str
    content: str

class CourseMaterialCreate(CourseMaterialBase):
    pass

class CourseMaterial(CourseMaterialBase):
    id: int
    user_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class QuestBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    xp_reward: int = Field(..., ge=0)
    quest_type: Optional[str] = None
    recurring: bool = False

class QuestCreate(QuestBase):
    pass

class QuestUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    xp_reward: Optional[int] = Field(None, ge=0)
    quest_type: Optional[str] = None
    recurring: Optional[bool] = None

class QuestRead(QuestBase):
    id: int
    user_id: int
    completed: bool
    created_at: datetime
    class Config:
        from_attributes = True

class GroupBossBattleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    max_health: int = Field(..., ge=1)
    group_health: int = Field(..., ge=0)
    reward_xp: int = Field(..., ge=0)
    reward_skill_points: int = Field(..., ge=0)
    reward_items: Optional[str] = None

class GroupBossBattleCreate(GroupBossBattleBase):
    group_id: int
    created_by: int

class GroupBossBattleUpdate(BaseModel):
    current_health: Optional[int] = Field(None, ge=0)
    group_health: Optional[int] = Field(None, ge=0)
    score: Optional[int] = Field(None, ge=0)
    is_completed: Optional[bool] = None
    passed: Optional[bool] = None
    phase: Optional[int] = Field(None, ge=1)

class GroupBossBattleRead(GroupBossBattleBase):
    id: int
    group_id: int
    created_by: int
    current_health: int
    score: int
    phase: int
    is_active: bool
    is_completed: bool
    passed: bool
    created_at: datetime
    participants_rel: List[UserRead] = []
    class Config:
        from_attributes = True

class GroupSearchParams(BaseModel):
    name: Optional[str] = None
    is_public: Optional[bool] = None
    min_members: Optional[int] = Field(None, ge=0)
    max_members: Optional[int] = Field(None, ge=1)
    created_after: Optional[datetime] = None

class GroupStats(BaseModel):
    total_members: int
    active_members: int
    quests_completed: int
    average_xp_earned: float

class TestRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    is_custom: bool = False
    creator_id: Optional[int] = None
    time_limit: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True

class TestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    is_custom: bool = False
    creator_id: Optional[int] = None
    time_limit: Optional[int] = None
    material_id: int

class TestResult(BaseModel):
    attempt_id: int
    score: float
    max_score: float
    passed: bool
    details: Optional[List[dict]] = None
    class Config:
        from_attributes = True

class TestResponseItem(BaseModel):
    question_id: int
    answer: Any

class TestResponses(BaseModel):
    responses: List[TestResponseItem]

class BossBattleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    difficulty: str
    reward_xp: int = Field(..., ge=0)
    reward_items: Optional[List[str]] = None

class BossBattleCreate(BossBattleBase):
    user_id: int
    max_health: int = Field(..., ge=1)

class BossBattleRead(BossBattleBase):
    id: int
    user_id: int
    current_health: Optional[int] = Field(None, ge=0)
    max_health: Optional[int] = Field(None, ge=1)
    is_active: bool
    is_completed: bool
    passed: bool
    created_at: datetime
    score: Optional[int] = Field(None, ge=0)
    class Config:
        from_attributes = True

class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)

class SkillRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_unlocked: bool
    class Config:
        from_attributes = True

class ExportFormat(BaseModel):
    format: Literal["csv", "json", "pdf"] = "csv"

class FlashcardDeckBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    topic: str = Field(..., min_length=1, max_length=100)

class FlashcardDeckCreate(FlashcardDeckBase):
    user_id: int

class FlashcardDeckRead(FlashcardDeckBase):
    id: int
    user_id: int
    created_at: datetime
    flashcards: List["FlashcardRead"] = []
    class Config:
        from_attributes = True

class FlashcardBase(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=500)

class FlashcardCreate(FlashcardBase):
    deck_id: int

class FlashcardRead(FlashcardBase):
    id: int
    deck_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class UserFlashcardCreate(FlashcardBase):
    deck_id: int

class FlashcardProgressRead(BaseModel):
    flashcard_id: int
    user_id: int
    correct_count: int = Field(..., ge=0)
    total_attempts: int = Field(..., ge=0)
    last_reviewed: Optional[datetime] = None
    class Config:
        from_attributes = True

class MemoryTrainingSessionBase(BaseModel):
    content: str = Field(..., min_length=1)
    score: int = Field(..., ge=0)
    is_ai_generated: bool = False

class MemoryTrainingSessionCreate(MemoryTrainingSessionBase):
    user_id: int

class MemoryTrainingSessionRead(MemoryTrainingSessionBase):
    id: int
    user_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class PomodoroSessionBase(BaseModel):
    start_time: datetime
    duration: int = Field(..., ge=1)
    completed: bool = False

class PomodoroSessionCreate(PomodoroSessionBase):
    user_id: int

class PomodoroSessionRead(PomodoroSessionBase):
    id: int
    user_id: int
    class Config:
        from_attributes = True

class GroupMessageBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    user_id: int
    group_id: int

class GroupMessageCreate(GroupMessageBase):
    pass

class GroupMessageRead(GroupMessageBase):
    id: int
    timestamp: datetime
    user: UserRead
    class Config:
        from_attributes = True

# Resolve forward refs
FlashcardDeckRead.update_forward_refs()
GroupMessageRead.update_forward_refs()