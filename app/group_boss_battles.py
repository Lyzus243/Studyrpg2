from fastapi import APIRouter, Depends, WebSocket, HTTPException, WebSocketDisconnect
from sqlmodel import Session, select
from app.schemas import GroupBossBattleCreate, GroupBossBattleRead
from app.crud import create_group_boss_battle, get_user
from app.models import GroupBossBattle, UserGroupBossBattle, User
from main import get_db, get_current_user, ConnectionManager
from typing import Dict
import json

group_boss_battles_router = APIRouter(prefix="/group_boss_battles", tags=["group_boss_battles"])

manager = ConnectionManager()

@group_boss_battles_router.post("/start", response_model=GroupBossBattleRead)
async def start_group_boss_battle(battle_data: GroupBossBattleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.execute(select(GroupBossBattle.group).where(GroupBossBattle.group_id == battle_data.group_id, GroupBossBattle.group.members.any(id=current_user.id))).first()
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized to start battle in this group")
    battle = create_group_boss_battle(db, battle_data, battle_data.group_id, current_user.id)
    link = UserGroupBossBattle(user_id=current_user.id, group_boss_battle_id=battle.id)
    db.add(link)
    db.commit()
    return GroupBossBattleRead.from_orm(battle)

@group_boss_battles_router.post("/action", response_model=GroupBossBattleRead)
async def perform_battle_action(action: Dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    battle_id = action.get("battle_id")
    action_type = action.get("type")
    user_id = current_user.id
    battle = db.get(GroupBossBattle, battle_id)
    if not battle or not battle.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive battle")
    
    link = db.execute(select(UserGroupBossBattle).where(UserGroupBossBattle.group_boss_battle_id == battle_id, UserGroupBossBattle.user_id == user_id)).first()
    if not link:
        link = UserGroupBossBattle(user_id=user_id, group_boss_battle_id=battle_id)
        db.add(link)
    
    if action_type == "attack":
        damage = 50
        battle.current_health -= damage
    elif action_type == "special":
        damage = 120
        battle.current_health -= damage
    elif action_type == "heal":
        battle.group_health += 50
    
    if battle.current_health <= 0:
        battle.is_completed = True
        battle.is_active = False
        battle.passed = True
        battle.score = 100
        battle.reward_xp = 250
        battle.reward_skill_points = 5
        battle.reward_items = json.dumps(["Dragon Scale", "Code Fragment"])
    
    db.add(battle)
    db.commit()
    db.refresh(battle)
    
    await manager.broadcast_to_group(
        json.dumps({"type": "battle_state", "battle": GroupBossBattleRead.from_orm(battle).dict()}),
        f"battle_{battle_id}"
    )
    return GroupBossBattleRead.from_orm(battle)

@group_boss_battles_router.websocket("/ws/{battle_id}/battle")
async def websocket_battle(websocket: WebSocket, battle_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    battle = db.get(GroupBossBattle, battle_id)
    if not battle or not battle.is_active:
        await websocket.close(code=1008)
        return
    group = db.execute(select(GroupBossBattle.group).where(GroupBossBattle.group_id == battle.group_id, GroupBossBattle.group.members.any(id=current_user.id))).first()
    if not group:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket, f"battle_{battle_id}")
    try:
        while True:
            data = await websocket.receive_text()
            action = json.loads(data)
            action["battle_id"] = battle_id
            action["user_id"] = current_user.id
            result = await perform_battle_action(action, current_user, db)
            await manager.broadcast_to_group(
                json.dumps({"type": "battle_state", "battle": result.dict()}),
                f"battle_{battle_id}"
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"battle_{battle_id}")
    except Exception as e:
        await websocket.close(code=1008)
        raise HTTPException(status_code=500, detail=f"WebSocket error: {str(e)}")
