# app/main.py
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jinja2 import TemplateNotFound
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List, Optional, Dict
from pathlib import Path
from jose import JWTError, jwt
from app.routers.auth import get_current_user_optional, get_current_user
from datetime import datetime
from app.init_db import init_db, get_async_session
from app.routers import (
    admin, admin_ui, auth, user, leveling_router, quests, pomodoro,
    memory_training, shop, flashcard, study_group, group_boss_battles,
     skills, ai, analytics
)
from app.connection_manager import ConnectionManager
from app import models
from app.models import UserActivity # Added Badge and UserBadge imports
import logging
import os
import json
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app.log", mode='a')]
)
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("Database initialized successfully")
        yield
    except Exception as e:
        logger.critical(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Application shutdown")

app = FastAPI(
    title="StudyRPG API",
    description="An RPG-style learning platform API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DebugMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Request processing failed: {str(e)}")
            raise
app.add_middleware(DebugMiddleware)

# Path config
BASE_DIR = Path(__file__).parent.parent
TEMPLATE_DIR = BASE_DIR / "static" / "templates"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

manager = ConnectionManager()

# ------------------------ Admin restriction ------------------------
async def admin_only(current_user: models.User = Depends(get_current_user)):
    if current_user.username != "Lyzus":
        raise HTTPException(status_code=403, detail="Admin access only")
    return current_user

# ------------------------ Routers ------------------------
app.include_router(auth.auth_router, prefix="/auth")
app.include_router(user.user_router, prefix="/users")
app.include_router(quests.quests_router, prefix="/quests")
app.include_router(pomodoro.pomodoro_router, prefix="/pomodoro")
app.include_router(memory_training.memory_router, prefix="/memory")
app.include_router(shop.shop_router, prefix="/shop")
app.include_router(flashcard.flashcard_router, prefix="/flashcards")
app.include_router(study_group.study_groups_router, prefix="/groups")
app.include_router(group_boss_battles.group_boss_battles_router, prefix="/battles/group")
app.include_router(skills.skills_router, prefix="/skills")
app.include_router(ai.ai_router, prefix="/ai")
app.include_router(analytics.analytics_router, prefix="/analytics")
app.include_router(leveling_router.leveling_router, prefix="/leveling")

# Remove admin_only dependency from UI routes
app.include_router(admin_ui.admin_ui, tags=["Admin UI"])

# Keep admin_only for API routes
app.include_router(admin.router, prefix="/admin", tags=["Admin"], dependencies=[Depends(admin_only)])

# Update the get_authenticated_user function in main.py
async def get_authenticated_user(request: Request, db: AsyncSession = Depends(get_async_session)) -> models.User:
    # Check Authorization header first
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    # Then check cookie
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Validate token and get user - FIXED: Use the same validation as in auth.py
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Check token expiration
        expire = payload.get("exp")
        if expire is None:
            raise HTTPException(status_code=401, detail="Token has no expiration")
            
        current_time = datetime.utcnow()
        expire_time = datetime.utcfromtimestamp(expire)
        
        if current_time > expire_time:
            raise HTTPException(status_code=401, detail="Token expired")
        
        # Query user
        result = await db.execute(select(models.User).where(models.User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Check if user is verified and active
        if not user.is_verified:
            raise HTTPException(status_code=401, detail="Email not verified")
        if not user.is_active:
            raise HTTPException(status_code=401, detail="Account deactivated")
        
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ------------------------ Public HTML pages ------------------------
@app.get("/", response_class=HTMLResponse)
async def intro_page(request: Request):
    return templates.TemplateResponse("intro.html", {"request": request})

@app.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    return templates.TemplateResponse("Faq.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/validAccount", response_class=HTMLResponse)
async def valid_page(request: Request):
    return templates.TemplateResponse("validAccount.html", {"request": request})

@app.get("/overview", response_class=HTMLResponse)
async def overview_page(request: Request):
    return templates.TemplateResponse("overview.html", {"request": request})

# ------------------------ Protected HTML pages ------------------------
@app.get("/profile/{username}", response_class=HTMLResponse)
async def profile_page(request: Request, username: str, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_authenticated_user)):
    # Fetch user stats
    stats = {
        "xp": current_user.xp,
        "level": current_user.level,
        "streak": current_user.streak,
        "skill_points": current_user.skill_points
    }
    
    # Fetch recent activities - FIXED
    activity_stmt = select(UserActivity).where(
        UserActivity.user_id == current_user.id
    ).order_by(UserActivity.timestamp.desc()).limit(5)
    result = await db.execute(activity_stmt)
    activities = result.scalars().all()
    
    # Fetch quests
    quest_stmt = select(models.Quest).where(
        models.Quest.user_id == current_user.id,
        models.Quest.completed_at == False
    ).limit(5)
    result = await db.execute(quest_stmt)
    quests = result.scalars().all()
    
    # Fetch skills
    skill_stmt = select(models.Skill).where(
        models.Skill.id == current_user.id
    ).limit(5)
    result = await db.execute(skill_stmt)
    skills = result.scalars().all()
    
    # Fetch boss battles
    battle_stmt = select(models.BossBattle).where(
        models.BossBattle.user_id == current_user.id
    ).order_by(models.BossBattle.is_completed.desc()).limit(3)
    result = await db.execute(battle_stmt)
    battles = result.scalars().all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "stats": stats,
        "activities": activities,
        "quests": quests,
        "skills": skills,
        "battles": battles
    })

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("inventory.html", {"request": request, "user": user})


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("analytics.html", {"request": request, "user": user})


