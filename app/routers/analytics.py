from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, timedelta
from typing import Dict, Any
import csv
import io
from app import models, schemas
from app.database import get_async_session
from app.auth_deps import get_current_user
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])

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
        daily_sessions = {str(row.date): row.session_count for row in pomodoro_data}
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

        # Daily quest completion stats
        daily_quest_result = await db.execute(
            select(
                func.date(models.Quest.completed_at).label("date"),
                func.count(models.Quest.id).label("quest_count"),
                func.sum(models.Quest.reward_xp).label("quest_xp")
            )
            .where(
                models.Quest.user_id == user_id,
                models.Quest.is_completed == True,
                models.Quest.completed_at >= start_date,
                models.Quest.completed_at <= end_date
            )
            .group_by(func.date(models.Quest.completed_at))
        )
        daily_quest_data = daily_quest_result.all()
        daily_quest_completions = {str(row.date): row.quest_count for row in daily_quest_data}
        daily_quest_xp = {str(row.date): row.quest_xp or 0 for row in daily_quest_data}

        return {
            "daily_xp": daily_xp,
            "daily_sessions": daily_sessions,
            "daily_quest_completions": daily_quest_completions,
            "daily_quest_xp": daily_quest_xp,
            "total_xp": total_quest_xp + total_minutes,
            "total_quest_xp": total_quest_xp,
            "total_pomodoro_minutes": total_minutes,
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

async def prepare_csv_data(db: AsyncSession, user_id: int, start_date: date, end_date: date) -> list:
    """Prepare detailed analytics data for CSV export"""
    analytics_data = await get_analytics_data(db, user_id, start_date, end_date)
    
    # Create a comprehensive daily breakdown
    csv_data = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = str(current_date)
        
        # Get data for this date
        pomodoro_sessions = analytics_data["daily_sessions"].get(date_str, 0)
        pomodoro_minutes = analytics_data["daily_xp"].get(date_str, 0)
        quest_completions = analytics_data["daily_quest_completions"].get(date_str, 0)
        quest_xp = analytics_data["daily_quest_xp"].get(date_str, 0)
        total_daily_xp = pomodoro_minutes + quest_xp
        
        csv_data.append({
            "Date": date_str,
            "Pomodoro Sessions": pomodoro_sessions,
            "Pomodoro Minutes": pomodoro_minutes,
            "Quest Completions": quest_completions,
            "Quest XP": quest_xp,
            "Total Daily XP": total_daily_xp,
            "Avg Session Length": round(pomodoro_minutes / max(1, pomodoro_sessions), 2) if pomodoro_sessions > 0 else 0
        })
        
        current_date += timedelta(days=1)
    
    return csv_data

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
        analytics_data = await get_analytics_data(db, current_user.username, start_date, end_date)
        
        quest_result = await db.execute(
            select(models.Quest).where(
                models.Quest.user_id == current_user.username,
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
            total_pomodoro_minutes=analytics_data["total_pomodoro_minutes"],
            total_quests_completed=total_quests_completed,
            total_xp_earned=analytics_data["total_xp"],
            average_pomodoro_duration=analytics_data["nba_style"]["avg_session_length"],
            daily_xp=analytics_data["daily_xp"]  # Add this to your schema
        )
    except Exception as e:
        logger.error(f"Error fetching analytics for user {current_user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")

@analytics_router.get("/download")
async def download_analytics_csv(
    range: schemas.AnalyticsTimeRange = Depends(),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    """Download analytics data as CSV file"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        start_date = range.start_date or date.today() - timedelta(days=30)
        end_date = range.end_date or date.today()
        
        # Get CSV data
        csv_data = await prepare_csv_data(db, current_user.username, start_date, end_date)
        
        if not csv_data:
            raise HTTPException(status_code=404, detail="No data found for the specified date range")
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=csv_data[0].keys())
        writer.writeheader()
        writer.writerows(csv_data)
        
        # Prepare response
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename
        filename = f"studyrpg_analytics_{start_date}_to_{end_date}.csv"
        
        # Return CSV as streaming response
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error generating CSV for user {current_user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV: {str(e)}")

@analytics_router.get("/summary")
async def get_analytics_summary(
    range: schemas.AnalyticsTimeRange = Depends(),
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    """Get a detailed analytics summary including daily breakdown"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        start_date = range.start_date or date.today() - timedelta(days=30)
        end_date = range.end_date or date.today()
        analytics_data = await get_analytics_data(db, current_user.username, start_date, end_date)
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "summary": {
                "total_pomodoro_sessions": analytics_data["nba_style"]["total_sessions"],
                "total_pomodoro_minutes": analytics_data["total_pomodoro_minutes"],
                "total_quest_xp": analytics_data["total_quest_xp"],
                "total_xp_earned": analytics_data["total_xp"],
                "average_pomodoro_duration": analytics_data["nba_style"]["avg_session_length"],
                "consistency_score": analytics_data["nba_style"]["consistency"],
                "efficiency_score": analytics_data["efficiency"]
            },
            "daily_breakdown": {
                "daily_xp": analytics_data["daily_xp"],
                "daily_sessions": analytics_data["daily_sessions"],
                "daily_quest_completions": analytics_data["daily_quest_completions"],
                "daily_quest_xp": analytics_data["daily_quest_xp"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching detailed analytics for user {current_user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch detailed analytics: {str(e)}")