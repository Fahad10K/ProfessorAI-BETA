"""
Celery Worker Entry Point
Run this in separate pods for distributed PDF processing

Usage:
    python worker.py

Or with Celery command:
    celery -A celery_app worker --loglevel=info --concurrency=3 --queues=pdf_processing
"""

import os
import sys
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    # Start worker
    # Optimized for EC2: concurrency=1 to prevent memory spikes
    # With 5 workers, we can process 5 PDFs simultaneously
    
    # Get worker number from environment (optional)
    worker_num = os.getenv('WORKER_NUM', '1')
    
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=1',  # 1 task per worker (prevents memory spikes on EC2)
        '--pool=prefork',  # Use prefork pool for better CPU utilization
        '--queues=pdf_processing,quiz_generation',
        '--max-tasks-per-child=20',  # Restart after 20 tasks (aggressive memory management)
        '--time-limit=3600',  # 1 hour hard limit
        '--soft-time-limit=3000',  # 50 minutes soft limit
        f'--hostname=worker{worker_num}@%h',  # Unique worker name
    ])
