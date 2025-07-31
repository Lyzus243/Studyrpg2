from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, timedelta
from typing import Dict, Any
from app import models, schemas
from app.database import get_async_session
from app.auth_deps import get_current_user
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="", tags=["analytics"])

async def get_analytics_data(db: AsyncSession, user_id: int, start_date: date, end_date: date) -> Dict[str, Any]:
    try:
        if start_date > end_date:
            logger.warning(f"Invalid date range: start_date {start_date} is after end_date {end_date}")
            raise ValueError("start_date cannot be after end_date")

        # Query Pomodoro session stats
        pomodoro_result = await db.execute(
            select(
                func.date(models.PomodoroSession.start_time).label("date"),
                func.sum(models.PomodoroSession.duration).label("xp"),
                func.count(models.PomodoroSession.id).label("session_count")
            )
            .where(
                models.PomodoroSession.user_id == user_id,
                models.PomodoroSession.start_time >= start_date,
                models.PomodoroSession.start_time <= end_date,
                models.PomodoroSession.is_completed == True
            )
            .group_by(func.date(models.PomodoroSession.start_time))
        )
        pomodoro_data = pomodoro_result.all()

        daily_xp = {str(row.date): row.xp or 0 for row in pomodoro_data}
        total_sessions = sum(row.session_count for row in pomodoro_data)
        total_minutes = sum(row.xp or 0 for row in pomodoro_data)

        # Calculate efficiency
        days_in_range = (end_date - start_date).days + 1
        efficiency = total_minutes / max(1, days_in_range)

        # NBA-style analytics
        consistency = len([v for v in daily_xp.values() if v > 0]) / max(1, days_in_range)
        avg_session_length = total_minutes / max(1, total_sessions)

        # Quest completion stats
        quest_result = await db.execute(
            select(func.sum(models.Quest.reward_xp))
            .where(
                models.Quest.user_id == user_id,
                models.Quest.is_completed == True,
                models.Quest.completed_at >= start_date,
                models.Quest.completed_at <= end_date
            )
        )
        total_quest_xp = quest_result.scalar() or 0

        return {
            "daily_xp": daily_xp,
            "total_xp": total_quest_xp + total_minutes,
            "efficiency": round(efficiency, 2),
            "nba_style": {
                "consistency": round(consistency, 2),
                "avg_session_length": round(avg_session_length, 2),
                "total_sessions": total_sessions
            }
        }
    except Exception as e:
        logger.error(f"Error in get_analytics_data for user {user_id}: {str(e)}")
        raise ValueError(f"Failed to retrieve analytics data: {str(e)}")

@analytics_router.get("", response_model=schemas.UserAnalyticsResponse)
async def get_analytics(
    range: schemas.AnalyticsTimeRange = Depends(),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        start_date = range.start_date or date.today() - timedelta(days=30)
        end_date = range.end_date or date.today()
        analytics_data = await get_analytics_data(db, current_user.id, start_date, end_date)
        quest_result = await db.execute(
            select(models.Quest).where(
                models.Quest.user_id == current_user.id,
                models.Quest.is_completed == True,
                models.Quest.completed_at >= start_date,
                models.Quest.completed_at <= end_date
            )
        )
        total_quests_completed = len(quest_result.scalars().all())
        return schemas.UserAnalyticsResponse(
            start_date=start_date,
            end_date=end_date,
            compare=range.compare,
            total_pomodoro_sessions=analytics_data["nba_style"]["total_sessions"],
            total_pomodoro_minutes=analytics_data["total_xp"],
            total_quests_completed=total_quests_completed,
            total_xp_earned=analytics_data["total_xp"],
            average_pomodoro_duration=analytics_data["nba_style"]["avg_session_length"]
        )
    except Exception as e:
        logger.error(f"Error fetching analytics for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")