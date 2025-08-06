from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import User, QuestCompletion

REQUIRED_XP = 300
REQUIRED_QUESTS = 5
REQUIRED_STREAK = 5

async def is_user_eligible_for_group(user: User, db: AsyncSession) -> bool:
    if user.xp < REQUIRED_XP or user.streak < REQUIRED_STREAK:
        return False

    # Count quests completed by the user
    result = await db.execute(
        select(func.count()).select_from(QuestCompletion).where(QuestCompletion.user_id == user.id)
    )
    completed_quests = result.scalar_one() or 0

    return completed_quests >= REQUIRED_QUESTS
