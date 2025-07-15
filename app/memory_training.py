from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Optional
from pydantic import BaseModel
from app.crud import create_memory_session, evaluate_memory_session
from app.auth import get_current_user
from app.models import User

memory_router = APIRouter(prefix="/memory_training", tags=["memory"])

MEMORY_EXERCISES = {
    "spaced_repetition": {
        "name": "Spaced Repetition",
        "description": "Answer questions with increasing intervals",
        "type": "text"
    },
    "active_recall": {
        "name": "Active Recall",
        "description": "Recall information without prompts",
        "type": "text"
    },
    "memory_palace": {
        "name": "Memory Palace",
        "description": "Visualize items in a familiar space",
        "type": "text"
    },
    "mnemonics": {
        "name": "Mnemonics",
        "description": "Use associations to remember",
        "type": "text"
    }
}

def get_db():
    from app.database import get_db
    return next(get_db())

# Pydantic schemas for request/response validation
class MemoryTrainingSessionCreate(BaseModel):
    user_id: int
    content: str
    score: int
    is_ai_generated: bool

class MemoryTrainingSessionEvaluate(BaseModel):
    session_id: int
    response: str

class MemoryTrainingSessionResponse(BaseModel):
    session_id: int
    content: str
    type: str

class MemoryTrainingEvaluationResponse(BaseModel):
    session_id: int
    score: int
    feedback: str

@memory_router.get("/exercises", response_model=MemoryTrainingSessionResponse)
async def get_memory_exercises(technique: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if technique not in MEMORY_EXERCISES:
        raise HTTPException(status_code=400, detail="Invalid technique")
    exercise = MEMORY_EXERCISES[technique]
    content = f"Sample {exercise['name']} exercise: Recall the sequence 3, 7, 2, 9"
    session = create_memory_session(db, user_id=current_user.id, content=content, score=0, is_ai_generated=True)
    return MemoryTrainingSessionResponse(
        session_id=session.id,
        content=content,
        type=exercise["name"]
    )

@memory_router.post("/evaluate", response_model=MemoryTrainingEvaluationResponse)
async def evaluate_memory_exercise(data: MemoryTrainingSessionEvaluate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(MemoryTrainingSessionCreate, data.session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found or not authorized")
    # Placeholder scoring logic (replace with actual logic as needed)
    score = len(data.response) if data.response else 0
    session = evaluate_memory_session(db, data.session_id, score)
    return MemoryTrainingEvaluationResponse(
        session_id=session.id,
        score=score,
        feedback="Good effort!"
    )