from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app import models, schemas
from app.database import get_async_session
from app.auth_deps import get_current_user_optional
from sqlalchemy import select
import asyncio
import logging
import os
import uuid
import openai
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ai_router = APIRouter(prefix="", tags=["ai"])

# Initialize OpenAI client safely
openai_client = None
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        openai_client = openai.AsyncClient(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
    else:
        logger.error("OPENAI_API_KEY environment variable is not set. AI features will be disabled.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    openai_client = None

# Configure upload directory
UPLOAD_DIR = "uploads/materials"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class MaterialBase(BaseModel):
    title: str
    description: Optional[str] = None

class MaterialCreate(MaterialBase):
    pass

class Material(MaterialBase):
    id: int
    user_id: str
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    created_at: datetime
    
    class Config:
        orm_mode = True

class AnalysisResult(BaseModel):
    summary: str
    key_points: List[str]

class AIStudyTools:
    def __init__(self, user_id: str, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.openai_client = openai_client

    async def _generate_question(self, content: str) -> Optional[Dict[str, Any]]:
        """Generate a single question using OpenAI"""
        if not self.openai_client:
            logger.error("Cannot generate question - OpenAI client not initialized")
            return None
            
        try:
            prompt = (
                "Generate a multiple-choice question with 4 options based on the following text. "
                "Format the response as: Question: [question]? | Option A: [A] | Option B: [B] | "
                "Option C: [C] | Option D: [D] | Correct Answer: [correct letter]\n\n"
                f"Text: {content[:512]}"
            )

            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful study assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            generated_text = response.choices[0].message.content.strip()
            parts = generated_text.split("|")
            
            if len(parts) < 5:
                return None
                
            question_text = parts[0].split("Question:", 1)[-1].strip().rstrip('?') + '?'
            options = [opt.split(":", 1)[-1].strip() for opt in parts[1:5]]
            correct_letter = parts[5].split(":", 1)[-1].strip()
            
            # Map letter to option index
            letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            correct_idx = letter_map.get(correct_letter.upper())
            
            if correct_idx is None or correct_idx >= len(options):
                return None
                
            return {
                "question": question_text,
                "options": options,
                "correct_option": options[correct_idx]
            }
            
        except Exception as e:
            logger.error(f"OpenAI question generation error: {str(e)}")
            return None

    async def generate_timed_test(self, material_id: int, duration: int) -> Dict[str, Any]:
        if not self.openai_client:
            raise HTTPException(
                status_code=503, 
                detail="AI service unavailable - OpenAI API key not configured"
            )
            
        try:
            material = await self.db.execute(
                select(models.Material).where(
                    models.Material.id == material_id,
                    models.Material.user_id == self.user_id
                )
            )
            material = material.scalar_one_or_none()
            if not material:
                raise HTTPException(status_code=404, detail="Material not found or not accessible")

            content = material.content
            questions = []
            tasks = []

            # Create question generation tasks
            for i in range(3):
                task = asyncio.create_task(self._generate_question(content))
                tasks.append(task)

            # Process results with timeout
            for i, task in enumerate(tasks):
                try:
                    question = await asyncio.wait_for(task, timeout=15.0)
                    if question:
                        questions.append({
                            "id": i + 1,
                            "question": question["question"],
                            "options": question["options"],
                            "correct_option": question["correct_option"]
                        })
                except asyncio.TimeoutError:
                    logger.warning(f"Question {i+1} generation timed out")
                except Exception as e:
                    logger.error(f"Error generating question {i+1}: {str(e)}")

            if not questions:
                raise HTTPException(status_code=500, detail="Failed to generate any valid questions")

            return {
                "questions": questions,
                "time_limit": duration,
                "instructions": f"Complete the {len(questions)} questions within {duration} minutes."
            }
        except Exception as e:
            logger.error(f"Error in generate_timed_test: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to generate timed test: {str(e)}")

    async def generate_practice_test(self, material_id: int) -> List[Dict]:
        """Reuse timed test generation but return only questions"""
        if not self.openai_client:
            raise HTTPException(
                status_code=503, 
                detail="AI service unavailable - OpenAI API key not configured"
            )
        test = await self.generate_timed_test(material_id, duration=0)
        return test["questions"]

    async def get_study_recommendations(self) -> List[str]:
        try:
            sessions = await self.db.execute(
                select(models.PomodoroSession).where(
                    models.PomodoroSession.user_id == self.user_id,
                    models.PomodoroSession.is_completed == True
                )
            )
            user = await self.db.get(models.User, self.user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if user.xp < 100:
                return ["Focus on foundational concepts with short study sessions"]

            sessions = sessions.scalars().all()
            test_results = await self.db.execute(
                select(models.TestResult).where(models.TestResult.user_id == self.user_id)
            )
            test_results = test_results.scalars().all()

            total_minutes = sum(session.duration for session in sessions)
            session_count = len(sessions)
            avg_score = sum(result.score for result in test_results) / max(1, len(test_results))

            recommendations = []
            if session_count < 5:
                recommendations.append("Increase study frequency with 25-minute Pomodoro sessions.")
            if total_minutes < 300:
                recommendations.append("Aim for at least 300 minutes of focused study per week.")
            if avg_score < 70:
                recommendations.append("Review weak areas in practice tests to improve scores.")
            else:
                recommendations.append("Continue with challenging material to maintain progress.")

            return recommendations or ["Start with short 25-minute study sessions to build momentum."]
        except Exception as e:
            logger.error(f"Error in get_study_recommendations: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")

    async def analyze_text(self, text: str) -> AnalysisResult:
        if not self.openai_client:
            raise ValueError("AI service unavailable - OpenAI API key not configured")
            
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful study assistant."},
                    {"role": "user", "content": f"Summarize this text and extract 3 key points:\n\n{text[:2000]}"}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse the response
            parts = result_text.split("Key Points:")
            summary = parts[0].replace("Summary:", "").strip()
            key_points = []
            
            if len(parts) > 1:
                key_points = [
                    kp.strip() 
                    for kp in parts[1].split("\n") 
                    if kp.strip() and kp.strip()[0].isdigit()
                ][:3]
            
            if not key_points:
                # Fallback if parsing fails
                key_points = [f"Key point {i+1}" for i in range(3)]
                
            return AnalysisResult(summary=summary, key_points=key_points)
            
        except Exception as e:
            logger.error(f"OpenAI text analysis error: {str(e)}")
            raise ValueError(f"Failed to analyze text: {str(e)}")

    async def analyze_material(self, material_id: int) -> AnalysisResult:
        # Get material from database
        result = await self.db.execute(
            select(models.Material)
            .where(
                models.Material.id == material_id,
                models.Material.user_id == self.user_id
            )
        )
        material = result.scalars().first()
        
        if not material:
            raise ValueError("Material not found or not accessible")
        
        if not material.content:
            raise ValueError("Material has no text content for analysis")
        
        return await self.analyze_text(material.content)

@ai_router.post("/test/timed", response_model=Dict)
async def generate_timed_test(
    request: schemas.TestGenerationRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        ai_tools = AIStudyTools(current_user.id, db)
        result = await ai_tools.generate_timed_test(request.material_id, request.duration)
        return result
    except Exception as e:
        # Handle the specific service unavailable error
        if "AI service unavailable" in str(e):
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate timed test: {str(e)}")

@ai_router.post("/test/practice", response_model=List[Dict])
async def generate_practice_test(
    material_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        ai_tools = AIStudyTools(current_user.id, db)
        return await ai_tools.generate_practice_test(material_id)
    except Exception as e:
        # Handle the specific service unavailable error
        if "AI service unavailable" in str(e):
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate practice test: {str(e)}")

@ai_router.post("/recommendations", response_model=List[str])
async def get_recommendations(
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        ai_tools = AIStudyTools(current_user.id, db)
        return await ai_tools.get_study_recommendations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")
    
@ai_router.post("/materials/", response_model=Material)
async def create_material(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    # Generate unique filename
    file_ext = file.filename.split('.')[-1]
    file_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    file_type = file.content_type
    
    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # For text files, extract content
    material_content = None
    if file_type.startswith("text/"):
        try:
            material_content = content.decode("utf-8")
        except:
            material_content = None
    
    # Create material in database
    db_material = models.Material(
        user_id=current_user.id,
        title=title,
        description=description,
        file_path=file_path,
        file_type=file_type,
        content=material_content,
        created_at=datetime.utcnow()
    )
    
    db.add(db_material)
    await db.commit()
    await db.refresh(db_material)
    return db_material

@ai_router.get("/materials/", response_model=List[Material])
async def read_materials(
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = await db.execute(
        select(models.Material)
        .where(models.Material.user_id == current_user.id)
        .order_by(models.Material.created_at.desc())
    )
    return result.scalars().all()

@ai_router.get("/materials/{material_id}", response_model=Material)
async def read_material(
    material_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = await db.execute(
        select(models.Material)
        .where(
            models.Material.id == material_id,
            models.Material.user_id == current_user.id
        )
    )
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material

# New endpoint for material analysis
@ai_router.post("/materials/{material_id}/analyze", response_model=AnalysisResult)
async def analyze_material(
    material_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        ai_tools = AIStudyTools(current_user.id, db)
        return await ai_tools.analyze_material(material_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Material analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze material")