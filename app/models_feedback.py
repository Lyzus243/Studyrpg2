"""
Separate Feedback model to avoid rewriting your entire app/models.py.
If you prefer, copy this class into app/models.py and delete this file,
then update imports accordingly.
"""

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
import datetime

# IMPORTANT:
# Use the same Base as your main models to ensure proper table creation
from app.models import Base

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)  # Changed to nullable=True to match migration
    email = Column(String, nullable=True)  # Changed to nullable=True to match migration
    category = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)