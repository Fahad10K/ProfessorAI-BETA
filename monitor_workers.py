#!/usr/bin/env python3
"""
Celery Worker Monitoring Script
Shows real-time status of all 5 workers and their task queues
"""

import os
import sys
from celery import Celery
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import celery app
from celery_app import celery_app

def print_header():
    print("=" * 100)
    print("🔍 CELERY WORKER MONITORING DASHBOARD")
    print("=" * 100)
    print()

def get_worker_stats():
    """Get statistics for all active workers"""
    
    # Inspect active workers
    inspect = celery_app.control.inspect()
    
    print("📊 WORKER STATUS")
    print("-" * 100)
    
    # Get active workers
    stats = inspect.stats()
    active_workers = inspect.active()
    registered = inspect.registered()
    
    if not stats:
        print("❌ No active workers found!")
        print("   Make sure workers are running:")
        print("   docker-compose -f docker-compose-production.yml ps")
        return
    
    print(f"✅ Found {len(stats)} active workers\n")
    
    # Display each worker
    for worker_name, worker_stats in stats.items():
        print(f"Worker: {worker_name}")
        print(f"  Pool: {worker_stats.get('pool', {}).get('implementation', 'N/A')}")
        print(f"  Max Concurrency: {worker_stats.get('pool', {}).get('max-concurrency', 'N/A')}")
        
        # Active tasks
        if active_workers and worker_name in active_workers:
            active_tasks = active_workers[worker_name]
            print(f"  Active Tasks: {len(active_tasks)}")
            for task in active_tasks:
                print(f"    - {task['name']} (ID: {task['id'][:8]}...)")
        else:
            print(f"  Active Tasks: 0")
        
        # Registered tasks
        if registered and worker_name in registered:
            task_list = registered[worker_name]
            print(f"  Registered Tasks: {len(task_list)}")
        
        print()
    
    print("-" * 100)
    print()

def get_queue_stats():
    """Get statistics for task queues"""
    
    print("📋 QUEUE STATUS")
    print("-" * 100)
    
    inspect = celery_app.control.inspect()
    
    # Get reserved tasks (in queue but not yet processing)
    reserved = inspect.reserved()
    scheduled = inspect.scheduled()
    
    if reserved:
        total_reserved = sum(len(tasks) for tasks in reserved.values())
        print(f"📦 Reserved Tasks (in queue): {total_reserved}")
        
        for worker_name, tasks in reserved.items():
            if tasks:
                print(f"  {worker_name}: {len(tasks)} tasks waiting")
    else:
        print("✅ No tasks in queue (all workers available)")
    
    print()
    print("-" * 100)
    print()

def get_recent_tasks():
    """Display recent task activity"""
    
    # This would require result backend with task history
    # For now, just show a message
    print("📈 RECENT ACTIVITY")
    print("-" * 100)
    print("To see detailed task history, check Redis backend or application logs")
    print()

def main():
    print_header()
    
    try:
        get_worker_stats()
        get_queue_stats()
        get_recent_tasks()
        
        print("=" * 100)
        print("💡 TIPS:")
        print("  - Run this script periodically to monitor worker health")
        print("  - If workers show 0 active and you expect tasks, check Redis connection")
        print("  - Each worker processes 1 PDF at a time (concurrency=1)")
        print("  - With 5 workers, you can process 5 PDFs simultaneously")
        print("=" * 100)
        
    except Exception as e:
        print(f"❌ Error connecting to Celery: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check if Redis is accessible")
        print("  2. Verify REDIS_URL in .env")
        print("  3. Ensure workers are running: docker ps")

if __name__ == "__main__":
    main()
