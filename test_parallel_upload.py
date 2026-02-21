"""
Test Script for Parallel Course Generation
Tests uploading multiple PDFs and monitors their parallel processing
"""

import requests
import time
import json
from pathlib import Path
from datetime import datetime

# Configuration
API_URL = "http://localhost:5003"

# Replace these with your actual PDF file paths
PDF_FILES = [
    r"C:\Users\Lenovo\Downloads\ai basic.pdf",
    r"C:\Users\Lenovo\Downloads\Curriculum_SrSec.pdf"
]

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def upload_pdf(file_path, course_title, priority=5):
    """Upload a single PDF and return task information"""
    url = f"{API_URL}/api/upload-pdfs"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'files': (Path(file_path).name, f, 'application/pdf')}
            data = {
                'course_title': course_title,
                'priority': priority
            }
            
            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()
            return response.json()
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Cannot connect to API at {API_URL}")
        print("   Make sure the FastAPI server is running!")
        return None
    except Exception as e:
        print(f"❌ Error uploading {file_path}: {e}")
        return None

def check_status(task_id):
    """Check status of a task"""
    url = f"{API_URL}/api/jobs/{task_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Error checking status: {e}")
        return None

def get_worker_stats():
    """Get worker statistics"""
    url = f"{API_URL}/api/worker-stats"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Error getting worker stats: {e}")
        return None

def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_single_upload():
    """Test uploading a single PDF"""
    print_header("TEST 1: Single PDF Upload")
    
    if not PDF_FILES or not Path(PDF_FILES[0]).exists():
        print("⚠️  Please update PDF_FILES in the script with actual file paths")
        return
    
    pdf_path = PDF_FILES[0]
    print(f"📤 Uploading: {Path(pdf_path).name}")
    
    result = upload_pdf(pdf_path, "Test Course - Single", priority=5)
    
    if not result:
        return
    
    print(f"✅ Upload successful!")
    print(f"   Task ID: {result['task_id']}")
    print(f"   Job ID: {result['job_id']}")
    print(f"   Status URL: {result['status_url']}")
    
    # Monitor progress
    print(f"\n⏳ Monitoring progress...\n")
    task_id = result['task_id']
    
    while True:
        status = check_status(task_id)
        
        if not status:
            print("❌ Failed to get status")
            break
        
        state = status.get('status')
        progress = status.get('progress', 0)
        message = status.get('message', '')
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {state:12} | Progress: {progress:3}% | {message}")
        
        if state == 'SUCCESS':
            print(f"\n🎉 Course generation completed!")
            result_data = status.get('result', {})
            print(f"   Course ID: {result_data.get('course_id')}")
            print(f"   Title: {result_data.get('course_title')}")
            print(f"   Modules: {result_data.get('modules')}")
            break
        elif state == 'FAILURE':
            print(f"\n❌ Task failed!")
            print(f"   Error: {status.get('error')}")
            break
        
        time.sleep(3)

