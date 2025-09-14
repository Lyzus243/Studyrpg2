from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.database import get_async_session
from app.models import User, ShopItem, Quest, Group, BossBattle
from app.models_feedback import Feedback
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy import func
from app.routers.auth import get_current_user, get_password_hash, oauth2_scheme
from app.email_utils import send_broadcast_email
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security import OAuth2PasswordBearer
import os
import logging
from dotenv import load_dotenv
from jose import JWTError, jwt

logger = logging.getLogger(__name__)
load_dotenv()
# Use HTTPBearer instead of OAuth2PasswordBearer for API endpoints
security = HTTPBearer()
# Use prefix for all admin routes
router = APIRouter(prefix="", tags=["admin"])

# Admin credentials from .env
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Lyzus308")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234567")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "pumlezerti@necub.com")

# JWT settings (should match your auth settings)
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGO", "HS256")

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
    """Check if user is admin based on .env credentials"""
    if not user:
        logger.warning("No user provided to admin check")
        raise HTTPException(status_code=403, detail="Admin access only")
    
    # Check if username matches admin username from .env (case-insensitive)
    if user.username.lower() != ADMIN_USERNAME.lower():
        logger.warning(f"Admin access denied for user: {user.username} (expected: {ADMIN_USERNAME})")
        raise HTTPException(status_code=403, detail="Admin access only")
    
    logger.info(f"✅ Admin access granted for user: {user.username}")
    return True

async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Simple admin token verifier that only checks username against ADMIN_USERNAME
    """
    if not credentials:
        logger.info("No credentials received")
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    if not token:
        logger.info("No token in credentials")
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Decode and verify token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if os.getenv("DEBUG", "false").lower() == "true":
            logger.debug("Decoded JWT payload: %s", payload)
    except JWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    # Get the subject (username) from the token
    subject = payload.get("sub")
    if not subject:
        logger.warning("No sub found in token payload: %s", payload)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    # Query DB for user by username (case-insensitive)
    try:
        result = await db.execute(select(User).where(func.lower(User.username) == str(subject).lower()))
        user = result.scalar_one_or_none()
    except Exception as e:
        logger.error("DB lookup error in verify_admin_token: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    if not user:
        logger.warning("Token subject %s has no matching DB user", subject)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    # Only check if username matches ADMIN_USERNAME (case-insensitive)
    if user.username.lower() != ADMIN_USERNAME.lower():
        logger.warning("User %s is not admin (expected: %s)", user.username, ADMIN_USERNAME)
        raise HTTPException(status_code=403, detail="Admin access only")

    logger.info("Admin verified by username match: %s", user.username)
    return user


@router.get("/debug/env-check")
async def debug_env_check():
    """Debug endpoint to check environment variables (no auth required)"""
    return {
        "ADMIN_USERNAME": ADMIN_USERNAME,
        "ADMIN_PASSWORD_SET": bool(ADMIN_PASSWORD),
        "SECRET_KEY_SET": bool(SECRET_KEY),
        "ALGORITHM": ALGORITHM
    }
# =========================================================
# SHOP MANAGEMENT
# =========================================================
@router.get("/shop")
async def get_shop_items(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
    result = await db.execute(select(ShopItem))
    return result.scalars().all()

@router.post("/shop", response_model=ShopItemCreate)
async def add_shop_item(
    item: ShopItemCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
    result = await db.execute(select(Quest))
    return result.scalars().all()

@router.post("/quests", response_model=QuestCreate)
async def create_quest(
    quest: QuestCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
    result = await db.execute(select(User))
    return result.scalars().all()

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
    result = await db.execute(select(BossBattle))
    return result.scalars().all()

@router.post("/boss-battles")
async def create_boss_battle(
    boss_battle: BossBattleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
    boss_obj = BossBattle(**boss_battle.dict())
    db.add(boss_obj)
    await db.commit()
    await db.refresh(boss_obj)
    return boss_obj

# Add this to your admin.py file to test if the router is working
@router.get("/test-admin")
async def admin_test():
    return {"message": "Admin router is working"}


@router.put("/boss-battles/{boss_id}")
async def update_boss_battle(
    boss_id: int,
    boss_battle: BossBattleUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
    result = await db.execute(select(Feedback).order_by(Feedback.created_at.desc()))
    return result.scalars().all()

@router.put("/feedback/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
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
    current_user: User = Depends(verify_admin_token)
):
    # Get counts
    users_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    quests_count = (await db.execute(select(func.count()).select_from(Quest))).scalar_one()
    shop_items_count = (await db.execute(select(func.count()).select_from(ShopItem))).scalar_one()
    boss_battles_count = (await db.execute(select(func.count()).select_from(BossBattle))).scalar_one()
    
    # Handle feedback count with error handling
    try:
        feedback_count = (await db.execute(select(func.count()).select_from(Feedback))).scalar_one()
    except Exception as e:
        logger.warning(f"Failed to get feedback count: {e}")
        feedback_count = 0

    return {
        "users": users_count,
        "quests": quests_count,
        "shop_items": shop_items_count,
        "boss_battles": boss_battles_count,
        "feedback_items": feedback_count,
        "current_user": current_user.username,  # Add this for debugging
        "admin_check_passed": True  # Add this for debugging
    }

# =========================================================
# ADMIN DEBUG INFO
# =========================================================
@router.get("/debug/admin-info")
async def get_admin_debug_info(
    current_user: User = Depends(verify_admin_token)
):
    """Debug endpoint to check admin configuration"""
    
    return {
        "current_user": current_user.username,
        "expected_admin": ADMIN_USERNAME,
        "is_admin": current_user.username.lower() == ADMIN_USERNAME.lower(),
        "admin_configured": bool(ADMIN_USERNAME and ADMIN_PASSWORD),
        "env_admin_username": ADMIN_USERNAME,
        "env_has_password": bool(ADMIN_PASSWORD)
    }

# =========================================================
# DEBUG ENDPOINTS (temporary)
# =========================================================
@router.get("/debug/auth-test")
async def debug_auth_test(
    current_user: User = Depends(verify_admin_token)
):
    """Debug endpoint to test authentication"""
    return {
        "authenticated": True,
        "user": current_user.username,
        "is_admin": current_user.username.lower() == ADMIN_USERNAME.lower(),
        "env_admin": ADMIN_USERNAME
    }

@router.get("/debug/env-check")
async def debug_env_check():
    """Debug endpoint to check environment variables (no auth required)"""
    return {
        "ADMIN_USERNAME": ADMIN_USERNAME,
        "ADMIN_PASSWORD_SET": bool(ADMIN_PASSWORD),
        "SECRET_KEY_SET": bool(SECRET_KEY),
        "ALGORITHM": ALGORITHM
    }

# Function to create admin user if it doesn't exist
async def create_admin_user_if_not_exists(db: AsyncSession):
    """
    Create admin user if it doesn't exist
    """
    result = await db.execute(select(User).where(User.username == ADMIN_USERNAME))
    admin_user = result.scalar_one_or_none()
    
    if not admin_user:
        admin_user = User(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            hashed_password=get_password_hash(ADMIN_PASSWORD),
            is_active=True,
            is_verified=True,
            role="admin"
        )
        db.add(admin_user)
        await db.commit()
        logger.info("Admin user created successfully")
    else:
        logger.info("Admin user already exists")