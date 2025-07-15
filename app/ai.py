from typing import List, Dict, NamedTuple
import openai
import os
import json
from .database import get_async_session
from .models import User, CourseMaterial
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

openai.api_key = os.getenv("OPENAI_API_KEY")


class AnalysisResult(NamedTuple):
    summary: str
    key_points: List[str]
    difficulty: str
    suggested_study_time: int  # in minutes


class PracticeQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: int
    explanation: str


class AIStudyTools:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db

    def analyze_text(self, text: str) -> AnalysisResult:
        """
        Analyze study material text and return structured results.
        Args:
            text: The text content to analyze (extracted from PDF or other sources)
        Returns:
            AnalysisResult: Contains summary, key points, difficulty, and suggested study time
        """
        if openai.api_key:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful study assistant. Analyze the following study material and provide:"},
                    {"role": "system", "content": "1. A concise summary (2-3 sentences)"},
                    {"role": "system", "content": "2. 3-5 key points (bullet points)"},
                    {"role": "system", "content": "3. Difficulty level (Beginner/Intermediate/Advanced)"},
                    {"role": "system", "content": "4. Suggested study time in minutes"},
                    {"role": "user", "content": text[:4000]}  # Limit to token size
                ],
                temperature=0.3
            )

            content = response.choices[0].message.content
            return self._parse_ai_response(content)

        # Fallback to basic analysis if no API key
        return self._basic_text_analysis(text)

    def _parse_ai_response(self, response: str) -> AnalysisResult:
        """Parse the raw AI response into structured data"""
        lines = [line.strip() for line in response.split('\n') if line.strip()]

        summary = lines[0] if lines else "No summary generated"
        key_points = []
        difficulty = "Intermediate"
        study_time = 30  # default

        for line in lines[1:]:
            if line.startswith("- "):
                key_points.append(line[2:])
            elif "difficulty" in line.lower():
                difficulty = self._extract_difficulty(line)
            elif "minutes" in line.lower():
                study_time = self._extract_study_time(line)

        return AnalysisResult(
            summary=summary,
            key_points=key_points[:5] if key_points else ["No key points identified"],
            difficulty=difficulty,
            suggested_study_time=study_time
        )

    def _extract_difficulty(self, text: str) -> str:
        """Extract difficulty level from text"""
        text = text.lower()
        if "beginner" in text:
            return "Beginner"
        elif "advanced" in text:
            return "Advanced"
        return "Intermediate"

    def _extract_study_time(self, text: str) -> int:
        """Extract study time in minutes from text"""
        try:
            return int(''.join(filter(str.isdigit, text)))
        except (ValueError, TypeError):
            return 30  # default

    def _basic_text_analysis(self, text: str) -> AnalysisResult:
        """Fallback text analysis when no AI API is available"""
        word_count = len(text.split())
        reading_time = max(5, word_count // 200)  # 200 words per minute reading speed

        # Simple summary extraction (first 2 sentences)
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        summary = '. '.join(sentences[:2]) + '.' if sentences else "No summary available"

        return AnalysisResult(
            summary=summary,
            key_points=["Basic analysis: Focus on main concepts", "Review terminology", "Practice key examples"],
            difficulty="Intermediate",
            suggested_study_time=reading_time
        )

    async def generate_practice_test(self, course_material_id, num_questions=10):
        """
        Generate AI-powered practice test questions based on course material
        """
        material = (await self.db.exec(select(CourseMaterial).filter(CourseMaterial.id == course_material_id))).first()
        if not material:
            raise ValueError(f"Course material with id {course_material_id} not found")
        prompt = f"""
        Generate {num_questions} practice test questions based on the following study material:
        {material.content}

        Format each question as a JSON object with:
        - question: the question text
        - options: list of possible answers
        - correct_answer: index of correct option
        - explanation: brief explanation of the answer
        """

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return response.choices[0].message.content

    async def generate_timed_test(self, material_id, duration=30):
        test = await self.generate_practice_test(material_id)
        return {
            'questions': test,
            'time_limit': duration * 60,  # Convert to seconds
            'instructions': f"This is a timed test with a duration of {duration} minutes. Answer all questions to the best of your ability."
        }

    async def get_study_recommendations(self):
        """
        Generate personalized study recommendations based on user progress
        """
        user = (await self.db.exec(select(User).filter(User.id == self.user_id))).first()
        if not user:
            raise ValueError(f"User with id {self.user_id} not found")

        prompt = f"""
        Generate personalized study recommendations for a student with these characteristics:
        - Current level: {user.level}
        - Recent activity: {getattr(user, 'last_activities', 'N/A')}
        - Weak areas: {getattr(user, 'weak_topics', 'N/A')}

        Provide recommendations as a list of specific study actions with priorities.
        """

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )

        return response.choices[0].message.content

    async def enhance_memory_training(self, content):
        """
        Generate memory training exercises (like flashcards or spaced repetition items) from content
        """
        prompt = f"""
        Create memory training exercises (like flashcards or spaced repetition items) from:
        {content}

        Format as JSON with:
        - question: what to recall
        - answer: correct answer
        - hints: list of helpful hints
        - difficulty: easy/medium/hard
        """

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )

        return response.choices[0].message.content


class TestGenerator:
    @staticmethod
    def generate_practice_questions(topic: str, count: int = 5) -> List[Dict]:
        """
        Generates multiple-choice questions with:
        - Question text
        - 4 options
        - Correct answer
        - Explanation
        """
        prompt = f"""Generate {count} multiple-choice questions about {topic} in JSON format.
        Each question should have:
        1. 'question' (string)
        2. 'options' (list of 4 strings)
        3. 'correct_answer' (index 0-3)
        4. 'explanation' (string)
        """

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return TestGenerator._format_questions(response.choices[0].message.content)

    @staticmethod
    def _format_questions(raw_response: str) -> List[Dict]:
        """Converts the AI response to structured data"""
        try:
            data = json.loads(raw_response)
            if isinstance(data, dict) and "questions" in data:
                return data["questions"]
            return []
        except json.JSONDecodeError:
            # Fallback parsing if JSON is malformed
            questions = []
            current_question = {}

            for line in raw_response.split('\n'):
                if line.startswith("Q:") or line.startswith("Question:"):
                    if current_question:
                        questions.append(current_question)
                    current_question = {"question": line.split(":", 1)[1].strip()}
                elif line.startswith(("A.", "B.", "C.", "D.")):
                    if "options" not in current_question:
                        current_question["options"] = []
                    current_question["options"].append(line[3:].strip())
                elif "correct answer" in line.lower():
                    correct_marker = line.split(":")[1].strip().upper()
                    current_question["correct_answer"] = ord(correct_marker) - ord('A')
                elif line.startswith("Explanation:"):
                    current_question["explanation"] = line.split(":", 1)[1].strip()

            if current_question:
                questions.append(current_question)
            return questions