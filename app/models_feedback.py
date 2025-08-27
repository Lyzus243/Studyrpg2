"""
Separate Feedback model to avoid rewriting your entire app/models.py.
If you prefer, copy this class into app/models.py and delete this file,
then update imports accordingly.
"""

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
import datetime

# IMPORTANT:
# If your project already defines a canonical Base in app/models.py,
# you can import it instead of creating a new one here:
#
# from app.models import Base
#
# And then DELETE the Base = declarative_base() below.

Base = declarative_base()  # <-- Replace with "from app.models import Base" if available

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    category = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)
