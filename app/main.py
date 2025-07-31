from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jinja2 import TemplateNotFound
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from typing import List, Optional, Dict
from pathlib import Path
from jose import JWTError, jwt
from datetime import datetime, timedelta
from app.init_db import init_db, get_async_session
from app.routers import auth, user,leveling_router, quests, pomodoro, memory_training, shop, flashcard, study_group, group_boss_battles, boss_battles, skills, ai, analytics
from app.connection_manager import ConnectionManager
from app import models
import logging
import os
import json
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secure-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
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
            logger.debug(f"Incoming request: {request.method} {request.url}")
            response = await call_next(request)
            logger.debug(f"Response status: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Request processing failed: {str(e)}")
            raise

app.add_middleware(DebugMiddleware)

# Path configuration
BASE_DIR = Path(__file__).parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Connection manager
manager = ConnectionManager()

# Auth dependencies - FIXED VERSION

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
) -> models.User:
    """Get current authenticated user with improved error handling"""
    
    # Check if credentials exist
    if not credentials:
        logger.error("No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token exists and is not empty/undefined
    token = credentials.credentials
    if not token or token in ["undefined", "null", ""]:
        logger.error(f"Invalid token received: {token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        logger.debug(f"Validating token: {token[:20]}...")
        
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            logger.error("No username found in token payload")
            raise credentials_exception
        
        # Check token expiration
        expire = payload.get("exp")
        if expire is None:
            logger.error("No expiration time in token")
            raise credentials_exception
            
        current_time = datetime.utcnow()
        expire_time = datetime.utcfromtimestamp(expire)
        
        if current_time > expire_time:
            logger.error(f"Token expired: {expire_time} < {current_time}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        logger.debug(f"Looking up user: {username}")
        
    except JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise credentials_exception
    
    try:
        # Query user from database
        stmt = select(models.User).where(models.User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            logger.error(f"User not found in database: {username}")
            raise credentials_exception
        
        logger.debug(f"User authenticated successfully: {user.id}")
        return user
        
    except Exception as e:
        logger.error(f"Database error during user lookup: {str(e)}")
        await db.rollback()
        raise credentials_exception

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_session)
) -> models.User | None:
    """Optional authentication - returns None if not authenticated"""
    try:
        if not credentials:
            return None
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
    except Exception as e:
        logger.debug(f"Optional authentication failed: {str(e)}")
        return None
    
# Include routers
app.include_router(auth.auth_router, prefix="/api/auth")
app.include_router(user.user_router, prefix="/api/users")
app.include_router(quests.quests_router, prefix="/api/quests")
app.include_router(pomodoro.pomodoro_router, prefix="/api/pomodoro")
app.include_router(memory_training.memory_router, prefix="/api/memory")
app.include_router(shop.shop_router, prefix="/api/shop")
app.include_router(flashcard.flashcard_router, prefix="/api/flashcards")
app.include_router(study_group.study_groups_router, prefix="/api/groups")
app.include_router(group_boss_battles.group_boss_battles_router, prefix="/api/battles/group")
app.include_router(boss_battles.boss_battles_router, prefix="/api/battles")
app.include_router(skills.skills_router, prefix="/api/skills")
app.include_router(ai.ai_router, prefix="/api/ai")
app.include_router(analytics.analytics_router, prefix="/api/analytics")
app.include_router(leveling_router.leveling_router, prefix="/api/leveling")

# Core endpoints
@app.get("/", response_class=HTMLResponse)
async def get_root(
    request: Request,
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    try:
        template = "dashboard.html" if current_user else "intro.html"
        return templates.TemplateResponse(
            template,
            {"request": request, "user": current_user}
        )
    except TemplateNotFound as e:
        logger.error(f"Template not found: {str(e)}")
        raise HTTPException(status_code=404, detail="Template not found")

# Serve the leaderboard HTML page
@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    try:
        return templates.TemplateResponse(
            "leaderboard.html",
            {"request": request}
        )
    except TemplateNotFound as e:
        logger.error(f"Leaderboard template not found: {str(e)}")
        raise HTTPException(status_code=404, detail="Leaderboard template not found")


@app.get("/api/debug/db-test")
async def test_db(db: AsyncSession = Depends(get_async_session)):
    try:
        result = await db.execute(select(models.User).limit(1))
        user = result.scalar_one_or_none()
        return {"db_working": True, "user_found": user is not None}
    except Exception as e:
        return {"db_working": False, "error": str(e)}

# Fixed health check endpoint
@app.get("/api/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "operational",
        "api": "responsive"
    }

    try:
        # Get database session
        db = await get_async_session().__anext__()
        
        # Check database connectivity
        await db.execute(text("SELECT 1"))
        
        # Verify table access - it's OK if no users exist
        result = await db.execute(select(models.User).limit(1))
        if result.scalar_one_or_none() is None:
            logger.warning("Health check: Database accessible but no users found")
        
        logger.info("Health check passed successfully")
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        health_status.update({
            "status": "unhealthy",
            "error": str(e),
            "database": "unavailable",
            "api": "responsive"
        })
        return JSONResponse(
            content=health_status,
            status_code=503
        )
    
@app.get("/api/auth/verify")
async def verify_token(
    current_user: models.User = Depends(get_current_user)
):
    return {
        "valid": True,
        "user": {
            "username": current_user.username,
            "email": current_user.email,
            "id": current_user.id
        }
    }
    
@app.post("/api/debug/verify-token")
async def verify_token_debug(
    token: str,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return {"valid": False, "error": "No username in token"}
        
        expire = payload.get("exp")
        # FIXED: Use UTC conversion for expiration time
        if expire is None or datetime.utcnow() > datetime.utcfromtimestamp(expire):
            return {"valid": False, "error": "Token expired"}
            
        user = await db.execute(select(models.User).where(models.User.username == username))
        user = user.scalar_one_or_none()
        if user is None:
            return {"valid": False, "error": "User not found"}
            
        return {"valid": True, "user_id": user.id, "username": user.username}
        
    except JWTError as e:
        return {"valid": False, "error": str(e)}    




# Leaderboard API Route
@app.get("/api/leaderboard", response_model=List[Dict[str, str]])
async def get_leaderboard(
    db: AsyncSession = Depends(get_async_session),
    limit: int = 10
):
    result = await db.execute(
        select(
            models.User.username,
            models.User.experience_points,
            models.User.level
        )
        .order_by(models.User.experience_points.desc())
        .limit(limit)
    )
    leaderboard = [
        {
            "username": user.username,
            "xp": user.experience_points,
            "level": user.level,
            "rank": idx + 1
        }
        for idx, user in enumerate(result.all())
    ]
    return leaderboard

# WebSocket Endpoint
@app.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session)
):
    await websocket.accept()
    
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        user = await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            db
        )
        
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        await manager.connect(websocket, f"user_{user.id}")
        logger.info(f"WebSocket connected for user {user.id}")
        
        try:
            while True:
                data = await websocket.receive_json()
                # Broadcast leaderboard updates when requested
                if data.get("type") == "leaderboard_request":
                    leaderboard = await get_leaderboard(db)
                    await websocket.send_json({
                        "type": "leaderboard_update",
                        "data": leaderboard
                    })
                # Broadcast other user events
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
            logger.info(f"WebSocket disconnected for user {user.id}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON received via WebSocket")
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            
    except HTTPException as e:
        logger.error(f"WebSocket auth error: {str(e)}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except JWTError:
        logger.error("Invalid JWT in WebSocket connection")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info", 
        reload=True,
        timeout_keep_alive=60  # Added for WebSocket stability
    )