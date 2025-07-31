from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user
from fastapi.templating import Jinja2Templates
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

boss_battles_router = APIRouter(prefix="", tags=["boss_battles"])
templates = Jinja2Templates(directory="templates")

@boss_battles_router.get("/", response_class=HTMLResponse)
async def get_boss_battles_page(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized access attempt to boss battles page")
            raise HTTPException(status_code=401, detail="Authentication required")
        battles = await crud.get_boss_battles(db, current_user.id)
        logger.info(f"Fetched {len(battles)} boss battles for user {current_user.id}")
        return templates.TemplateResponse(
            "boss_battles.html",
            {"request": request, "battles": battles, "user": current_user}
        )
    except Exception as e:
        logger.error(f"Error in get_boss_battles_page for user {current_user.id if current_user else 'unknown'}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch boss battles: {str(e)}")

@boss_battles_router.post("/", response_model=schemas.BossBattleRead)
async def create_boss_battle(
    battle: schemas.BossBattleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to create boss battle")
            raise HTTPException(status_code=401, detail="Authentication required")
        if battle.difficulty < 1 or battle.difficulty > 10:
            logger.warning(f"Invalid difficulty {battle.difficulty} for boss battle creation by user {current_user.id}")
            raise HTTPException(status_code=400, detail="Difficulty must be between 1 and 10")
        
        # Create battle directly
        new_battle = models.BossBattle(
            user_id=current_user.id,
            name=battle.name,
            difficulty=battle.difficulty,
            current_health=battle.max_health,
            max_health=battle.max_health,
            reward_xp=battle.reward_xp,
            reward_skill_points=battle.reward_skill_points,
            is_completed=False
        )
        
        db.add(new_battle)
        await db.commit()
        await db.refresh(new_battle)
        
        logger.info(f"Created boss battle {new_battle.id} for user {current_user.id}")
        return schemas.BossBattleRead.from_orm(new_battle)
    except Exception as e:
        logger.error(f"Error in create_boss_battle for user {current_user.id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create boss battle: {str(e)}")