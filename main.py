import urllib
import os
import json
import csv
import io
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict

import PyPDF2
from fastapi import (
    FastAPI, Depends, HTTPException, Request, BackgroundTasks, Body, Query, Form, UploadFile, File, Response, WebSocket, WebSocketDisconnect, APIRouter
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import models, schemas, crud
from app.pomodoro import pomodoro_router
from app.flashcard import flashcards_router
from app.memory_training import memory_router
from app.auth import create_access_token
from app.quests import get_quest_templates
from app.ai import AIStudyTools
from app.database import get_async_session, engine

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(
    title="StudyRPG",
    description="Gamified study companion inspired by RPGs and Solo Leveling.",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)

# Templates
templates = Jinja2Templates(directory="templates")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, key: str):
        await websocket.accept()
        if key not in self.active_connections:
            self.active_connections[key] = []
        self.active_connections[key].append(websocket)

    def disconnect(self, websocket: WebSocket, key: str):
        if key in self.active_connections:
            self.active_connections[key].remove(websocket)
            if not self.active_connections[key]:
                del self.active_connections[key]

    async def broadcast(self, message: str, key: str, sender: WebSocket = None):
        if key in self.active_connections:
            for connection in self.active_connections[key]:
                if connection != sender:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        self.disconnect(connection, key)

manager = ConnectionManager()

# Authentication dependency
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_session)) -> Optional[models.User]:
    if not token:
        logger.debug("No token provided")
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            logger.debug("No username in token payload")
            return None
        user = await crud.get_user_by_username(db, username)
        if not user:
            logger.debug(f"User not found for username: {username}")
            return None
        return user
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None

async def require_auth(request: Request, db: AsyncSession = Depends(get_async_session)) -> models.User:
    user = await get_current_user(token=request.cookies.get("access_token"), db=db)
    if not user:
        logger.info(f"Redirecting unauthenticated request from {request.url.path} to login")
        response = RedirectResponse(url="/auth/login", status_code=302)
        response.delete_cookie("access_token")
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"429 Too Many Requests from {request.client.host}: {exc.detail}")
    return PlainTextResponse("Too many requests - try again later.", status_code=429)

# Routers
auth_router = APIRouter()
user_router = APIRouter()
group_router = APIRouter()
quest_router = APIRouter()
skill_router = APIRouter()
battle_router = APIRouter()
analytics_router = APIRouter()
ai_router = APIRouter()

# Authentication Routes
@auth_router.get("/intro", response_class=HTMLResponse)
async def intro_page(request: Request):
    return templates.TemplateResponse("intro.html", {"request": request})

@auth_router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@auth_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@auth_router.post("/signup", response_class=RedirectResponse)
async def signup_user(
    user: schemas.UserCreate = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_session)
):
    logger.info("Starting signup process")
    try:
        existing_user = await crud.get_user_by_username(db, user.username)
        if existing_user:
            logger.warning(f"Username {user.username} already exists")
            raise HTTPException(status_code=400, detail="Username already exists")
        existing_email = await crud.get_user_by_email(db, user.email.lower())
        if existing_email:
            logger.warning(f"Email {user.email} already registered")
            raise HTTPException(status_code=400, detail="Email already registered")
        logger.info("Creating new user")
        new_user = await crud.create_user(db, user)
        logger.info(f"User {new_user.username} created, generating token")
        verification_token = create_access_token(
            data={"sub": new_user.email, "purpose": "email_verification"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        logger.info("Scheduling verification email")
        background_tasks.add_task(
            crud.send_verification_email,
            new_user.email,
            new_user.username,
            verification_token
        )
        logger.info(f"Redirecting to /auth/validAccount.html?username={new_user.username}")
        return RedirectResponse(url=f"/auth/validAccount.html?username={new_user.username}", status_code=303)
    except HTTPException as e:
        logger.error(f"HTTPException during signup: {e.detail}")
        error_message = urllib.parse.quote(e.detail)
        return RedirectResponse(url=f"/auth/signup?error={error_message}", status_code=303)
    except Exception as e:
        logger.error(f"Unexpected signup error: {str(e)}")
        error_message = urllib.parse.quote("An unexpected error occurred")
        return RedirectResponse(url=f"/auth/signup?error={error_message}", status_code=303)

@auth_router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_async_session)):
    user = await crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"Authentication failed for username: {form_data.username}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@auth_router.post("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@auth_router.get("/verify-email", response_class=RedirectResponse)
