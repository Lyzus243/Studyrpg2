from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from typing import AsyncGenerator
from pathlib import Path
from app.crud import create_skill, create_item
from app.schemas import SkillCreate, ItemBase
from app.base import Base
from app import models
import logging
import os

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Updated database path
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR}/studyrpg.db?check_same_thread=False"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    logger.debug("Starting database initialization")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.create_all)

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            
            # Initialize skills
            skills = [
                SkillCreate(name="Focus Boost", description="Increases focus by 10%", cost=10),
                SkillCreate(name="Memory Master", description="Improves memory retention by 15%", cost=15),
                SkillCreate(name="Speed Learner", description="Reduces study time by 5%", cost=12)
            ]
            for skill in skills:
                result = await session.execute(
                    select(models.Skill).where(models.Skill.name == skill.name)
                )
                if not result.scalars().first():
                    await create_skill(session, skill)

            # Initialize items
            items = [
                ItemBase(name="Energy Drink", description="Boosts Pomodoro duration", price=5),
                ItemBase(name="Study Guide", description="Increases XP gain", price=8),
                ItemBase(name="Focus Amulet", description="Reduces distractions", price=10)
            ]
            for item in items:
                result = await session.execute(
                    select(models.Item).where(models.Item.name == item.name)
                )
                if not result.scalars().first():
                    await create_item(session, item)

        logger.info(f"Database initialized at {DATABASE_URL}")

    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
        raise

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Session error: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())