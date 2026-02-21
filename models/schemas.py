"""
Data Models - Pydantic schemas for course structure and API requests
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Union

class SubTopic(BaseModel):
    """Defines a sub-topic within a larger learning module."""
    title: str = Field(description="The title of the sub-topic")
    content: Optional[str] = Field(None, description="Detailed generated content for this sub-topic")

class Module(BaseModel):
    """Defines a learning module or a week in the curriculum."""
    week: int = Field(description="The week number of the module")
    title: str = Field(description="The title of the module")
    sub_topics: List[SubTopic] = Field(description="A list of sub-topics covered in this module")

class CourseLMS(BaseModel):
    """The final, structured output for the entire course, ready for an LMS."""
    course_title: str = Field(description="The overall title of the course")
    course_id: Optional[Union[int, str]] = Field(None, description="Unique identifier (INTEGER for JSON, TEXT UUID for database)")
    modules: List[Module] = Field(description="A list of all modules in the course")

# API Request Models
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(description="The user's message/query")
    language: str = Field(default="en-IN", description="Response language code")

class TextQuery(BaseModel):
    """Legacy text query model for compatibility."""
    query: str = Field(description="The user's query")
    language: str = Field(default="en-IN", description="Response language code")

class TTSRequest(BaseModel):
    """Request model for text-to-speech generation."""
    text: str = Field(description="Text to convert to speech")
    language: str = Field(default="en-IN", description="Language for TTS")

# Quiz Models
class QuizQuestion(BaseModel):
    """Individual quiz question with multiple choice options."""
    question_id: str = Field(description="Unique identifier for the question")
    question_number: int = Field(description="Question number (1, 2, 3...)")
    question_text: str = Field(description="The quiz question text")
    options: List[str] = Field(description="List of 4 multiple choice options (A, B, C, D)")
    correct_answer: str = Field(description="Correct option (A, B, C, or D)")
    explanation: Optional[str] = Field(None, description="Explanation for the correct answer")
    topic: Optional[str] = Field(None, description="Topic/module this question relates to")

class Quiz(BaseModel):
    """Complete quiz structure."""
    quiz_id: str = Field(description="Unique identifier for the quiz")
    title: str = Field(description="Quiz title")
    description: str = Field(description="Quiz description")
    questions: List[QuizQuestion] = Field(description="List of quiz questions")
    total_questions: int = Field(description="Total number of questions")
    quiz_type: str = Field(description="Type: 'module' or 'course'")
    module_week: Optional[int] = Field(None, description="Module week number for module quizzes")

class QuizSubmission(BaseModel):
    """Quiz submission from user."""
    quiz_id: str = Field(description="Quiz identifier")
    user_id: str = Field(description="User identifier")
    answers: dict = Field(description="Dict mapping question_id to selected answer (A/B/C/D)")

class QuizResult(BaseModel):
    """Quiz evaluation results."""
    quiz_id: str = Field(description="Quiz identifier")
    user_id: str = Field(description="User identifier")
    score: int = Field(description="Number of correct answers")
    total_questions: int = Field(description="Total number of questions")
    percentage: float = Field(description="Score percentage")
    passed: bool = Field(description="Whether user passed (>= 60%)")
    detailed_results: List[dict] = Field(description="Detailed per-question results")


class QuizRequest(BaseModel):
    """Request model for quiz generation."""
    quiz_type: str = Field(description="Type: 'module' or 'course'")
    course_id: Union[int, str] = Field(description="Course identifier (can be integer or UUID string)")
    module_week: Optional[int] = Field(None, description="Module week number for module quizzes")

# Display Models (for client without answers)
class QuizQuestionDisplay(BaseModel):
    """Quiz question for display without correct answer."""
    question_id: str = Field(description="Unique identifier for the question")
    question_text: str = Field(description="The quiz question text")
    options: List[str] = Field(description="List of 4 multiple choice options (A, B, C, D)")
    topic: Optional[str] = Field(None, description="Topic/module this question relates to")

class QuizDisplay(BaseModel):
    """Quiz structure for display without correct answers."""
    quiz_id: str = Field(description="Unique identifier for the quiz")
    title: str = Field(description="Quiz title")
    description: str = Field(description="Quiz description")
    questions: List[QuizQuestionDisplay] = Field(description="List of quiz questions without answers")
    total_questions: int = Field(description="Total number of questions")
    quiz_type: str = Field(description="Type: 'module' or 'course'")
    module_week: Optional[int] = Field(None, description="Module week number for module quizzes")
    course_id: Optional[str] = Field(None, description="Course identifier")