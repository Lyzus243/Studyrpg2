from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from pathlib import Path
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
        from app import models
        async with engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
        
        logger.info(f"Database initialized at {DATABASE_URL}")
        if not os.path.exists(f"{BASE_DIR}/studyrpg.db"):
            logger.warning("Database file not created!")
        
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