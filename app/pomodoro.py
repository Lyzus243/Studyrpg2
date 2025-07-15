# app/pomodoro.py
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List
from app.models import PomodoroSession, User
from app.schemas import PomodoroSessionCreate, PomodoroSessionRead
from app.auth import get_current_user
from app.crud import create_pomodoro_session, get_pomodoro_history, get_todays_stats
from app.database import get_async_session

pomodoro_router = APIRouter(prefix="/pomodoro", tags=["pomodoro"])

class PomodoroTimer:
    def __init__(self, work_minutes=25, break_minutes=5, cycles=4):
        self.work_minutes = work_minutes
        self.break_minutes = break_minutes
        self.cycles = cycles
        self.current_cycle = 0
        self.is_running = False
        self.session_log = []

    def start(self):
        self.is_running = True
        for cycle in range(self.cycles):
            self.current_cycle = cycle + 1
            print(f"Cycle {self.current_cycle}: Work for {self.work_minutes} minutes.")
            self._countdown(self.work_minutes)
            print("Time for a break!")
            self._countdown(self.break_minutes)
            self.session_log.append({
                "cycle": self.current_cycle,
                "work_minutes": self.work_minutes,
                "break_minutes": self.break_minutes,
                "timestamp": datetime.utcnow()
            })
        self.is_running = False
        print("Pomodoro session complete!")

    def _countdown(self, minutes):
        # For real use, replace with time.sleep(minutes * 60)
        # For demo/testing, use a short sleep
        for i in range(minutes, 0, -1):
            print(f"{i} minute(s) remaining...")
            time.sleep(1)  # Simulate 1 minute with 1 second for demo

    def get_log(self):
        return self.session_log

def calculate_flashcard_coverage(total_flashcards: int, completed_flashcards: int) -> float:
    if total_flashcards == 0:
        return 0.0
    return (completed_flashcards / total_flashcards) * 100

def pomodoro_xp_bonus(session_count: int) -> int:
    # Award bonus XP for completed pomodoro sessions
    return session_count * 5  # Example: 5 XP per session

@pomodoro_router.post("/sessions", response_model=PomodoroSessionRead)
async def create_pomodoro_session(
    session_data: PomodoroSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Create a new Pomodoro session for the authenticated user.
    """
    session = await create_pomodoro_session(db, current_user.id, session_data.duration)
    return PomodoroSessionRead.from_orm(session)

@pomodoro_router.get("/stats", response_model=dict)
async def get_pomodoro_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get Pomodoro stats for the authenticated user (today's sessions).
    """
    stats = await get_todays_stats(db, current_user.id)
    return stats

@pomodoro_router.get("/history", response_model=List[PomodoroSessionRead])
async def get_pomodoro_history(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get Pomodoro session history for the authenticated user.
    """
    history = await get_pomodoro_history(db, current_user.id)
    # Filter by days if needed
    start_date = datetime.utcnow() - timedelta(days=days)
    filtered_history = [
        PomodoroSessionRead.from_orm(session)
        for session in history
        if session.start_time >= start_date
    ]
    return filtered_history