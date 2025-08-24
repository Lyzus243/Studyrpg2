from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.database import get_async_session
from app.models import User, ShopItem, Quest, Group, BossBattle
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy import func
from app.routers.auth import get_current_user, get_password_hash
from app.email_utils import send_broadcast_email
import os
import logging

logger = logging.getLogger(__name__)

# Use prefix for all admin routes
router = APIRouter(prefix="", tags=["admin"])

# Local Schema definitions
class ShopItemCreate(BaseModel):
    name: str
    description: str
    price: int
    item_type: str
    effect: Optional[str] = None
    image_url: Optional[str] = None

class ShopItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    item_type: Optional[str] = None
    effect: Optional[str] = None
    image_url: Optional[str] = None

class QuestCreate(BaseModel):
    title: str
    description: str
    reward_xp: int
    difficulty: str
    duration_minutes: int

class QuestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reward_xp: Optional[int] = None
    difficulty: Optional[str] = None
    duration_minutes: Optional[int] = None

class UserRoleUpdate(BaseModel):
    role: str

class XPUpdate(BaseModel):
    xp: int

class PasswordReset(BaseModel):
    password: str

class BossBattleCreate(BaseModel):
    name: str
    description: str
    health: int
    difficulty: str = "medium"
    image_url: Optional[str] = None
    is_active: bool = False

class BossBattleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    health: Optional[int] = None
    difficulty: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

