"""
Test script to verify conversation memory works correctly
"""

import requests
import time

BASE_URL = "http://localhost:5003"

def test_conversation():
    print("=" * 60)
    print("Testing Conversation Memory")
    print("=" * 60)
    
    # Request 1: Introduce myself
    print("\n🧪 Test 1: Introduce myself")
    print("Message: 'Hi, my name is Alice and I'm studying robotics'")
    
    response1 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "Hi, my name is Alice and I'm studying robotics",
        "language": "en-IN"
    })
    
    data1 = response1.json()
    session_id = data1['session_id']
    
    print(f"✅ Session ID: {session_id}")
    print(f"📝 Answer: {data1['answer'][:150]}...")
    
    time.sleep(1)
    
    # Request 2: Ask about my name (should remember)
    print("\n🧪 Test 2: Ask 'What's my name?'")
    print(f"Using session_id: {session_id}")
    
    response2 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "What's my name?",
        "language": "en-IN",
        "session_id": session_id  # ✅ REUSE session_id
    })
    
    data2 = response2.json()
    print(f"📝 Answer: {data2['answer'][:200]}...")
    
    if "Alice" in data2['answer'] or "alice" in data2['answer']:
        print("✅ PASS: Agent remembered my name!")
    else:
        print("❌ FAIL: Agent didn't remember my name")
    
    time.sleep(1)
    
    # Request 3: Ask what I'm studying (should remember)
    print("\n🧪 Test 3: Ask 'What am I studying?'")
    print(f"Using session_id: {session_id}")
    
    response3 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "What am I studying?",
        "language": "en-IN",
        "session_id": session_id  # ✅ REUSE session_id
    })
    
    data3 = response3.json()
    print(f"📝 Answer: {data3['answer'][:200]}...")
    
    if "robotics" in data3['answer'].lower():
        print("✅ PASS: Agent remembered what I'm studying!")
    else:
        print("❌ FAIL: Agent didn't remember what I'm studying")
    
    time.sleep(1)
    
    # Request 4: Test without session_id (should NOT remember)
    print("\n🧪 Test 4: Ask 'What's my name?' WITHOUT session_id")
    print("NOT sending session_id (new conversation)")
    
    response4 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "What's my name?",
        "language": "en-IN"
        # No session_id - should get new session
    })
    
    data4 = response4.json()
    new_session_id = data4['session_id']
    print(f"✅ New Session ID: {new_session_id}")
    print(f"📝 Answer: {data4['answer'][:200]}...")
    
    if "Alice" not in data4['answer'] and "alice" not in data4['answer']:
        print("✅ PASS: New session doesn't have old memory (correct!)")
    else:
        print("❌ FAIL: New session has old memory (shouldn't happen)")
    
    print("\n" + "=" * 60)
    print("Conversation Memory Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_conversation()
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to server at http://localhost:5003")
        print("Make sure the app is running: python app_celery.py")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
