from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from typing import List
import pandas as pd

from . import models


# === XP Over Time ===
def xp_progress_over_time(quests, days: int = 30) -> pd.DataFrame:
    """
    Returns a DataFrame showing XP earned per day over the last `days` days.
    """
    today = datetime.utcnow().date()
    data = []

    for i in range(days):
        day = today - timedelta(days=i)
        xp = sum(q.xp_reward for q in quests if q.completed and q.date_assigned.date() == day)
        data.append({"date": day, "xp": xp})

    df = pd.DataFrame(data)
    df.sort_values("date", inplace=True)
    return df


# === Study Streak Counter ===
def study_streak_counter(quests) -> int:
    """
    Returns the current study streak — consecutive days with at least one completed quest.
    """
    today = datetime.utcnow().date()
    streak = 0

    for i in range(100):  # Search back up to 100 days
        day = today - timedelta(days=i)
        if any(q.completed and q.date_assigned.date() == day for q in quests):
            streak += 1
        else:
            break

    return streak


# === Leaderboard ===
def leaderboard(users) -> List:
    """
    Returns a sorted list of users by XP, descending.
    """
    return sorted(users, key=lambda u: u.xp, reverse=True)


# === NBA-Style Stats ===
def nba_style_stats(users) -> pd.DataFrame:
    """
    Returns a DataFrame with detailed stats per user: XP, level, streak, skills.
    """
    data = []

    for u in users:
        data.append({
            "Username": u.username,
            "XP": u.xp,
            "Level": u.level,
            "Streak": getattr(u, "streak", 0),
            "Memory": getattr(u, "memory", 0),
            "Focus": getattr(u, "focus", 0),
            "Comprehension": getattr(u, "comprehension", 0),
            "Speed": getattr(u, "speed", 0),
        })

    df = pd.DataFrame(data)
    df.sort_values("XP", ascending=False, inplace=True)
    return df


# === Heatmap Data (for activity) ===
def generate_heatmap_data(db: Session, user_id: int, days: int = 30) -> List[List[int]]:
    """
    Generate heatmap-compatible data for the user's XP activity over time.
    Returns a list of [weekday (0–6), day_offset (0 = today), xp].
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    records = db.query(models.UserAnalytics)\
                .filter(
                    models.UserAnalytics.user_id == user_id,
                    models.UserAnalytics.date.between(start_date, end_date)
                ).all()

    heatmap = []
    for record in records:
        xp = record.metrics.get("xp_earned", 0)
        if xp > 0:
            day_offset = (end_date - record.date).days
            weekday = record.date.weekday()  # 0 = Monday, 6 = Sunday
            heatmap.append([weekday, day_offset, xp])

    return heatmap
