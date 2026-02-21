"""
Test script to verify ChatServiceV2 implementation
Tests agent creation, tool setup, and basic functionality
"""

import asyncio
import logging
import sys
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_imports():
    """Test that all imports work correctly."""
    logger.info("=" * 60)
    logger.info("TEST 1: Verifying Imports")
    logger.info("=" * 60)
    
    try:
        from services.chat_service_v2 import ChatServiceV2
        logger.info("✅ ChatServiceV2 imported successfully")
        
        from services.retrieval_tool import RetrievalToolFactory
        logger.info("✅ RetrievalToolFactory imported successfully")
        
        from langchain.agents import create_agent
        logger.info("✅ create_agent imported successfully")
        
        from langchain.tools import tool
        logger.info("✅ @tool decorator imported successfully")
        
        from langchain_openai import ChatOpenAI
        logger.info("✅ ChatOpenAI imported successfully")
        
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False

async def test_service_initialization():
    """Test ChatServiceV2 initialization without vector store."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Service Initialization (No Vector Store)")
    logger.info("=" * 60)
    
    try:
        from services.chat_service_v2 import ChatServiceV2
        
        # This will initialize without RAG if vector store is unavailable
        service = ChatServiceV2()
        
        logger.info(f"✅ Service initialized")
        logger.info(f"   - RAG Active: {service.is_rag_active}")
        logger.info(f"   - Agent: {service.agent is not None}")
        logger.info(f"   - Vector Store: {service.vector_store is not None}")
        logger.info(f"   - Semantic Router: {service.semantic_router is not None}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_greeting_handler():
    """Test greeting handler (no LLM/RAG needed)."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Greeting Handler")
    logger.info("=" * 60)
    
    try:
        from services.chat_service_v2 import ChatServiceV2
        
        service = ChatServiceV2()
        
        # Test greeting
        test_queries = ["hello", "hi there", "good morning"]
        
        for query in test_queries:
            logger.info(f"\n🧪 Testing: '{query}'")
            result = await service.ask_question(
                query=query,
                query_language_code="en-IN",
                session_id="test_session_greeting"
            )
            
            logger.info(f"   ✓ Route: {result['route']}")
            logger.info(f"   ✓ Answer: {result['answer'][:100]}...")
            logger.info(f"   ✓ Confidence: {result['confidence']:.2f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Greeting handler failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_general_llm():
    """Test general LLM without RAG."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: General LLM (No RAG)")
    logger.info("=" * 60)
    
    try:
        from services.chat_service_v2 import ChatServiceV2
        
        service = ChatServiceV2()
        
        # Test general question
        query = "What is the capital of France?"
        logger.info(f"\n🧪 Testing: '{query}'")
        
        result = await service.ask_question(
            query=query,
            query_language_code="en-IN",
            session_id="test_session_general"
        )
        
        logger.info(f"   ✓ Route: {result['route']}")
        logger.info(f"   ✓ Answer: {result['answer'][:150]}...")
        logger.info(f"   ✓ Sources: {result['sources']}")
        logger.info(f"   ✓ Confidence: {result['confidence']:.2f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ General LLM test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_conversation_memory():
    """Test conversation memory management."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Conversation Memory")
    logger.info("=" * 60)
    
    try:
        from services.chat_service_v2 import ChatServiceV2
        
        service = ChatServiceV2()
        session_id = "test_session_memory"
        
        # Send multiple messages
        messages = [
            "My name is Alice",
            "What's my name?",
            "I'm studying computer science",
            "What am I studying?"
        ]
        
        for i, query in enumerate(messages, 1):
            logger.info(f"\n🧪 Message {i}: '{query}'")
            
            result = await service.ask_question(
                query=query,
                query_language_code="en-IN",
                session_id=session_id
            )
            
            logger.info(f"   ✓ Answer: {result['answer'][:100]}...")
        
        # Check memory
        memory = service._get_messages(session_id)
        logger.info(f"\n✅ Memory contains {len(memory)} messages")
        logger.info(f"   Should be: {len(messages) * 2} messages (user + assistant)")
        
        return len(memory) == len(messages) * 2
    except Exception as e:
        logger.error(f"❌ Memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_message_trimming():
    """Test automatic message trimming."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Message Trimming")
    logger.info("=" * 60)
    
    try:
        from services.chat_service_v2 import ChatServiceV2
        
        service = ChatServiceV2()
        session_id = "test_session_trimming"
        
        # Send 15 messages (30 total with responses)
        # Service limits to 20 messages
        for i in range(15):
            await service.ask_question(
                query=f"Question {i+1}",
                query_language_code="en-IN",
                session_id=session_id
            )
        
        memory = service._get_messages(session_id)
        logger.info(f"✅ After 15 exchanges, memory has {len(memory)} messages")
        logger.info(f"   Max allowed: {service.max_messages} messages")
        logger.info(f"   Trimming works: {len(memory) <= service.max_messages}")
        
        return len(memory) <= service.max_messages
    except Exception as e:
        logger.error(f"❌ Trimming test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """Run all verification tests."""
    logger.info("\n" + "🧪" * 30)
    logger.info("CHATSERVICEV2 VERIFICATION TESTS")
    logger.info("🧪" * 30 + "\n")
    
    results = {}
    
    # Test 1: Imports
    results['imports'] = await test_imports()
    
    # Test 2: Initialization
    results['initialization'] = await test_service_initialization()
    
    # Test 3: Greeting Handler
    if results['initialization']:
        results['greeting'] = await test_greeting_handler()
    
    # Test 4: General LLM
    if results['initialization']:
        results['general_llm'] = await test_general_llm()
    
    # Test 5: Conversation Memory
    if results['initialization']:
        results['memory'] = await test_conversation_memory()
    
    # Test 6: Message Trimming
    if results['initialization']:
        results['trimming'] = await test_message_trimming()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    logger.info("=" * 60)
    
    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED! ChatServiceV2 is ready for integration.")
        return True
    else:
        logger.error(f"\n❌ {total - passed} test(s) failed. Fix issues before integration.")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
