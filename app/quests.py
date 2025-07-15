from typing import List, Dict
from datetime import datetime, timedelta

# Example quest templates
QUEST_TEMPLATES = [
    {"title": "Read a chapter of your textbook", "description": "Complete one chapter.", "xp_reward": 10, "quest_type": "daily"},
    {"title": "Take notes for 1 hour", "description": "Focus on note-taking.", "xp_reward": 15, "quest_type": "daily"},
    {"title": "Solve 5 practice problems", "description": "Practice problem-solving.", "xp_reward": 20, "quest_type": "daily"},
    {"title": "Review and summarize key concepts", "description": "Summarize what you learned.", "xp_reward": 15, "quest_type": "daily"},
    {"title": "Complete a practice exam", "description": "Test your knowledge.", "xp_reward": 50, "quest_type": "weekly"},
    {"title": "Attend a study group session", "description": "Collaborate with peers.", "xp_reward": 30, "quest_type": "weekly"},
    {"title": "Write a summary essay on a topic", "description": "Deepen your understanding.", "xp_reward": 40, "quest_type": "weekly"},
    {"title": "Create a mind map of the chapter", "description": "Visualize your learning.", "xp_reward": 25, "quest_type": "weekly"},
    {"title": "Finish a course module", "description": "Complete all lessons in a module.", "xp_reward": 100, "quest_type": "monthly"},
    {"title": "Present a topic to a peer group", "description": "Teach others.", "xp_reward": 75, "quest_type": "monthly"},
    {"title": "Achieve a high score on a major test", "description": "Score above 90%.", "xp_reward": 150, "quest_type": "monthly"},
    {"title": "Create a comprehensive study guide", "description": "Summarize the whole module.", "xp_reward": 90, "quest_type": "monthly"},
]

def get_quest_templates(quest_type: str = None) -> List[Dict]:
    if quest_type:
        return [q for q in QUEST_TEMPLATES if q["quest_type"] == quest_type]
    return QUEST_TEMPLATES

def calculate_xp_for_quest(quest: Dict) -> int:
    # XP is defined in the template, but you can add logic for bonuses here
    return quest.get("xp_reward", 0)

def assign_daily_quests(user_id: int, db_crud, db_session):
    # Assigns all daily quests to a user for today if not already assigned
    today = datetime.utcnow().date()
    assigned = []
    for quest in get_quest_templates("daily"):
        # Check if quest already assigned today
        existing = db_crud.get_quests(db_session, user_id, quest_type="daily")
        if not any(q.title == quest["title"] and q.date_assigned.date() == today for q in existing):
            db_crud.create_quest(db_session, quest, user_id)
            assigned.append(quest["title"])
    return assigned

def assign_weekly_quests(user_id: int, db_crud, db_session):
    # Assigns all weekly quests to a user for the current week if not already assigned
    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())
    assigned = []
    for quest in get_quest_templates("weekly"):
        existing = db_crud.get_quests(db_session, user_id, quest_type="weekly")
        if not any(q.title == quest["title"] and q.date_assigned >= week_start for q in existing):
            db_crud.create_quest(db_session, quest, user_id)
            assigned.append(quest["title"])
    return assigned

def assign_monthly_quests(user_id: int, db_crud, db_session):
    # Assigns all monthly quests to a user for the current month if not already assigned
    now = datetime.utcnow()
    month_start = now.replace(day=1)
    assigned = []
    for quest in get_quest_templates("monthly"):
        existing = db_crud.get_quests(db_session, user_id, quest_type="monthly")
        if not any(q.title == quest["title"] and q.date_assigned >= month_start for q in existing):
            db_crud.create_quest(db_session, quest, user_id)
            assigned.append(quest["title"])
    return assigned