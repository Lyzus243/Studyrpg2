# init_db.py
import sys
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import models
from app import models

async def initialize_database():
    """Initialize the database by creating all tables."""
    # Replace with your database URL (e.g., PostgreSQL, MySQL)
    engine = create_async_engine("sqlite+aiosqlite:///studyrpg.db", echo=True)
    
    print("📋 Tables registered in metadata:")
    for table_name in SQLModel.metadata.tables.keys():
        print(f" - {table_name}")
    
    async with engine.begin() as conn:
        # Optional: Drop tables for clean init (remove in production)
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    print("✅ Database tables created.")

if __name__ == "__main__":
    asyncio.run(initialize_database())