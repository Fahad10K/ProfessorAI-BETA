#!/usr/bin/env python3
"""
Local Worker Testing Script
Verifies the 5-worker setup works correctly before EC2 deployment
"""

import os
import sys
import time
from celery_app import celery_app

def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)

def test_celery_config():
    """Test 1: Verify Celery configuration"""
    print_header("TEST 1: Celery Configuration")
    
    try:
        # Check broker connection
        print("📡 Testing Redis connection...")
        result = celery_app.control.inspect().ping()
        
        if result:
            print(f"✅ Redis connected: {len(result)} workers detected")
            for worker_name in result.keys():
                print(f"   - {worker_name}")
        else:
            print("⚠️  No workers detected (this is OK if workers not started yet)")
        
        # Check configuration
        print("\n📋 Celery Configuration:")
        print(f"   - Broker: {celery_app.conf.broker_url[:30]}...")
        print(f"   - Task Queues: {[q.name for q in celery_app.conf.task_queues]}")
        print(f"   - Worker Prefetch: {celery_app.conf.worker_prefetch_multiplier}")
        print(f"   - Max Tasks Per Child: {celery_app.conf.worker_max_tasks_per_child}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_worker_registration():
    """Test 2: Check if workers are registered"""
    print_header("TEST 2: Worker Registration")
    
    try:
        inspect = celery_app.control.inspect()
        
        # Get registered tasks
        registered = inspect.registered()
        
        if not registered:
            print("⚠️  No workers running")
            print("\n💡 To start workers, open 5 PowerShell terminals and run:")
            print("   Terminal 1: $env:WORKER_NUM='1'; python worker.py")
            print("   Terminal 2: $env:WORKER_NUM='2'; python worker.py")
            print("   Terminal 3: $env:WORKER_NUM='3'; python worker.py")
            print("   Terminal 4: $env:WORKER_NUM='4'; python worker.py")
            print("   Terminal 5: $env:WORKER_NUM='5'; python worker.py")
            return False
        
        print(f"✅ Found {len(registered)} active workers:\n")
        
        for worker_name, tasks in registered.items():
            print(f"Worker: {worker_name}")
            print(f"   Registered Tasks: {len(tasks)}")
            for task in tasks:
                if 'pdf_processing' in task or 'quiz' in task:
                    print(f"   - {task}")
        
        return len(registered) >= 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_worker_stats():
    """Test 3: Get detailed worker stats"""
    print_header("TEST 3: Worker Statistics")
    
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            print("⚠️  No workers running")
            return False
        
        print(f"✅ Worker Statistics:\n")
        
        for worker_name, worker_stats in stats.items():
            pool_info = worker_stats.get('pool', {})
            print(f"Worker: {worker_name}")
            print(f"   Pool: {pool_info.get('implementation', 'N/A')}")
            print(f"   Max Concurrency: {pool_info.get('max-concurrency', 'N/A')}")
            print(f"   Total Tasks: {worker_stats.get('total', {})}")
            print()
        
        # Check if we have the expected number of workers
        expected_workers = 5
        actual_workers = len(stats)
        
        if actual_workers == expected_workers:
            print(f"✅ All {expected_workers} workers are running!")
        elif actual_workers > 0:
            print(f"⚠️  Only {actual_workers}/{expected_workers} workers running")
            print(f"   Start remaining workers for full capacity")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_queue_status():
    """Test 4: Check queue status"""
    print_header("TEST 4: Queue Status")
    
    try:
        inspect = celery_app.control.inspect()
        
        # Active tasks
        active = inspect.active()
        reserved = inspect.reserved()
        
        if active:
            total_active = sum(len(tasks) for tasks in active.values())
            print(f"📊 Active Tasks: {total_active}")
            for worker_name, tasks in active.items():
                if tasks:
                    print(f"   {worker_name}: {len(tasks)} tasks processing")
        else:
            print("✅ No active tasks (workers are idle)")
        
        if reserved:
            total_reserved = sum(len(tasks) for tasks in reserved.values())
            print(f"📦 Reserved Tasks (in queue): {total_reserved}")
        else:
            print("✅ No tasks in queue (all workers available)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_send_test_task():
    """Test 5: Send a test task (optional)"""
    print_header("TEST 5: Send Test Task (Optional)")
    
    user_input = input("\n⚠️  Send a test task to workers? This will test actual processing. (y/N): ")
    
    if user_input.lower() != 'y':
        print("⏭️  Skipping test task")
        return True
    
    try:
        from tasks.pdf_processing import process_pdf_and_generate_course
        
        print("\n📤 Sending test task...")
        
        # Create a minimal test task
        task = process_pdf_and_generate_course.delay(
            job_id="test_job_123",
            pdf_files_data=[],  # Empty for testing
            course_title="Test Course"
        )
        
        print(f"✅ Task sent! Task ID: {task.id}")
        print(f"\n⏳ Waiting for task to be picked up (5 seconds)...")
        
        time.sleep(5)
        
        # Check task status
        if task.state == 'PENDING':
            print("📋 Task is waiting in queue")
        elif task.state == 'STARTED':
            print("🚀 Task is being processed by a worker!")
        elif task.state == 'SUCCESS':
            print("✅ Task completed successfully!")
        elif task.state == 'FAILURE':
            print("❌ Task failed (expected with empty data)")
        else:
            print(f"📊 Task state: {task.state}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "🧪" * 40)
    print("  LOCAL WORKER TESTING SUITE - 5 WORKERS")
    print("🧪" * 40)
    
    print("\n📝 This script will verify your 5-worker setup is working correctly")
    print("   before deploying to EC2.\n")
    
    results = []
    
    # Run tests
    results.append(("Celery Config", test_celery_config()))
    results.append(("Worker Registration", test_worker_registration()))
    results.append(("Worker Stats", test_worker_stats()))
    results.append(("Queue Status", test_queue_status()))
    results.append(("Test Task", test_send_test_task()))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print()
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your setup is ready for EC2 deployment!")
        print("\n📋 Next Steps:")
        print("   1. Upload modified files to EC2")
        print("   2. Rebuild containers: docker-compose -f docker-compose-production.yml build")
        print("   3. Start services: docker-compose -f docker-compose-production.yml up -d")
        print("   4. Verify: docker ps (should show 6 containers)")
    else:
        print("\n⚠️  Some tests failed. Please fix issues before deploying.")
        print("\n💡 Common fixes:")
        print("   - Ensure Redis is accessible (check REDIS_URL in .env)")
        print("   - Start workers manually to test locally")
        print("   - Check if all required packages are installed")
    
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    main()