# Feedback schemas
class FeedbackBase(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    category: str
    message: str

class FeedbackCreate(FeedbackBase):
    pass

class FeedbackUpdate(BaseModel):
    resolved: Optional[bool] = None

def require_admin(user: User):
    """Role-based admin check (no hard-coded username)"""
    if not user or getattr(user, "role", "user") not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Admin access only")

# =========================================================
# SHOP MANAGEMENT
# =========================================================
@router.get("/shop")
async def get_shop_items(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(ShopItem))
    return result.scalars().all()

@router.post("/shop", response_model=ShopItemCreate)
async def add_shop_item(
    item: ShopItemCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    shop_item = ShopItem(**item.dict())
    db.add(shop_item)
    await db.commit()
    await db.refresh(shop_item)
    return shop_item

@router.put("/shop/{item_id}")
async def update_shop_item(
    item_id: int,
    item: ShopItemUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(ShopItem).where(ShopItem.id == item_id))
    shop_item = result.scalar_one_or_none()
    if not shop_item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in item.dict(exclude_unset=True).items():
        setattr(shop_item, key, value)
    await db.commit()
    await db.refresh(shop_item)
    return shop_item

@router.delete("/shop/{item_id}")
async def delete_shop_item(
    item_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(ShopItem).where(ShopItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()
    return {"detail": "Item deleted"}

# =========================================================
# QUEST MANAGEMENT
# =========================================================
@router.get("/quests")
async def get_quests(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(Quest))
    return result.scalars().all()

@router.post("/quests", response_model=QuestCreate)
async def create_quest(
    quest: QuestCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    quest_obj = Quest(**quest.dict())
    db.add(quest_obj)
    await db.commit()
    await db.refresh(quest_obj)
    return quest_obj

@router.put("/quests/{quest_id}")
async def update_quest(
    quest_id: int,
    quest: QuestUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(Quest).where(Quest.id == quest_id))
    quest_obj = result.scalar_one_or_none()
    if not quest_obj:
        raise HTTPException(status_code=404, detail="Quest not found")
    for key, value in quest.dict(exclude_unset=True).items():
        setattr(quest_obj, key, value)
    await db.commit()
    await db.refresh(quest_obj)
    return quest_obj

@router.delete("/quests/{quest_id}")
async def delete_quest(
    quest_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    await db.delete(quest)
    await db.commit()
    return {"detail": "Quest deleted"}

@router.post("/quests/{quest_id}/assign/{group_id}")
async def assign_quest_to_group(
    quest_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    quest_result = await db.execute(select(Quest).where(Quest.id == quest_id).options(selectinload(Quest.groups)))
    quest_obj = quest_result.scalar_one_or_none()
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group = group_result.scalar_one_or_none()
    
    if not quest_obj or not group:
        raise HTTPException(status_code=404, detail="Quest or group not found")
    
    # Add group to quest's groups
    quest_obj.groups.append(group)
    await db.commit()
    return {"detail": f"Quest '{quest_obj.title}' assigned to group '{group.name}'"}

# =========================================================
# USER MANAGEMENT
# =========================================================
@router.get("/users")
async def get_users(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(User))
    return result.scalars().all()

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role_update.role
    await db.commit()
    return {"detail": f"User role updated to {role_update.role}"}

@router.put("/users/{user_id}/xp")
async def update_user_xp(
    user_id: int,
    xp_update: XPUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.xp += xp_update.xp
    await db.commit()
    return {"detail": f"User XP updated by {xp_update.xp} points"}

@router.put("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = True
    await db.commit()
    return {"detail": "User banned"}

@router.put("/users/{user_id}/unban")
async def unban_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = False
    await db.commit()
    return {"detail": "User unbanned"}

@router.put("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    new_password: PasswordReset,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = get_password_hash(new_password.password)
    await db.commit()
    return {"detail": "Password reset successful"}

# =========================================================
# GROUP MANAGEMENT
# =========================================================
@router.get("/groups")
async def get_groups(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(
        select(Group).options(
            selectinload(Group.members),
            selectinload(Group.quests)
        )
    )
    return result.scalars().all()

@router.put("/groups/{group_id}/approve/{user_id}")
async def approve_group_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    group_result = await db.execute(select(Group).where(Group.id == group_id).options(selectinload(Group.members)))
    group = group_result.scalar_one_or_none()
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not group or not user:
        raise HTTPException(status_code=404, detail="Group or user not found")
    group.members.append(user)
    await db.commit()
    return {"detail": "User approved and added to group"}

@router.put("/groups/{group_id}/remove/{user_id}")
async def remove_group_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    group_result = await db.execute(select(Group).where(Group.id == group_id).options(selectinload(Group.members)))
    group = group_result.scalar_one_or_none()
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not group or not user:
        raise HTTPException(status_code=404, detail="Group or user not found")
    if user in group.members:
        group.members.remove(user)
        await db.commit()
    return {"detail": "User removed from group"}

# =========================================================
# BOSS BATTLE MANAGEMENT
# =========================================================
@router.get("/boss-battles")
async def get_boss_battles(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(BossBattle))
    return result.scalars().all()

@router.post("/boss-battles")
async def create_boss_battle(
    boss_battle: BossBattleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    boss_obj = BossBattle(**boss_battle.dict())
    db.add(boss_obj)
    await db.commit()
    await db.refresh(boss_obj)
    return boss_obj

@router.put("/boss-battles/{boss_id}")
async def update_boss_battle(
    boss_id: int,
    boss_battle: BossBattleUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(BossBattle).where(BossBattle.id == boss_id))
    boss_obj = result.scalar_one_or_none()
    if not boss_obj:
        raise HTTPException(status_code=404, detail="Boss battle not found")
    for key, value in boss_battle.dict(exclude_unset=True).items():
        setattr(boss_obj, key, value)
    await db.commit()
    await db.refresh(boss_obj)
    return boss_obj

@router.delete("/boss-battles/{boss_id}")
async def delete_boss_battle(
    boss_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(BossBattle).where(BossBattle.id == boss_id))
    boss = result.scalar_one_or_none()
    if not boss:
        raise HTTPException(status_code=404, detail="Boss battle not found")
    await db.delete(boss)
    await db.commit()
    return {"detail": "Boss battle deleted"}

@router.post("/boss-battles/{boss_id}/activate")
async def activate_boss_battle(
    boss_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    result = await db.execute(select(BossBattle).where(BossBattle.id == boss_id))
    boss = result.scalar_one_or_none()
    if not boss:
        raise HTTPException(status_code=404, detail="Boss battle not found")
    
    # Deactivate all other boss battles
    active_bosses = await db.execute(select(BossBattle).where(BossBattle.is_active == True))
    for active_boss in active_bosses.scalars():
        active_boss.is_active = False
    
    # Activate the selected boss
    boss.is_active = True
    await db.commit()
    return {"detail": f"Boss battle '{boss.name}' activated"}

# =========================================================
# BROADCAST MANAGEMENT
# =========================================================
@router.post("/broadcast")
async def broadcast_message(
    data: dict,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    subject = data.get("subject")
    message = data.get("message")
    
    if not subject or not message:
        raise HTTPException(status_code=400, detail="Subject and message are required")
    
    # Get all active users emails (exclude banned users)
    try:
        result = await db.execute(
            select(User.email, User.username)
            .where(User.is_active == True)
        )
        users = result.all()
    except Exception as e:
        logger.error(f"Failed to fetch users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")
    
    if not users:
        return {
            "detail": "No active users found to send broadcast to",
            "total_users": 0,
            "success_count": 0,
            "failed_count": 0
        }
    
    # Send broadcast email to all users
    success_count = 0
    failed_count = 0
    failed_emails = []
    
    logger.info(f"Starting broadcast to {len(users)} users")
    
    for email, username in users:
        try:
            personalized_message = f"Hi {username},\n\n{message}"
            success = await send_broadcast_email(email, subject, personalized_message)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
                failed_emails.append(email)
                
        except Exception as e:
            logger.error(f"Failed to send broadcast to {email}: {str(e)}")
            failed_count += 1
            failed_emails.append(email)
    
    logger.info(f"Broadcast completed: {success_count} successful, {failed_count} failed")
    
    response_data = {
        "detail": f"Broadcast sent to {success_count} of {len(users)} users",
        "total_users": len(users),
        "success_count": success_count,
        "failed_count": failed_count
    }
    
    if failed_emails and os.getenv("DEBUG", "false").lower() == "true":
        response_data["failed_emails"] = failed_emails
    
    return response_data

@router.post("/broadcast/test")
async def test_broadcast(
    data: dict,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    
    subject = data.get("subject", "Test Broadcast from StudyRPG")
    message = data.get("message", "This is a test broadcast message.")
    
    try:
        success = await send_broadcast_email(
            current_user.email, 
            f"[TEST] {subject}", 
            f"Hi {current_user.username},\n\n{message}\n\n-- This was a test broadcast --"
        )
        
        if success:
            return {"detail": "Test broadcast sent successfully to admin email"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test broadcast")
            
    except Exception as e:
        logger.error(f"Test broadcast failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test broadcast failed: {str(e)}")

@router.get("/broadcast/test-smtp")
async def test_smtp_connection_endpoint(
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    
    try:
        from app.email_utils import test_smtp_connection
        success = await test_smtp_connection()
        
        if success:
            return {"detail": "SMTP connection test successful"}
        else:
            return {"detail": "SMTP connection test failed", "status": "error"}
            
    except Exception as e:
        logger.error(f"SMTP test endpoint error: {str(e)}")
        return {"detail": f"SMTP connection test failed: {str(e)}", "status": "error"}

# =========================================================
# FEEDBACK MANAGEMENT
# =========================================================
@router.get("/feedback")
async def get_feedback_list(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    # Import Feedback model from the correct location
    from app.models_feedback import Feedback
    result = await db.execute(select(Feedback).order_by(Feedback.created_at.desc()))
    return result.scalars().all()

@router.put("/feedback/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    # Import Feedback model from the correct location
    from app.models_feedback import Feedback
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    feedback.resolved = True
    await db.commit()
    return {"detail": "Feedback resolved"}

@router.delete("/feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    # Import Feedback model from the correct location
    from app.models_feedback import Feedback
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    await db.delete(feedback)
    await db.commit()
    return {"detail": "Feedback deleted"}

# =========================================================
# ANALYTICS & STATS
# =========================================================
@router.get("/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_admin(current_user)
    
    # Import Feedback model from the correct location
    from app.models_feedback import Feedback
    
    # Get counts
    users_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    quests_count = (await db.execute(select(func.count()).select_from(Quest))).scalar_one()
    shop_items_count = (await db.execute(select(func.count()).select_from(ShopItem))).scalar_one()
    boss_battles_count = (await db.execute(select(func.count()).select_from(BossBattle))).scalar_one()
    feedback_count = (await db.execute(select(func.count()).select_from(Feedback))).scalar_one()

    return {
        "users": users_count,
        "quests": quests_count,
        "shop_items": shop_items_count,
        "boss_battles": boss_battles_count,
        "feedback_items": feedback_count,
    }