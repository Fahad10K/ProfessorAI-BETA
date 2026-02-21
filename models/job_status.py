"""
Job Status Tracking - Manages background job states
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
import uuid

class JobStatus(str, Enum):
    """Job processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobInfo(BaseModel):
    """Job information model"""
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0  # 0-100
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    class Config:
        use_enum_values = True

class JobTracker:
    """
    In-memory job tracking system.
    
    TODO: Replace with database when Neon PostgreSQL is integrated
    For now, jobs are stored in memory and lost on server restart.
    """
    
    def __init__(self):
        self._jobs: Dict[str, JobInfo] = {}
    
    def create_job(self) -> str:
        """Create a new job and return job_id"""
        job_id = str(uuid.uuid4())
        job = JobInfo(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now()
        )
        self._jobs[job_id] = job
        return job_id
    
    def update_status(self, job_id: str, status: JobStatus, message: Optional[str] = None):
        """Update job status"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.status = status
            job.message = message
            
            if status == JobStatus.PROCESSING and not job.started_at:
                job.started_at = datetime.now()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                job.completed_at = datetime.now()
    
    def update_progress(self, job_id: str, progress: int, message: Optional[str] = None):
        """Update job progress (0-100)"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.progress = min(100, max(0, progress))
            if message:
                job.message = message
    
    def set_result(self, job_id: str, result: Dict[str, Any]):
        """Set job result on completion"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.result = result
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
    
    def set_error(self, job_id: str, error: str):
        """Set job error on failure"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.error = error
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
    
    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job information"""
        return self._jobs.get(job_id)
    
    def delete_job(self, job_id: str):
        """Delete job (cleanup old jobs)"""
        if job_id in self._jobs:
            del self._jobs[job_id]
    
    def get_all_jobs(self) -> Dict[str, JobInfo]:
        """Get all jobs (for debugging)"""
        return self._jobs.copy()

# Global job tracker instance
job_tracker = JobTracker()

# TODO: When Neon PostgreSQL is integrated, replace JobTracker with database operations
# See services/database_service.py for the database implementation