@app.get("/badges", response_class=HTMLResponse)
async def badges_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("badge.html", {"request": request, "user": user})



# ------------------------
# Inventory API endpoint
# ------------------------
@app.get("/inventory-data")
async def get_inventory_data(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_authenticated_user)
):
    try:
        # Query user's items with item details
        result = await db.execute(
            select(models.UserItem, models.Item)
            .join(models.Item, models.UserItem.item_id == models.Item.id)
            .where(models.UserItem.user_id == current_user.id)
        )
        items = result.all()
        
        inventory = []
        for user_item, item in items:
            inventory.append({
                "id": user_item.id,
                "item_id": item.id,
                "name": item.name,
                "description": item.description,
                "price": item.price,
                "is_used": user_item.is_used,
                "used_at": user_item.used_at.isoformat() if user_item.used_at else None,
                "purchased_at": user_item.purchased_at.isoformat()
            })
        
        return {"inventory": inventory}
        
    except Exception as e:
        logger.error(f"Error fetching inventory: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching inventory data")
# Badges API endpoint
# @app.get("/api/user/badges")
# async def get_user_badges(
#     db: AsyncSession = Depends(get_async_session),
#     current_user: models.User = Depends(get_authenticated_user)
# ):
#     try:
#         # Get all available badges
#         result = await db.execute(select(Badge))
#         all_badges = result.scalars().all()
        
#         # Get badges earned by current user
#         result = await db.execute(
#             select(UserBadge).where(UserBadge.user_id == current_user.id)
#         )
#         user_badges = result.scalars().all()
        
#         return {
#             "badges": [
#                 {
#                     "id": badge.id,
#                     "name": badge.name,
#                     "description": badge.description,
#                     "icon_url": badge.icon_url,
#                     "xp_required": badge.xp_required
#                 }
#                 for badge in all_badges
#             ],
#             "earnedBadges": [
#                 {
#                     "badge_id": ub.badge_id,
#                     "earned_at": ub.earned_at.isoformat() if ub.earned_at else None
#                 }
#                 for ub in user_badges
#             ]
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Error fetching badges")

@app.get("/leveling", response_class=HTMLResponse)
async def leveling_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("leveling.html", {"request": request, "user": user})

@app.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("skills.html", {"request": request, "user": user})

@app.get("/quests", response_class=HTMLResponse)
async def quests_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("quests.html", {"request": request, "user": user})

@app.get("/pomodoro", response_class=HTMLResponse)
async def pomodoro_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("pomodoro.html", {"request": request, "user": user})

@app.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("memory.html", {"request": request, "user": user})

