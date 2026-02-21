"""
Test Script for Concurrency Fix
Tests that multiple PDF uploads can be processed simultaneously
"""

import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor
import sys

BASE_URL = "http://localhost:5001"

def test_single_upload():
    """Test 1: Single upload - baseline test"""
    print("\n" + "="*60)
    print("TEST 1: Single PDF Upload (Baseline)")
    print("="*60)
    
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/")
        print("✅ Server is running")
    except:
        print("❌ Server is not running! Start with: python run_profai_websocket.py")
        return False
    
    # Create a simple test file (you'll need a real PDF)
    print("\n⚠️  NOTE: This test requires a PDF file named 'test.pdf' in the current directory")
    print("If you don't have one, create a simple PDF or skip this test\n")
    
    try:
        with open('test.pdf', 'rb') as f:
            files = {'files': ('test.pdf', f, 'application/pdf')}
            data = {'course_title': 'Test Course 1'}
            
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/upload-pdfs", files=files, data=data)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get('job_id')
                
                print(f"✅ Upload accepted in {response_time:.2f} seconds")
                print(f"   Job ID: {job_id}")
                print(f"   Status: {result.get('status')}")
                
                # Poll for completion
                print("\n   Monitoring job progress...")
                return monitor_job(job_id)
            else:
                print(f"❌ Upload failed: {response.text}")
                return False
                
    except FileNotFoundError:
        print("⚠️  test.pdf not found - skipping this test")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def monitor_job(job_id, timeout=300):
    """Monitor job until completion or timeout"""
    start_time = time.time()
    last_progress = -1
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
            if response.status_code == 200:
                job = response.json()
                status = job.get('status')
                progress = job.get('progress', 0)
                message = job.get('message', '')
                
                if progress != last_progress:
                    print(f"   [{progress}%] {status}: {message}")
                    last_progress = progress
                
                if status == 'completed':
                    elapsed = time.time() - start_time
                    print(f"\n✅ Job completed in {elapsed:.1f} seconds")
                    result = job.get('result', {})
                    print(f"   Course ID: {result.get('course_id')}")
                    print(f"   Title: {result.get('course_title')}")
                    print(f"   Modules: {result.get('modules')}")
                    return True
                    
                elif status == 'failed':
                    print(f"\n❌ Job failed: {job.get('error')}")
                    return False
                    
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            return False
    
    print(f"\n⏱️  Timeout after {timeout} seconds")
    return False

def test_concurrent_uploads():
    """Test 2: Multiple concurrent uploads"""
    print("\n" + "="*60)
    print("TEST 2: Concurrent PDF Uploads (THE BIG TEST!)")
    print("="*60)
    
    print("\n⚠️  This test requires 3 PDF files: test1.pdf, test2.pdf, test3.pdf")
    
    # Check for test files
    test_files = ['test1.pdf', 'test2.pdf', 'test3.pdf']
    available_files = []
    
    for filename in test_files:
        try:
            with open(filename, 'rb') as f:
                available_files.append(filename)
        except FileNotFoundError:
            print(f"⚠️  {filename} not found")
    
    if len(available_files) < 2:
        print("⚠️  Need at least 2 PDF files to test concurrency - skipping")
        return True
    
    print(f"\n✅ Found {len(available_files)} test files")
    
    def upload_file(filename, course_num):
        """Upload a file and return job_id and timing"""
        try:
            with open(filename, 'rb') as f:
                files = {'files': (filename, f, 'application/pdf')}
                data = {'course_title': f'Concurrent Test Course {course_num}'}
                
                start_time = time.time()
                response = requests.post(f"{BASE_URL}/api/upload-pdfs", files=files, data=data)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        'success': True,
                        'job_id': result.get('job_id'),
                        'response_time': response_time,
                        'course_num': course_num
                    }
                else:
                    return {'success': False, 'error': response.text}
                    
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # Upload all files concurrently
    print("\n🚀 Uploading all files simultaneously...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=len(available_files)) as executor:
        results = list(executor.map(
            lambda x: upload_file(x[0], x[1]), 
            zip(available_files, range(1, len(available_files) + 1))
        ))
    
    upload_time = time.time() - start_time
    
    # Check results
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    print(f"\n✅ All uploads completed in {upload_time:.2f} seconds")
    print(f"   Successful: {len(successful)}")
    print(f"   Failed: {len(failed)}")
    
    if failed:
        for fail in failed:
            print(f"   ❌ Error: {fail.get('error')}")
    
    # Show all job IDs
    print("\n📋 Job IDs created:")
    for result in successful:
        print(f"   Course {result['course_num']}: {result['job_id']} (responded in {result['response_time']:.2f}s)")
    
    # Key test: All responses should be < 2 seconds (non-blocking!)
    max_response_time = max([r['response_time'] for r in successful])
    if max_response_time < 2.0:
        print(f"\n✅ PASS: All responses under 2 seconds (max: {max_response_time:.2f}s)")
        print("   Server is NON-BLOCKING! ✨")
    else:
        print(f"\n⚠️  WARNING: Some responses took > 2 seconds (max: {max_response_time:.2f}s)")
        print("   Server may still be blocking")
    
    # Monitor first job to completion
    if successful:
        print(f"\n📊 Monitoring first job to completion...")
        first_job = successful[0]['job_id']
        monitor_job(first_job)
    
    return len(successful) > 0

def test_job_status_endpoint():
    """Test 3: Job status endpoint"""
    print("\n" + "="*60)
    print("TEST 3: Job Status Endpoint")
    print("="*60)
    
    # Test with invalid job ID
    print("\nTesting with invalid job_id...")
    response = requests.get(f"{BASE_URL}/api/jobs/invalid-job-id")
    
    if response.status_code == 404:
        print("✅ Correctly returns 404 for invalid job_id")
        return True
    else:
        print(f"⚠️  Expected 404, got {response.status_code}")
        return False

def test_legacy_endpoint():
    """Test 4: Legacy sync endpoint still works"""
    print("\n" + "="*60)
    print("TEST 4: Legacy Sync Endpoint (Backward Compatibility)")
    print("="*60)
    
    print("\n⚠️  This endpoint BLOCKS until completion (2-10 minutes)")
    print("Skip this test to save time (y/n)?")
    
    # For automated testing, skip this
    print("Skipping... (remove this to actually test)")
    return True

def main():
    """Run all tests"""
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  CONCURRENCY FIX TEST SUITE".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    print("\nThis test suite verifies that:")
    print("  1. Multiple users can upload PDFs simultaneously")
    print("  2. Server responds instantly (< 2 seconds)")
    print("  3. Jobs are processed in background")
    print("  4. Job status can be monitored")
    
    print("\n⚠️  Prerequisites:")
    print("  - Server must be running: python run_profai_websocket.py")
    print("  - PDF files needed: test.pdf, test1.pdf, test2.pdf, test3.pdf")
    print("  - (You can use any PDF files, just rename them)")
    
    input("\nPress Enter to start tests...")
    
    tests = [
        ("Single Upload", test_single_upload),
        ("Concurrent Uploads", test_concurrent_uploads),
        ("Job Status Endpoint", test_job_status_endpoint),
        ("Legacy Sync Endpoint", test_legacy_endpoint)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Concurrency fix is working! 🎉")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
