"""
Celery Tasks for PDF Processing
Handles long-running PDF uploads and course generation in background workers
"""

import logging
import os
import sys
import tempfile
from typing import List, Dict, Any
import traceback

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from celery_app import celery_app
import config
from services.document_service import DocumentService

# Initialize document service
document_service = DocumentService()

@celery_app.task(
    bind=True,
    name='tasks.pdf_processing.process_pdf_and_generate_course',
    queue='pdf_processing',
    max_retries=3,
    default_retry_delay=60
)
def process_pdf_and_generate_course(
    self,
    job_id: str,
    pdf_files_data: List[Dict[str, Any]],
    course_title: str = None,
    country: str = None
) -> Dict[str, Any]:
    """
    Process PDF files and generate course content.
    
    This task runs in a separate worker pod and can scale horizontally.
    
    Args:
        job_id: Unique job identifier
        pdf_files_data: List of dicts with 'filename' and 'content' (base64 encoded)
        course_title: Optional course title
        country: Country where course is offered (e.g., 'India', 'USA')
        
    Returns:
        Dict with course data or error information
    """
    try:
        # Update task state to STARTED
        self.update_state(
            state='STARTED',
            meta={
                'status': 'processing',
                'progress': 10,
                'message': 'Starting PDF processing...'
            }
        )
        
        logging.info(f"[Job {job_id}] Processing {len(pdf_files_data)} PDF files")
        
        # Create temporary files from base64 data
        temp_files = []
        try:
            import base64
            from io import BytesIO
            
            for pdf_data in pdf_files_data:
                # Decode base64 content
                file_content = base64.b64decode(pdf_data['content'])
                
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix='.pdf',
                    prefix='upload_'
                )
                temp_file.write(file_content)
                temp_file.close()
                
                temp_files.append({
                    'path': temp_file.name,
                    'filename': pdf_data['filename']
                })
            
            # Update progress
            self.update_state(
                state='STARTED',
                meta={
                    'status': 'processing',
                    'progress': 20,
                    'message': f'Saved {len(temp_files)} files, extracting text...'
                }
            )
            
            # Process PDFs using the synchronous file-path method
            # (process_pdfs_and_generate_course is async + expects UploadFile objects)
            result = document_service.process_pdf_files_from_paths(
                temp_files,
                course_title,
                country=country,
                progress_callback=lambda progress, msg: self.update_state(
                    state='STARTED',
                    meta={
                        'status': 'processing',
                        'progress': progress,
                        'message': msg
                    }
                )
            )
            
            # Success
            logging.info(f"[Job {job_id}] Course generated successfully: {result.get('course_id')}")
            
            # --- Auto-generate quiz after course creation ---
            quiz_id = None
            try:
                self.update_state(
                    state='STARTED',
                    meta={
                        'status': 'processing',
                        'progress': 92,
                        'message': 'Generating course quiz...'
                    }
                )
                import asyncio
                from services.quiz_service import QuizService
                quiz_svc = QuizService()
                quiz = asyncio.run(quiz_svc.generate_course_quiz(result))
                quiz_id = quiz.quiz_id if quiz else None
                if quiz_id:
                    logging.info(f"[Job {job_id}] ✅ Auto-generated course quiz: {quiz_id}")
            except Exception as qe:
                logging.warning(f"[Job {job_id}] ⚠️ Auto quiz generation failed (non-fatal): {qe}")
            
            task_result = {
                'status': 'completed',
                'job_id': job_id,
                'result': {
                    'course_id': result.get('course_id'),
                    'course_title': result.get('course_title'),
                    'modules': len(result.get('modules', []))
                }
            }
            if quiz_id:
                task_result['result']['quiz_id'] = quiz_id
            
            return task_result
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file['path'])
                except Exception as e:
                    logging.warning(f"Could not delete temp file: {e}")
    
    except Exception as exc:
        error_msg = str(exc)
        error_trace = traceback.format_exc()
        logging.error(f"[Job {job_id}] Task failed: {error_msg}")
        logging.error(error_trace)
        
        # Update state to FAILURE
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'failed',
                'error': error_msg,
                'traceback': error_trace
            }
        )
        
        # Retry if possible
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    bind=True,
    name='tasks.pdf_processing.batch_process_pdfs',
    queue='pdf_processing'
)
def batch_process_pdfs(
    self,
    job_ids: List[str],
    pdf_files_batch: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Process multiple PDF uploads in batch.
    Useful for bulk uploads by teachers.
    
    Args:
        job_ids: List of job identifiers
        pdf_files_batch: List of PDF file data
        
    Returns:
        List of results
    """
    results = []
    
    for job_id, pdf_data in zip(job_ids, pdf_files_batch):
        try:
            result = process_pdf_and_generate_course.apply_async(
                args=[job_id, pdf_data['files'], pdf_data.get('course_title')],
                priority=pdf_data.get('priority', 5)
            )
            results.append({
                'job_id': job_id,
                'task_id': result.id,
                'status': 'queued'
            })
        except Exception as e:
            results.append({
                'job_id': job_id,
                'status': 'failed',
                'error': str(e)
            })
    
    return results


@celery_app.task(
    name='tasks.pdf_processing.cleanup_old_jobs',
    queue='pdf_processing'
)
def cleanup_old_jobs():
    """
    Periodic task to clean up old job records.
    Runs daily to remove completed jobs older than 7 days.
    """
    from datetime import datetime, timedelta
    
    try:
        # TODO: Implement cleanup logic when database is enabled
        # Delete jobs older than 7 days
        cutoff_date = datetime.now() - timedelta(days=7)
        logging.info(f"Cleaning up jobs older than {cutoff_date}")
        
        # This will be implemented with database
        pass
        
    except Exception as e:
        logging.error(f"Cleanup task failed: {e}")