def test_parallel_upload():
    """Upload multiple PDFs and monitor parallel processing"""
    print_header("TEST 2: Parallel PDF Upload")
    
    # Filter out non-existent files
    valid_files = [f for f in PDF_FILES if Path(f).exists()]
    
    if len(valid_files) < 2:
        print("⚠️  Need at least 2 valid PDF files to test parallel processing")
        print("   Please update PDF_FILES in the script with actual file paths")
        return
    
    print(f"🚀 Uploading {len(valid_files)} PDFs simultaneously...\n")
    
    # Upload all PDFs
    tasks = []
    start_time = time.time()
    
    for i, pdf_path in enumerate(valid_files):
        print(f"📤 Uploading: {Path(pdf_path).name}")
        result = upload_pdf(pdf_path, f"Parallel Course {i+1}", priority=5+i)
        
        if result:
            tasks.append({
                'file': Path(pdf_path).name,
                'task_id': result['task_id'],
                'job_id': result['job_id'],
                'completed': False
            })
            print(f"   ✅ Task ID: {result['task_id']}\n")
        else:
            print(f"   ❌ Upload failed\n")
    
    if not tasks:
        print("❌ No tasks were submitted successfully")
        return
    
    upload_time = time.time() - start_time
    print(f"📊 Submitted {len(tasks)} tasks in {upload_time:.2f} seconds")
    print(f"\n⏳ Monitoring parallel processing...\n")
    
    # Monitor all tasks
    completed = 0
    last_update = {}
    
    while completed < len(tasks):
        for task in tasks:
            if task.get('completed'):
                continue
            
            status = check_status(task['task_id'])
            
            if not status:
                continue
            
            state = status.get('status')
            progress = status.get('progress', 0)
            message = status.get('message', 'Processing...')
            
            # Only print if status changed
            current_status = f"{state}:{progress}"
            if last_update.get(task['task_id']) != current_status:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] {task['file'][:30]:30} | {state:12} | {progress:3}% | {message[:40]}")
                last_update[task['task_id']] = current_status
            
            if state == 'SUCCESS':
                task['completed'] = True
                completed += 1
                result = status.get('result', {})
                print(f"   ✅ Course ID: {result.get('course_id')} | Modules: {result.get('modules')}\n")
            elif state == 'FAILURE':
                task['completed'] = True
                completed += 1
                print(f"   ❌ Error: {status.get('error')}\n")
        
        if completed < len(tasks):
            time.sleep(3)
    
    total_time = time.time() - start_time
    print(f"\n🎉 All tasks completed in {total_time:.2f} seconds!")
    print(f"   Average: {total_time/len(tasks):.2f} seconds per course")

def test_worker_stats():
    """Display worker statistics"""
    print_header("TEST 3: Worker Statistics")
    
    stats = get_worker_stats()
    
    if not stats:
        print("❌ Could not retrieve worker stats")
        return
    
    active_workers = stats.get('active_workers', {})
    active_tasks = stats.get('active_tasks', {})
    
    print(f"🔧 Active Workers: {len(active_workers)}")
    for worker_name, tasks in active_workers.items():
        print(f"   • {worker_name}")
    
    print(f"\n📋 Active Tasks:")
    total_active = sum(len(tasks) for tasks in active_tasks.values())
    if total_active == 0:
        print("   No tasks currently running")
    else:
        for worker_name, tasks in active_tasks.items():
            if tasks:
                print(f"\n   Worker: {worker_name}")
                for task in tasks:
                    print(f"      - Task ID: {task.get('id')}")
                    print(f"        Name: {task.get('name')}")

def main():
    """Main test runner"""
    print("\n" + "🎓"*30)
    print("  PARALLEL COURSE GENERATION TEST SUITE")
    print("🎓"*30)
    
    # Check if API is running
    print("\n🔍 Checking API connection...")
    if not check_api_health():
        print("❌ API is not responding!")
        print("\nPlease start the API server:")
        print("   python app_celery.py")
        return
    
    print("✅ API is running\n")
    
    # Display menu
    while True:
        print("\n" + "-"*60)
        print("Select a test:")
        print("  1. Test single PDF upload")
        print("  2. Test parallel PDF upload (multiple PDFs)")
        print("  3. Check worker statistics")
        print("  4. Run all tests")
        print("  5. Exit")
        print("-"*60)
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == '1':
            test_single_upload()
        elif choice == '2':
            test_parallel_upload()
        elif choice == '3':
            test_worker_stats()
        elif choice == '4':
            test_worker_stats()
            time.sleep(2)
            test_single_upload()
            time.sleep(2)
            test_parallel_upload()
        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        else:
            print("⚠️  Invalid choice. Please enter 1-5.")
        
        input("\n\nPress Enter to continue...")

if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Before running this script:")
    print("   1. Update PDF_FILES list with actual PDF file paths")
    print("   2. Make sure Redis is running (docker or Upstash)")
    print("   3. Start at least 1 Celery worker")
    print("   4. Start the FastAPI server (python app_celery.py)")
    print("\nFor detailed instructions, see: TESTING_PARALLEL_COURSE_GENERATION.md\n")
    
    proceed = input("Ready to proceed? (y/n): ").strip().lower()
    if proceed == 'y':
        main()
    else:
        print("\n👋 Setup your environment first, then run this script again!")
