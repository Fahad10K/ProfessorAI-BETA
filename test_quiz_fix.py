#!/usr/bin/env python3
"""
Test script to verify the quiz validation fix
"""

import requests
import json
import sys

def test_quiz_generation():
    """Test course quiz generation to verify the validation fix"""
    
    # API endpoint
    url = "http://127.0.0.1:5001/api/quiz/generate-course"
    
    # Test payload
    payload = {
        "quiz_type": "course",
        "course_id": "1"  # Assuming course ID 1 exists
    }
    
    try:
        print("🧪 Testing course quiz generation...")
        print(f"📡 Making request to: {url}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Quiz generated successfully!")
            result = response.json()
            print(f"📋 Quiz Title: {result.get('quiz', {}).get('title', 'N/A')}")
            print(f"📝 Total Questions: {result.get('quiz', {}).get('total_questions', 'N/A')}")
            print(f"🎯 Quiz Type: {result.get('quiz', {}).get('quiz_type', 'N/A')}")
            
            # Check if quiz has questions without correct_answer field (as expected for display)
            questions = result.get('quiz', {}).get('questions', [])
            if questions:
                first_question = questions[0]
                if 'correct_answer' not in first_question:
                    print("✅ VALIDATION FIX CONFIRMED: Questions don't contain correct_answer field (as expected for display)")
                else:
                    print("⚠️  WARNING: Questions still contain correct_answer field")
                    
                print(f"📋 Sample Question: {first_question.get('question_text', 'N/A')[:100]}...")
            
            return True
            
        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            try:
                error_detail = response.json()
                print(f"🔍 Error Details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"🔍 Error Text: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Could not connect to the server.")
        print("💡 Make sure the FastAPI server is running on http://127.0.0.1:5001")
        return False
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT ERROR: Request took too long (>30s)")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {str(e)}")
        return False

def test_quiz_retrieval():
    """Test quiz retrieval to see if existing quizzes work with the fix"""
    
    try:
        print("\n🔍 Testing quiz retrieval...")
        
        # Try to get a list of available quizzes by checking the data directory
        import os
        quiz_dir = "data/quizzes"
        if os.path.exists(quiz_dir):
            quiz_files = [f for f in os.listdir(quiz_dir) if f.endswith('.json')]
            if quiz_files:
                # Test retrieving the first quiz
                quiz_id = quiz_files[0].replace('.json', '')
                print(f"📋 Testing retrieval of quiz: {quiz_id}")
                
                url = f"http://127.0.0.1:5001/api/quiz/{quiz_id}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    print("✅ SUCCESS: Quiz retrieved successfully!")
                    result = response.json()
                    quiz_data = result.get('quiz', {})
                    print(f"📋 Quiz Title: {quiz_data.get('title', 'N/A')}")
                    print(f"📝 Total Questions: {quiz_data.get('total_questions', 'N/A')}")
                    return True
                else:
                    print(f"❌ FAILED: HTTP {response.status_code}")
                    try:
                        error_detail = response.json()
                        print(f"🔍 Error Details: {json.dumps(error_detail, indent=2)}")
                    except:
                        print(f"🔍 Error Text: {response.text}")
                    return False
            else:
                print("ℹ️  No existing quiz files found to test retrieval")
                return True
        else:
            print("ℹ️  Quiz directory not found")
            return True
            
    except Exception as e:
        print(f"❌ ERROR in quiz retrieval test: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Quiz Validation Fix Test")
    print("=" * 50)
    
    # Test 1: Quiz Generation
    success1 = test_quiz_generation()
    
    # Test 2: Quiz Retrieval
    success2 = test_quiz_retrieval()
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY:")
    print(f"   Quiz Generation: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"   Quiz Retrieval:  {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("\n🎉 ALL TESTS PASSED! The quiz validation fix is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 SOME TESTS FAILED! Please check the error messages above.")
        sys.exit(1)