@app.get("/shop", response_class=HTMLResponse)
async def shop_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("shop.html", {"request": request, "user": user})

@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("groups.html", {"request": request, "user": user})

@app.get("/battles/group", response_class=HTMLResponse)
async def battles_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("boss_battles.html", {"request": request, "user": user})

@app.get("/ai-tools", response_class=HTMLResponse)
async def ai_tools_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("ai_tools.html", {"request": request, "user": user})

@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("leaderboard.html", {"request": request, "user": user})

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, user: models.User = Depends(get_authenticated_user)):
    return templates.TemplateResponse("analytics.html", {"request": request, "user": user})


# ------------------------
# Debug / Health endpoints
# ------------------------
@app.get("/debug/db-test")
async def test_db(db: AsyncSession = Depends(get_async_session)):
    try:
        result = await db.execute(select(models.User).limit(1))
        user = result.scalar_one_or_none()
        return {"db_working": True, "user_found": user is not None}
    except Exception as e:
        return {"db_working": False, "error": str(e)}

@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "operational",
        "api": "responsive"
    }

    try:
        # Acquire an async session and run simple checks
        db_gen = get_async_session()
        db = await db_gen.__anext__()  # type: ignore
        try:
            await db.execute(text("SELECT 1"))
            result = await db.execute(select(models.User).limit(1))
            if result.scalar_one_or_none() is None:
                logger.warning("Health check: Database accessible but no users found")
            return health_status
        finally:
            try:
                await db_gen.aclose()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        health_status.update({
            "status": "unhealthy",
            "error": str(e),
            "database": "unavailable",
            "api": "responsive"
        })
        return JSONResponse(content=health_status, status_code=503)

@app.get("/auth/verify")
async def verify_token(current_user: models.User = Depends(get_current_user)):
    return {
        "valid": True,
        "user": {"username": current_user.username, "email": current_user.email, "id": current_user.id}
    }

@app.post("/debug/verify-token")
async def verify_token_debug(token: str, db: AsyncSession = Depends(get_async_session)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return {"valid": False, "error": "No username in token"}
        expire = payload.get("exp")
        if expire is None or datetime.utcnow() > datetime.utcfromtimestamp(expire):
            return {"valid": False, "error": "Token expired"}
        res = await db.execute(select(models.User).where(models.User.username == username))
        user = res.scalar_one_or_none()
        if user is None:
            return {"valid": False, "error": "User not found"}
        return {"valid": True, "user_id": user.id, "username": user.username}
    except JWTError as e:
        return {"valid": False, "error": str(e)}

# ------------------------
# Leaderboard API
# ------------------------
@app.get("/leaderboard-data")
async def get_leaderboard(db: AsyncSession = Depends(get_async_session), limit: int = 10):
    res = await db.execute(
        select(models.User.username, models.User.xp, models.User.level)
        .order_by(models.User.xp.desc())
        .limit(limit)
    )
    rows = res.all()
    leaderboard = [
        {
            "username": r[0], 
            "xp": str(r[1]),  # Convert to string
            "level": str(r[2]),  # Convert to string
            "rank": str(idx + 1)  # Convert to string
        }
        for idx, r in enumerate(rows)
    ]
    return leaderboard

# ------------------------
# WebSocket
# ------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None, db: AsyncSession = Depends(get_async_session)):
    await websocket.accept()

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(creds, db)
        await manager.connect(websocket, f"user_{user.id}")
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "leaderboard_request":
                    leaderboard = await get_leaderboard(db)
                    await websocket.send_json({"type": "leaderboard_update", "data": leaderboard})
                else:
                    await manager.broadcast_to_group(
                        json.dumps({
                            "type": "user_update",
                            "user_id": user.id,
                            "data": data,
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        f"user_{user.id}"
                    )
        except WebSocketDisconnect:
            manager.disconnect(websocket, f"user_{user.id}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON via WebSocket")
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    except HTTPException as e:
        logger.error(f"WebSocket auth error: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except JWTError:
        logger.error("Invalid JWT in WebSocket")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

# ------------------------
# Run
# ------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", reload=True, timeout_keep_alive=60)