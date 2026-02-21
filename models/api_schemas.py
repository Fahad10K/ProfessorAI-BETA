"""
API Request/Response Schemas for Swagger Documentation
All Pydantic models for API payloads
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

# ============= SESSION MANAGEMENT SCHEMAS =============

class SessionCheckResponse(BaseModel):
    """Response for session check endpoint"""
    has_session: bool = Field(..., description="Whether user has an active session")
    session_id: Optional[str] = Field(None, description="UUID of the active session")
    message_count: Optional[int] = Field(None, description="Number of messages in session")
    last_activity: Optional[str] = Field(None, description="ISO timestamp of last activity")
    started_at: Optional[str] = Field(None, description="ISO timestamp when session started")
    message: Optional[str] = Field(None, description="Status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "has_session": True,
                "session_id": "abc-123-uuid",
                "message_count": 15,
                "last_activity": "2024-01-07T10:30:00",
                "started_at": "2024-01-07T09:00:00"
            }
        }


class SessionCreateRequest(BaseModel):
    """Request for creating a new session"""
    user_id: int = Field(..., description="User ID to create session for", gt=0)
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Browser user agent string")
    device_type: Optional[str] = Field(None, description="Device type (mobile, desktop, tablet)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "device_type": "mobile"
            }
        }


class SessionCreateResponse(BaseModel):
    """Response for session creation"""
    session_id: str = Field(..., description="UUID of created session")
    user_id: int = Field(..., description="User ID")
    started_at: str = Field(..., description="ISO timestamp when session started")
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc-123-uuid",
                "user_id": 123,
                "started_at": "2024-01-07T10:00:00",
                "message": "Session created successfully"
            }
        }


class SessionEndRequest(BaseModel):
    """Request for ending a session"""
    session_id: str = Field(..., description="UUID of session to end")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc-123-uuid"
            }
        }


class SessionEndResponse(BaseModel):
    """Response for session end"""
    session_id: str = Field(..., description="UUID of ended session")
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc-123-uuid",
                "message": "Session ended successfully"
            }
        }


class MessageItem(BaseModel):
    """Individual message in conversation history"""
    id: int = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    message_type: Optional[str] = Field(None, description="Message type (text, voice)")
    created_at: str = Field(..., description="ISO timestamp when message was created")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SessionHistoryResponse(BaseModel):
    """Response for session history endpoint"""
    session_id: str = Field(..., description="Session UUID")
    message_count: int = Field(..., description="Number of messages returned")
    messages: List[MessageItem] = Field(..., description="List of messages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc-123-uuid",
                "message_count": 2,
                "messages": [
                    {
                        "id": 1,
                        "role": "user",
                        "content": "Hi, my name is Alice",
                        "message_type": "text",
                        "created_at": "2024-01-07T10:00:00"
                    },
                    {
                        "id": 2,
                        "role": "assistant",
                        "content": "Hello Alice! How can I help you?",
                        "message_type": "text",
                        "created_at": "2024-01-07T10:00:05"
                    }
                ]
            }
        }


# ============= CHAT SCHEMAS =============

class ChatRequest(BaseModel):
    """Request for text chat endpoint"""
    user_id: int = Field(..., description="User ID (required)", gt=0)
    message: str = Field(..., description="User's message/query", min_length=1)
    language: str = Field("en-IN", description="Language code for response")
    course_id: Optional[int] = Field(None, description="Optional course ID for filtering RAG results")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Browser user agent")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "message": "What is robotics?",
                "language": "en-IN"
            }
        }


class ChatResponse(BaseModel):
    """Response from chat endpoint"""
    answer: str = Field(..., description="AI-generated response")
    session_id: str = Field(..., description="Session UUID")
    user_id: int = Field(..., description="User ID")
    route: Optional[str] = Field(None, description="Semantic route (greeting, general_question, course_query)")
    confidence: Optional[float] = Field(None, description="Route confidence score (0-1)")
    sources: Optional[List[Dict]] = Field(None, description="Retrieved source documents")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Robotics is the science of designing and building robots...",
                "session_id": "abc-123-uuid",
                "user_id": 123,
                "route": "course_query",
                "confidence": 0.85,
                "sources": []
            }
        }


class ChatWithAudioRequest(BaseModel):
    """Request for chat with audio endpoint"""
    user_id: int = Field(..., description="User ID (required)", gt=0)
    message: str = Field(..., description="User's message/query", min_length=1)
    language: str = Field("en-IN", description="Language code for TTS")
    course_id: Optional[int] = Field(None, description="Optional course ID for filtering RAG results")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Browser user agent")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "message": "Explain artificial intelligence",
                "language": "en-IN"
            }
        }


class ChatWithAudioResponse(BaseModel):
    """Response from chat with audio endpoint"""
    answer: str = Field(..., description="AI-generated text response")
    audio_data: str = Field(..., description="Base64-encoded audio data")
    session_id: str = Field(..., description="Session UUID")
    user_id: int = Field(..., description="User ID")
    metadata: Dict[str, Any] = Field(..., description="Additional response metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "AI stands for Artificial Intelligence...",
                "audio_data": "base64_encoded_audio_string...",
                "session_id": "abc-123-uuid",
                "user_id": 123,
                "metadata": {"route": "general_question", "confidence": 0.75}
            }
        }


# ============= COURSE SCHEMAS =============

class CourseItem(BaseModel):
    """Course information"""
    id: Union[int, str] = Field(..., description="Course ID (SERIAL or UUID)")
    title: str = Field(..., description="Course title")
    description: Optional[str] = Field(None, description="Course description")
    level: str = Field(..., description="Course level (Beginner, Intermediate, Advanced)")
    teacher_id: Union[int, str] = Field(..., description="Teacher user ID (SERIAL or UUID)")
    course_order: Optional[int] = Field(None, description="Display order")
    course_number: Optional[int] = Field(None, description="Course number")
    country: Optional[str] = Field(None, description="Country where course is offered")
    file_metadata: Optional[Dict] = Field(None, description="Course file metadata")
    created_by: Optional[str] = Field(None, description="Creator username")
    created_at: str = Field(..., description="ISO timestamp")
    updated_at: str = Field(..., description="ISO timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "title": "Introduction to Robotics",
                "description": "Learn robotics fundamentals",
                "level": "Beginner",
                "teacher_id": 5,
                "course_order": 1,
                "course_number": 101,
                "country": "India",
                "file_metadata": {},
                "created_by": "admin",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }


# CoursesListResponse removed - use List[CourseItem] directly in endpoint


# ============= ADMIN DASHBOARD SCHEMAS =============


class UsersByRole(BaseModel):
    """User count breakdown by role"""
    student: int = Field(0, description="Number of students")
    teacher: int = Field(0, description="Number of teachers")
    admin: int = Field(0, description="Number of admins")


class CourseStats(BaseModel):
    """Course statistics"""
    id: int = Field(..., description="Course ID")
    title: str = Field(..., description="Course title")
    country: Optional[str] = Field(None, description="Country")
    level: str = Field(..., description="Course level")
    enrollment_count: int = Field(..., description="Total enrollments")
    paid_enrollment_count: int = Field(..., description="Paid enrollments")


class RecentUser(BaseModel):
    """Recent user information"""
    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    role: str = Field(..., description="User role")
    created_at: str = Field(..., description="ISO timestamp")


class SessionActivity(BaseModel):
    """Daily session activity"""
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    session_count: int = Field(..., description="Number of sessions")
    unique_users: int = Field(..., description="Unique users count")


class DashboardStats(BaseModel):
    """Admin dashboard statistics"""
    total_courses: int = Field(..., description="Total number of courses")
    total_users: int = Field(..., description="Total number of users")
    users_by_role: UsersByRole = Field(..., description="Users breakdown by role")
    active_sessions_24h: int = Field(..., description="Active sessions in last 24 hours")
    total_messages: int = Field(..., description="Total messages sent")
    total_enrollments: int = Field(..., description="Total course enrollments")
    paid_enrollments: int = Field(..., description="Paid enrollments")
    total_purchases: int = Field(..., description="Total purchases")
    total_revenue: float = Field(..., description="Total revenue in default currency")
    courses: List[CourseStats] = Field(..., description="Course list with stats")
    recent_users: List[RecentUser] = Field(..., description="Recently registered users")
    session_activity_7d: List[SessionActivity] = Field(..., description="Session activity last 7 days")


class AdminDashboardResponse(BaseModel):
    """Response for admin dashboard endpoint"""
    status: str = Field(..., description="Response status")
    timestamp: str = Field(..., description="Response timestamp (ISO)")
    data: DashboardStats = Field(..., description="Dashboard statistics")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "timestamp": "2024-01-07T10:00:00",
                "data": {
                    "total_courses": 25,
                    "total_users": 1500,
                    "users_by_role": {
                        "student": 1400,
                        "teacher": 90,
                        "admin": 10
                    },
                    "active_sessions_24h": 350,
                    "total_messages": 12500,
                    "total_enrollments": 3200,
                    "paid_enrollments": 850,
                    "total_purchases": 900,
                    "total_revenue": 125000.00,
                    "courses": [],
                    "recent_users": [],
                    "session_activity_7d": []
                }
            }
        }


# ============= ERROR RESPONSES =============

class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Service not available"
            }
        }


# ============= HEALTH CHECK SCHEMAS =============

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    message: str = Field(..., description="Status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "running",
                "version": "2.0.0-production",
                "message": "ProfAI Production API with Celery Workers"
            }
        }
