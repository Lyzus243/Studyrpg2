from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel

# Database URL consistent with init_db.py, main.py, flashcard.py
DATABASE_URL = "sqlite+aiosqlite:///studyrpg.db"

# Async engine for SQLite
engine = create_async_engine(DATABASE_URL, echo=True)

# SQLModel base class
Base = SQLModel

# Async session dependency
async def get_async_session():
    async with AsyncSession(engine) as session:
        yield session