async def verify_email(token: str, db: AsyncSession = Depends(get_async_session)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        purpose: Optional[str] = payload.get("purpose")
        if email is None or purpose != "email_verification":
            logger.error("Invalid verification token")
            raise HTTPException(status_code=400, detail="Invalid token")
        if datetime.utcnow().timestamp() > payload.get("exp", 0):
            error_message = urllib.parse.quote("Token has expired")
            return RedirectResponse(url=f"/auth/signup?error={error_message}", status_code=303)
        user = await crud.get_user_by_email(db, email.lower())
        if not user:
            error_message = urllib.parse.quote("User not found")
            return RedirectResponse(url=f"/auth/signup?error={error_message}", status_code=303)
        if not user.is_verified:
            user.is_verified = True
            db.add(user)
            await db.commit()
            await db.refresh(user)
        response = RedirectResponse(url=f"/auth/validAccount?username={user.username}&verified=true", status_code=303)
        access_token = create_access_token({"sub": user.email, "user_id": user.id}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, samesite="lax")
        return response
    except JWTError:
        error_message = urllib.parse.quote("Invalid token")
        return RedirectResponse(url=f"/auth/signup?error={error_message}", status_code=303)

@auth_router.get("/validAccount", response_class=HTMLResponse)
async def valid_account(request: Request, username: str, db: AsyncSession = Depends(get_async_session)):
    logger.info(f"Rendering validAccount for username: {username}")
    user = await crud.get_user_by_username(db, username)
    if not user:
        logger.error(f"User not found: {username}")
        raise HTTPException(status_code=404, detail="User not found")
    message = "Your email has been verified!" if request.query_params.get('verified') else "User created successfully. Verification email sent."
    return templates.TemplateResponse("validAccount.html", {"request": request, "user": user, "message": message})

@auth_router.post("/resend-verification")
async def resend_verification(background_tasks: BackgroundTasks, current_user: models.User = Depends(get_current_user)):
    if current_user.is_verified:
        return {"message": "Already verified."}
    verification_token = create_access_token({"sub": current_user.email, "purpose": "email_verification"}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    background_tasks.add_task(crud.send_verification_email, current_user.email, current_user.username, verification_token)
    return {"message": "Verification email sent."}

@auth_router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = None):
    return templates.TemplateResponse("reset-password.html", {"request": request, "token": token})

@auth_router.post("/password-reset/request")
async def request_password_reset(email: str = Body(...), db: AsyncSession = Depends(get_async_session), background_tasks: BackgroundTasks = BackgroundTasks()):
    user = await crud.get_user_by_email(db, email.lower())
    if not user:
        return {"message": "If the email exists, a reset link has been sent."}
    token = await crud.generate_reset_token(db, user.id)
    reset_link = f"{os.getenv('API_URL', 'http://localhost:8000')}/auth/reset-password?token={token}"
    message = MessageSchema(
        subject="StudyRPG Password Reset",
        recipients=[email],
        body=f"Click the following link to reset your password: {reset_link}\nThis link expires in 1 hour.",
        subtype="plain",
        from_email=os.getenv("MAIL_FROM")
    )
    fm = FastMail(conf)
    background_tasks.add_task(fm.send_message, message)
    return {"message": "If the email exists, a reset link has been sent."}

@auth_router.post("/password-reset/confirm")
async def confirm_password_reset(token: str = Body(...), new_password: str = Body(...), db: AsyncSession = Depends(get_async_session)):
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user_id = await crud.validate_reset_token(db, token)
    await crud.update_user_password(db, user_id, new_password)
    await db.exec(select(models.PasswordReset).where(models.PasswordReset.token == token).delete())
    await db.commit()
    return {"message": "Password reset successfully"}

# User Routes
@user_router.get("/me", response_model=schemas.UserRead)
async def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    return schemas.UserRead.from_orm(current_user)

@user_router.put("/me", response_model=schemas.UserRead)
async def update_profile(payload: schemas.UserUpdate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    updated_user = await crud.update_user(db, current_user.id, payload.dict(exclude_unset=True))
    if updated_user.email != current_user.email:
        verification_token = create_access_token({"sub": updated_user.email, "purpose": "email_verification"}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        background_tasks.add_task(crud.send_verification_email, updated_user.email, updated_user.username, verification_token)
    return schemas.UserRead.from_orm(updated_user)

@user_router.get("/profile/{user_id}", response_class=HTMLResponse)
async def get_profile(request: Request, user_id: int, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    user = await crud.get_user(db, user_id)
    groups = await crud.get_study_groups(db, user_id)
    quests = await crud.get_quests(db, user_id, completed=True)
    solo_battles = await crud.get_boss_battles(db, user_id)
    group_battles = (await db.exec(select(models.GroupBossBattle).join(models.UserGroupBossBattle).where(models.UserGroupBossBattle.user_id == user_id))).all()
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "current_user": current_user,
        "profile": {
            "username": user.username,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "xp": user.xp,
            "skill_points": user.skill_points,
            "streak": user.streak,
            "groups": [schemas.StudyGroupRead.from_orm(g) for g in groups],
            "completed_quests": [schemas.QuestRead.from_orm(q) for q in quests],
            "boss_battles": [
                {**schemas.BossBattleRead.from_orm(b).dict(), "is_group": False} for b in solo_battles
            ] + [
                {**schemas.GroupBossBattleRead.from_orm(b).dict(), "is_group": True} for b in group_battles
            ]
        }
    })

# Study Group Routes
@group_router.get("/study-groups", response_class=HTMLResponse)
async def get_study_groups_page(request: Request, current_user: models.User = Depends(get_current_user), query: Optional[str] = None, group_id: Optional[int] = None, db: AsyncSession = Depends(get_async_session)):
    groups = [await crud.get_study_group(db, group_id)] if group_id else await crud.get_study_groups(db, current_user.id, query)
    if group_id and not groups[0]:
        raise HTTPException(status_code=404, detail="Group not found")
    return templates.TemplateResponse("groups.html", {
        "request": request,
        "current_user": current_user,
        "groups": [schemas.StudyGroupRead.from_orm(g) for g in groups]
    })

@group_router.post("/study-groups", response_model=schemas.StudyGroupRead)
async def create_study_group_api(group: schemas.StudyGroupCreate, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    study_group = await crud.create_study_group(db, group, current_user.id)
    message = models.GroupMessage(
        content=f"Group '{study_group.name}' created by {current_user.username}",
        user_id=current_user.id,
        group_id=study_group.id,
        timestamp=datetime.utcnow()
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    await manager.broadcast(json.dumps({
        "type": "chat_message",
        "content": message.content,
        "user": schemas.UserRead.from_orm(current_user).dict(),
        "timestamp": message.timestamp.isoformat()
    }), f"group_{study_group.id}")
    await manager.broadcast(json.dumps({
        "type": "group_update",
        "group_id": study_group.id,
        "message": f"New group '{study_group.name}' created by {current_user.username}"
    }), "notifications")
    return schemas.StudyGroupRead.from_orm(study_group)

@group_router.get("/api/groups/{group_id}/messages")
async def get_group_messages(group_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    group = (await db.exec(select(models.StudyGroup).filter(models.StudyGroup.id == group_id, models.StudyGroup.members.any(id=current_user.id)))).first()
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized to view this group's messages")
    messages = (await db.exec(
        select(models.GroupMessage)
        .filter(models.GroupMessage.group_id == group_id)
        .order_by(models.GroupMessage.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )).all()
    return [
        {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "user": {"id": msg.user.id, "username": msg.user.username, "avatar_url": msg.user.avatar_url}
        }
        for msg in messages
    ]

@group_router.get("/api/groups/{group_id}/unread-count")
async def get_unread_message_count(group_id: int, last_seen: datetime = Query(...), db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    group = (await db.exec(select(models.StudyGroup).filter(models.StudyGroup.id == group_id, models.StudyGroup.members.any(id=current_user.id)))).first()
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized to view this group's messages")
    count = (await db.exec(
        select(models.GroupMessage)
        .filter(
            models.GroupMessage.group_id == group_id,
            models.GroupMessage.timestamp > last_seen,
            models.GroupMessage.user_id != current_user.id
        )
    )).count()
    return {"unread_count": count}

@group_router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str):
    try:
        user = await get_current_user(token=token, db=AsyncSession(engine))
        if not user:
            await websocket.close(code=1008)
            return
        await manager.connect(websocket, "notifications")
        try:
            while True:
                await websocket.receive_json()
        except WebSocketDisconnect:
            manager.disconnect(websocket, "notifications")
    except JWTError:
        await websocket.close(code=1008)

@group_router.websocket("/ws/groups/{group_id}/chat")
async def websocket_group_chat(websocket: WebSocket, group_id: int, token: str = Query(...), db: AsyncSession = Depends(get_async_session)):
    user = await get_current_user(token=token, db=db)
    if not user:
        await websocket.close(code=1008)
        return
    group = (await db.exec(select(models.StudyGroup).filter(models.StudyGroup.id == group_id, models.StudyGroup.members.any(id=user.id)))).first()
    if not group:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket, f"group_{group_id}")
    join_message = json.dumps({
        "type": "user_joined",
        "user_id": user.id,
        "username": user.username,
        "timestamp": datetime.utcnow().isoformat()
    })
    await manager.broadcast(join_message, f"group_{group_id}", websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            if not message_data.get("content") or not message_data["content"].strip():
                continue
            new_message = models.GroupMessage(
                content=message_data["content"].strip(),
                group_id=group_id,
                user_id=user.id,
                timestamp=datetime.utcnow()
            )
            db.add(new_message)
            await db.commit()
            await db.refresh(new_message)
            message_to_send = json.dumps({
                "type": "chat_message",
                "id": new_message.id,
                "content": new_message.content,
                "timestamp": new_message.timestamp.isoformat(),
                "user": {"id": user.id, "username": user.username, "avatar_url": user.avatar_url}
            })
            await manager.broadcast(message_to_send, f"group_{group_id}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"group_{group_id}")
        leave_message = json.dumps({
            "type": "user_left",
            "user_id": user.id,
            "username": user.username,
            "timestamp": datetime.utcnow().isoformat()
        })
        await manager.broadcast(leave_message, f"group_{group_id}")
    except json.JSONDecodeError:
        await websocket.close(code=1003)

# Quest Routes
@quest_router.post("/", response_model=schemas.QuestRead)
async def create_quest(quest: schemas.QuestCreate, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    return await crud.create_quest(db, quest, current_user.id)

@quest_router.get("/templates")
async def quest_templates():
    return get_quest_templates()

@quest_router.get("/{user_id}", response_model=List[schemas.QuestRead])
async def get_user_quests(user_id: int, quest_type: Optional[str] = None, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await crud.get_quests(db, user_id, quest_type)

@quest_router.put("/{quest_id}", response_model=schemas.QuestRead)
async def update_quest(quest_id: int, quest: schemas.QuestUpdate, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    quest = await crud.update_quest(db, quest_id, quest, current_user.id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quest

@quest_router.delete("/{quest_id}")
async def delete_quest(quest_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    return await crud.delete_quest(db, quest_id, current_user.id)

@quest_router.post("/{quest_id}/complete")
async def complete_quest(quest_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    quest = await crud.complete_quest(db, quest_id, current_user.id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    analytics = await crud.get_analytics_data(db, current_user.id, date.today(), date.today())
    await manager.broadcast(json.dumps({
        "type": "analytics_update",
        "analytics": schemas.UserAnalyticsResponse(
            start_date=date.today(),
            end_date=date.today(),
            daily_xp=analytics["daily_xp"],
            efficiency=analytics["efficiency"],
            nba_style=analytics["nba_style"]
        ).dict()
    }), f"analytics_{current_user.id}")
    return {"message": "Quest completed"}

# Skill Routes
@skill_router.post("/", response_model=schemas.SkillRead)
async def create_skill(skill: schemas.SkillCreate, db: AsyncSession = Depends(get_async_session)):
    return await crud.create_skill(db, skill)

@skill_router.get("/", response_class=HTMLResponse)
async def skills_page(request: Request, current_user: models.User = Depends(require_auth), db: AsyncSession = Depends(get_async_session)):
    skills = await crud.get_user_skills(db, current_user.id)
    return templates.TemplateResponse("skills.html", {"request": request, "user": current_user, "skills": skills})

@skill_router.post("/{skill_id}/unlock")
async def unlock_skill(skill_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    skill = await crud.unlock_skill(db, current_user.id, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill

@skill_router.get("/unlocked", response_model=List[schemas.SkillRead])
async def unlocked_skills(db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    return await crud.get_unlocked_skills(db, current_user.id)

# Battle Routes
@battle_router.post("/", response_model=schemas.BossBattleRead)
async def create_boss_battle(battle: schemas.BossBattleCreate, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    return await crud.create_boss_battle(db, battle, current_user.id)

@battle_router.get("/", response_model=List[schemas.BossBattleRead])
async def get_boss_battles(db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    return await crud.get_boss_battles(db, current_user.id)

@battle_router.post("/group_boss_battles/create", response_model=schemas.GroupBossBattleRead)
async def create_group_boss_battle(battle: schemas.GroupBossBattleCreate, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    group = (await db.exec(select(models.StudyGroup).where(models.StudyGroup.id == battle.group_id, models.StudyGroup.members.any(id=current_user.id)))).first()
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized")
    group_battle = await crud.create_group_boss_battle(db, battle, battle.group_id, current_user.id)
    return schemas.GroupBossBattleRead.from_orm(group_battle)

@battle_router.get("/group_boss_battles/{group_id}", response_model=List[schemas.GroupBossBattleRead])
async def get_group_boss_battles(group_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    group = (await db.exec(select(models.StudyGroup).where(models.StudyGroup.id == group_id, models.StudyGroup.members.any(id=current_user.id)))).first()
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await crud.get_group_boss_battles(db, group_id)

@battle_router.post("/group_boss_battles/{battle_id}/join")
async def join_group_boss_battle(battle_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    battle = (await db.exec(select(models.GroupBossBattle).filter_by(id=battle_id))).first()
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    group = (await db.exec(select(models.StudyGroup).filter(models.StudyGroup.id == battle.group_id, models.StudyGroup.members.any(id=current_user.id)))).first()
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized")
    existing = (await db.exec(select(models.UserGroupBossBattle).filter_by(user_id=current_user.id, group_boss_battle_id=battle_id))).first()
    if existing:
        return {"message": "Already joined"}
    link = models.UserGroupBossBattle(user_id=current_user.id, group_boss_battle_id=battle_id)
    db.add(link)
    await db.commit()
    return {"message": "Joined battle"}

@battle_router.post("/group_boss_battles/{battle_id}/update")
async def update_group_boss_battle(battle_id: int, update: schemas.GroupBossBattleUpdate, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    battle = (await db.exec(select(models.GroupBossBattle).filter_by(id=battle_id))).first()
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    group = (await db.exec(select(models.StudyGroup).filter(models.StudyGroup.id == battle.group_id, models.StudyGroup.members.any(id=current_user.id)))).first()
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized")
    battle.current_health = update.current_health or battle.current_health
    battle.group_health = update.group_health or battle.group_health
    battle.score = update.score or battle.score
    if battle.current_health <= 0:
        battle.is_completed = True
        battle.passed = True
    if battle.group_health <= 0:
        battle.is_completed = True
        battle.passed = False
    db.add(battle)
    await db.commit()
    await db.refresh(battle)
    await manager.broadcast(json.dumps({
        "type": "battle_state",
        "current_health": battle.current_health,
        "group_health": battle.group_health,
        "score": battle.score,
        "is_completed": battle.is_completed,
        "passed": battle.passed
    }), f"battle_{battle_id}")
    return schemas.GroupBossBattleRead.from_orm(battle)

@battle_router.post("/group_boss_battles/{battle_id}/claim")
async def claim_rewards(battle_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    battle = (await db.exec(select(models.GroupBossBattle).filter_by(id=battle_id))).first()
    if not battle or not battle.is_completed:
        raise HTTPException(status_code=400, detail="Battle not completed")
    user = (await db.exec(select(models.User).filter_by(id=current_user.id))).first()
    user.xp += battle.reward_xp
    user.skill_points += battle.reward_skill_points
    if battle.reward_items:
        for item in json.loads(battle.reward_items):
            db.add(models.Item(user_id=current_user.id, name=item, description="Reward from group boss battle"))
    db.add(user)
    await db.commit()
    analytics = await crud.get_analytics_data(db, current_user.id, date.today(), date.today())
    await manager.broadcast(json.dumps({
        "type": "analytics_update",
        "analytics": schemas.UserAnalyticsResponse(
            start_date=date.today(),
            end_date=date.today(),
            daily_xp=analytics["daily_xp"],
            efficiency=analytics["efficiency"],
            nba_style=analytics["nba_style"]
        ).dict()
    }), f"analytics_{current_user.id}")
    return {"message": "Rewards claimed"}

@battle_router.websocket("/ws/group_boss_battles/{battle_id}/state")
async def websocket_battle_state(websocket: WebSocket, battle_id: int, token: str, db: AsyncSession = Depends(get_async_session)):
    user = await get_current_user(token=token, db=db)
    if not user:
        await websocket.close(code=1008)
        return
    battle = (await db.exec(select(models.GroupBossBattle).filter_by(id=battle_id))).first()
    if not battle:
        await websocket.close(code=1008)
        return
    group = (await db.exec(select(models.StudyGroup).where(models.StudyGroup.id == battle.group_id, models.StudyGroup.members.any(id=user.id)))).first()
    if not group:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket, f"battle_{battle_id}")
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"battle_{battle_id}")

# Analytics Routes
@analytics_router.get("/", response_class=HTMLResponse)
async def analytics(
    request: Request,
    start_date: date = Query(None, description="Start date for analytics (YYYY-MM-DD)"),
    end_date: date = Query(None, description="End date for analytics (YYYY-MM-DD)"),
    compare: bool = Query(False, description="Compare with previous period"),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(require_auth)
):
    start_date = start_date or date.today() - timedelta(days=30)
    end_date = end_date or date.today()
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    try:
        analytics = await crud.get_analytics_data(db, current_user.id, start_date, end_date)
        if not analytics["daily_xp"]:
            logger.info(f"No analytics data for user {current_user.id} from {start_date} to {end_date}")
        compare_data = None
        if compare:
            prev_start_date = start_date - (end_date - start_date)
            compare_data = await crud.get_analytics_data(db, current_user.id, prev_start_date, start_date - timedelta(days=1))
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "analytics": schemas.UserAnalyticsResponse(
                start_date=start_date,
                end_date=end_date,
                compare=compare,
                daily_xp=analytics["daily_xp"],
                efficiency=analytics["efficiency"],
                nba_style=analytics["nba_style"]
            ).dict(),
            "compare_data": compare_data,
            "user_id": current_user.id
        })
    except Exception as e:
        logger.error(f"Error fetching analytics for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics data")

@analytics_router.get("/data", response_model=schemas.UserAnalyticsResponse)
async def analytics_data(
    time_range: schemas.AnalyticsTimeRange = Depends(),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    start_date = time_range.start_date or date.today() - timedelta(days=30)
    end_date = time_range.end_date or date.today()
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    try:
        analytics = await crud.get_analytics_data(db, current_user.id, start_date, end_date)
        return schemas.UserAnalyticsResponse(
            start_date=start_date,
            end_date=end_date,
            compare=time_range.compare,
            daily_xp=analytics["daily_xp"],
            efficiency=analytics["efficiency"],
            nba_style=analytics["nba_style"]
        )
    except Exception as e:
        logger.error(f"Error fetching analytics data for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics data")

@analytics_router.get("/download")
async def download_analytics(
    start_date: date = Query(None, description="Start date for analytics (YYYY-MM-DD)"),
    end_date: date = Query(None, description="End date for analytics (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    start_date = start_date or date.today() - timedelta(days=30)
    end_date = end_date or date.today()
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    try:
        analytics = await crud.get_analytics_data(db, current_user.id, start_date, end_date)
        if not analytics["daily_xp"]:
            raise HTTPException(status_code=404, detail="No analytics data available for the specified date range")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "XP", "Efficiency", "Consistency", "AvgSessionLength"])
        for d in analytics["daily_xp"]:
            writer.writerow([
                d,
                analytics["daily_xp"][d],
                analytics["efficiency"],
                analytics["nba_style"].get("consistency", 0),
                analytics["nba_style"].get("avg_session_length", 0)
            ])
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analytics_{start_date}_to_{end_date}.csv"}
        )
    except Exception as e:
        logger.error(f"Error generating analytics CSV for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate analytics CSV")

@analytics_router.websocket("/ws/analytics")
async def websocket_analytics(websocket: WebSocket, token: str, db: AsyncSession = Depends(get_async_session)):
    user = await get_current_user(token=token, db=db)
    if not user:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket, f"analytics_{user.id}")
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "request_update":
                start_date = date.fromisoformat(data.get("start_date", (date.today() - timedelta(days=30)).isoformat()))
                end_date = date.fromisoformat(data.get("end_date", date.today().isoformat()))
                compare = data.get("compare", False)
                if start_date > end_date:
                    await websocket.send_json({"type": "error", "message": "start_date cannot be after end_date"})
                    continue
                analytics = await crud.get_analytics_data(db, user.id, start_date, end_date)
                compare_data = None
                if compare:
                    prev_start_date = start_date - (end_date - start_date)
                    compare_data = await crud.get_analytics_data(db, user.id, prev_start_date, start_date - timedelta(days=1))
                await websocket.send_json({
                    "type": "analytics_update",
                    "analytics": schemas.UserAnalyticsResponse(
                        start_date=start_date,
                        end_date=end_date,
                        compare=compare,
                        daily_xp=analytics["daily_xp"],
                        efficiency=analytics["efficiency"],
                        nba_style=analytics["nba_style"]
                    ).dict(),
                    "compare_data": compare_data
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"analytics_{user.id}")
    except Exception as e:
        logger.error(f"WebSocket analytics error for user {user.id}: {str(e)}")
        await websocket.close(code=1003)

# AI Routes
@ai_router.post("/generate-timed-test")
async def generate_timed_test(request: schemas.TestGenerationRequest, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    ai_tools = AIStudyTools(current_user.id)
    test_data = ai_tools.generate_timed_test(request.material_id, request.duration)
    test_attempt = models.MaterialTestAttempt(
        user_id=current_user.id,
        material_id=request.material_id,
        test_type="timed",
        time_limit=test_data['time_limit'],
        started_at=datetime.utcnow(),
        generated_questions=json.dumps(test_data['test'])
    )
    db.add(test_attempt)
    await db.commit()
    await db.refresh(test_attempt)
    analytics = await crud.get_analytics_data(db, current_user.id, date.today(), date.today())
    await manager.broadcast(json.dumps({
        "type": "analytics_update",
        "analytics": schemas.UserAnalyticsResponse(
            start_date=date.today(),
            end_date=date.today(),
            daily_xp=analytics["daily_xp"],
            efficiency=analytics["efficiency"],
            nba_style=analytics["nba_style"]
        ).dict()
    }), f"analytics_{current_user.id}")
    return {
        "test_id": test_attempt.id,
        "questions": test_data['test'],
        "time_limit": test_data['time_limit'],
        "instructions": test_data['instructions']
    }

@ai_router.post("/practice-test")
async def ai_practice_test(material_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    questions = AIStudyTools(current_user.id).generate_practice_test(material_id)
    analytics = await crud.get_analytics_data(db, current_user.id, date.today(), date.today())
    await manager.broadcast(json.dumps({
        "type": "analytics_update",
        "analytics": schemas.UserAnalyticsResponse(
            start_date=date.today(),
            end_date=date.today(),
            daily_xp=analytics["daily_xp"],
            efficiency=analytics["efficiency"],
            nba_style=analytics["nba_style"]
        ).dict()
    }), f"analytics_{current_user.id}")
    return {"questions": questions}

@ai_router.post("/recommendations")
async def ai_recommend(db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    recs = AIStudyTools(current_user.id).get_study_recommendations()
    return {"recommendations": recs}

@ai_router.post("/process-pdf")
async def process_pdf(pdf: UploadFile = File(...)):
    contents = await pdf.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB")
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
        text = "".join(page.extract_text() or "" for page in pdf_reader.pages)
        if not text.strip():
            raise HTTPException(status_code=400, detail="The PDF file contains no readable text.")
        ai_tool = AIStudyTools(user_id=1)
        analysis_result = ai_tool.analyze_text(text)
        return JSONResponse({
            "summary": analysis_result.summary,
            "key_points": analysis_result.key_points,
            "status": "success"
        })
    except PyPDF2.errors.PdfReadError:
        raise HTTPException(status_code=400, detail="Invalid PDF format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Other Routes
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, current_user: models.User = Depends(require_auth), db: AsyncSession = Depends(get_async_session)):
    flashcard_progress = await crud.get_flashcard_progress(db, current_user.id)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "streak": current_user.streak,
        "flashcard_progress": [schemas.FlashcardProgressRead.from_orm(p) for p in flashcard_progress]
    })

@app.get("/ai-tools", response_class=HTMLResponse)
async def ai_tools_page(request: Request):
    return templates.TemplateResponse("ai_tools.html", {"request": request})

@app.get("/boss-battles", response_class=HTMLResponse)
async def boss_battles_page(request: Request):
    return templates.TemplateResponse("boss_battles.html", {"request": request})

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    return templates.TemplateResponse("inventory.html", {"request": request})

@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    return templates.TemplateResponse("leaderboard.html", {"request": request})

@app.get("/badges", response_class=HTMLResponse)
async def badge_page(request: Request):
    return templates.TemplateResponse("badge.html", {"request": request})

@app.get("/shop", response_class=HTMLResponse)
async def shop_page(request: Request, db: AsyncSession = Depends(get_async_session)):
    items = (await db.exec(select(models.Item))).all()
    return templates.TemplateResponse("shop.html", {"request": request, "items": items})

@app.get("/add-item", response_class=HTMLResponse)
async def add_item_form(request: Request):
    return templates.TemplateResponse("add_item.html", {"request": request})

@app.post("/add-item")
async def add_item(name: str = Form(...), description: str = Form(...), price: float = Form(...), image_url: str = Form(...), db: AsyncSession = Depends(get_async_session)):
    new_item = models.Item(name=name, description=description, price=price, image_url=image_url)
    db.add(new_item)
    await db.commit()
    return RedirectResponse(url="/shop", status_code=303)

@app.get("/add-to-cart/{item_id}")
async def add_to_cart(item_id: int):
    return RedirectResponse(url="/shop?message=added", status_code=303)

@app.get("/activity-feed")
async def get_activity_feed(current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    activities = [
        {"title": "Completed Quest: Study Math", "completed": True, "date": datetime.utcnow().isoformat()},
        {"title": "Studied Flashcards", "completed": True, "date": (datetime.utcnow() - timedelta(days=1)).isoformat()}
    ]
    return activities

@app.get("/overview", response_class=HTMLResponse)
async def get_overview(request: Request, current_user: Optional[models.User] = Depends(get_current_user)):
    return templates.TemplateResponse("overview.html", {"request": request, "current_user": current_user})

@app.post("/tests/create", response_model=schemas.TestCreate)
async def create_test(test: schemas.TestCreate, db: AsyncSession = Depends(get_async_session)):
    db_test = models.MaterialTestAttempt(**test.dict())
    db.add(db_test)
    await db.commit()
    await db.refresh(db_test)
    return db_test

@app.post("/tests/{test_id}/attempt", response_model=schemas.TestAttempt)
async def start_test_attempt(test_id: int, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    test = (await db.exec(select(models.MaterialTestAttempt).filter(models.MaterialTestAttempt.id == test_id))).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    attempt = models.MaterialTestAttempt(test_id=test_id, user_id=current_user.id)
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt

@app.post("/tests/attempt/{attempt_id}/submit", response_model=schemas.TestResult)
async def submit_test_attempt(attempt_id: int, responses: schemas.TestResponses, db: AsyncSession = Depends(get_async_session), current_user: models.User = Depends(get_current_user)):
    attempt = (await db.exec(select(models.MaterialTestAttempt).filter_by(id=attempt_id, user_id=current_user.id))).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    test = (await db.exec(select(models.MaterialTestAttempt).filter_by(id=attempt.test_id))).first()
    if not test:
        raise HTTPException(status_code=404, detail="Associated test not found")
    correct_answers = {q.id: q.correct_option for q in json.loads(test.generated_questions)}
    user_answers = {item.question_id: item.answer for item in responses.responses}
    total = len(correct_answers)
    correct = sum(1 for qid, ans in user_answers.items() if correct_answers.get(qid) == ans)
    score = (correct / total) * 100 if total else 0.0
    result = models.TestResult(
        attempt_id=attempt_id,
        score=score,
        total_questions=total,
        correct_answers=correct,
        submitted_at=datetime.utcnow()
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    analytics = await crud.get_analytics_data(db, current_user.id, date.today(), date.today())
    await manager.broadcast(json.dumps({
        "type": "analytics_update",
        "analytics": schemas.UserAnalyticsResponse(
            start_date=date.today(),
            end_date=date.today(),
            daily_xp=analytics["daily_xp"],
            efficiency=analytics["efficiency"],
            nba_style=analytics["nba_style"]
        ).dict()
    }), f"analytics_{current_user.id}")
    return result

@app.post("/api/user-flashcards")
async def create_user_flashcard_api(user_flashcard: schemas.UserFlashcardCreate, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    await crud.create_user_flashcard(db, user_flashcard, current_user.id)
    await crud.record_user_activity(db, current_user.id)
    analytics = await crud.get_analytics_data(db, current_user.id, date.today(), date.today())
    await manager.broadcast(json.dumps({
        "type": "analytics_update",
        "analytics": schemas.UserAnalyticsResponse(
            start_date=date.today(),
            end_date=date.today(),
            daily_xp=analytics["daily_xp"],
            efficiency=analytics["efficiency"],
            nba_style=analytics["nba_style"]
        ).dict()
    }), f"analytics_{current_user.id}")
    return {"status": "success"}

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(user_router, prefix="/users", tags=["users"])
app.include_router(group_router, prefix="/groups", tags=["groups"])
app.include_router(quest_router, prefix="/quests", tags=["quests"])
app.include_router(skill_router, prefix="/skills", tags=["skills"])
app.include_router(battle_router, prefix="/battles", tags=["battles"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
app.include_router(ai_router, prefix="/ai", tags=["ai"])
app.include_router(flashcards_router, prefix="/flashcards", tags=["flashcards"])
app.include_router(memory_router, prefix="/memory_training", tags=["memory"])
app.include_router(pomodoro_router, prefix="/pomodoro", tags=["pomodoro"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000)