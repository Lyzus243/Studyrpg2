
from fastapi import APIRouter, Depends
from sqlmodel import Session
from crud import create_boss_battle, has_passed_boss
from schemas import BossBattleCreate
import json

boss_battles_router = APIRouter()

BOSS_BATTLES = [
    {"title": "Midterm Exam", "description": "A challenging exam", "difficulty": "medium", "reward_xp": 100, "reward_items": ["Book"]},
    {"title": "Final Boss: Comprehensive Test", "description": "The ultimate test", "difficulty": "hard", "reward_xp": 200, "reward_items": ["Trophy"]}
]

def get_db():
    from main import get_db
    return next(get_db())

def get_boss_battles():
    return BOSS_BATTLES

@boss_battles_router.post("/simulate")
async def simulate_boss_battle(battle_data: BossBattleCreate, db: Session = Depends(get_db)):
    battle = create_boss_battle(db, user_id=1, battle_data=battle_data.dict())
    battle.score = 80
    battle.passed = True
    battle.current_health = 0
    battle.max_health = 100
    battle.is_completed = True
    battle.is_active = False
    battle.reward_xp = battle_data.reward_xp
    battle.reward_items = json.dumps(battle_data.reward_items)
    db.add(battle)
    db.commit()
    db.refresh(battle)
    return battle
