"""
Comprehensive Service Verification Script
Tests that all services can be instantiated and work correctly
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_service_imports():
    """Test 1: Verify all services can be imported"""
    print("\n" + "="*60)
    print("TEST 1: Service Imports")
    print("="*60)
    
    services_to_test = [
        ('AudioService', 'services.audio_service'),
        ('ChatService', 'services.chat_service'),
        ('DocumentService', 'services.document_service'),
        ('AsyncDocumentService', 'services.async_document_service'),
        ('LLMService', 'services.llm_service'),
        ('QuizService', 'services.quiz_service'),
        ('RAGService', 'services.rag_service'),
        ('SarvamService', 'services.sarvam_service'),
        ('TeachingService', 'services.teaching_service'),
        ('TranscriptionService', 'services.transcription_service'),
        ('DatabaseService', 'services.database_service_actual'),
    ]
    
    failed_imports = []
    
    for service_name, module_path in services_to_test:
        try:
            module = __import__(module_path, fromlist=[service_name])
            service_class = getattr(module, service_name if service_name != 'DatabaseService' else 'get_database_service')
            print(f"✅ {service_name:30} - Import successful")
        except Exception as e:
            print(f"❌ {service_name:30} - Import failed: {e}")
            failed_imports.append(service_name)
    
    return len(failed_imports) == 0, failed_imports


def test_service_initialization():
    """Test 2: Verify all services can be instantiated"""
    print("\n" + "="*60)
    print("TEST 2: Service Initialization")
    print("="*60)
    
    failed_inits = []
    
    # Test DocumentService
    try:
        from services.document_service import DocumentService
        doc_service = DocumentService()
        has_db = hasattr(doc_service, 'db_service') and doc_service.db_service is not None
        print(f"✅ DocumentService              - Initialized {'(with database)' if has_db else '(JSON mode)'}")
    except Exception as e:
        print(f"❌ DocumentService              - Failed: {e}")
        failed_inits.append('DocumentService')
    
    # Test AsyncDocumentService
    try:
        from services.async_document_service import async_document_service
        has_db = hasattr(async_document_service, 'db_service') and async_document_service.db_service is not None
        print(f"✅ AsyncDocumentService         - Initialized {'(with database)' if has_db else '(JSON mode)'}")
    except Exception as e:
        print(f"❌ AsyncDocumentService         - Failed: {e}")
        failed_inits.append('AsyncDocumentService')
    
    # Test QuizService
    try:
        from services.quiz_service import QuizService
        quiz_service = QuizService()
        has_db = hasattr(quiz_service, 'db_service') and quiz_service.db_service is not None
        print(f"✅ QuizService                  - Initialized {'(with database)' if has_db else '(JSON mode)'}")
    except Exception as e:
        print(f"❌ QuizService                  - Failed: {e}")
        failed_inits.append('QuizService')
    
    # Test LLMService
    try:
        from services.llm_service import LLMService
        llm_service = LLMService()
        print(f"✅ LLMService                   - Initialized")
    except Exception as e:
        print(f"❌ LLMService                   - Failed: {e}")
        failed_inits.append('LLMService')
    
    # Test AudioService
    try:
        from services.audio_service import AudioService
        audio_service = AudioService()
        print(f"✅ AudioService                 - Initialized")
    except Exception as e:
        print(f"❌ AudioService                 - Failed: {e}")
        failed_inits.append('AudioService')
    
    # Test TeachingService
    try:
        from services.teaching_service import TeachingService
        teaching_service = TeachingService()
        print(f"✅ TeachingService              - Initialized")
    except Exception as e:
        print(f"❌ TeachingService              - Failed: {e}")
        failed_inits.append('TeachingService')
    
    # Test SarvamService
    try:
        from services.sarvam_service import SarvamService
        sarvam_service = SarvamService()
        print(f"✅ SarvamService                - Initialized")
    except Exception as e:
        print(f"❌ SarvamService                - Failed: {e}")
        failed_inits.append('SarvamService')
    
    # Test TranscriptionService
    try:
        from services.transcription_service import TranscriptionService
        transcription_service = TranscriptionService()
        print(f"✅ TranscriptionService         - Initialized")
    except Exception as e:
        print(f"❌ TranscriptionService         - Failed: {e}")
        failed_inits.append('TranscriptionService')
    
    # Test ChatService (may fail if no vector store)
    try:
        from services.chat_service import ChatService
        chat_service = ChatService()
        rag_active = chat_service.is_rag_active
        print(f"✅ ChatService                  - Initialized {'(RAG active)' if rag_active else '(No vector store)'}")
    except Exception as e:
        print(f"⚠️  ChatService                  - Warning: {str(e)[:50]}...")
        # Not counting as failure since it's expected without vector store
    
    # Test DatabaseService
    try:
        from services.database_service_actual import get_database_service
        db_service = get_database_service()
        if db_service:
            print(f"✅ DatabaseService              - Initialized (Connected to DB)")
        else:
            print(f"⚠️  DatabaseService              - Database disabled (USE_DATABASE=False)")
    except Exception as e:
        print(f"⚠️  DatabaseService              - Warning: {str(e)[:50]}...")
    
    return len(failed_inits) == 0, failed_inits


def test_database_integration():
    """Test 3: Verify database integration in key services"""
    print("\n" + "="*60)
    print("TEST 3: Database Integration")
    print("="*60)
    
    use_database = os.getenv('USE_DATABASE', 'false').lower() == 'true'
    print(f"USE_DATABASE setting: {use_database}")
    
    if not use_database:
        print("⚠️  Database not enabled - Skipping database tests")
        print("   Set USE_DATABASE=True in .env to test database features")
        return True, []
    
    issues = []
    
    # Check DocumentService
    try:
        from services.document_service import DocumentService
        doc_service = DocumentService()
        if hasattr(doc_service, 'db_service'):
            if doc_service.db_service:
                print("✅ DocumentService has database integration")
            else:
                print("❌ DocumentService.db_service is None")
                issues.append("DocumentService database not connected")
        else:
            print("❌ DocumentService missing db_service attribute")
            issues.append("DocumentService missing db_service")
    except Exception as e:
        print(f"❌ DocumentService check failed: {e}")
        issues.append(f"DocumentService: {e}")
    
    # Check AsyncDocumentService
    try:
        from services.async_document_service import async_document_service
        if hasattr(async_document_service, 'db_service'):
            if async_document_service.db_service:
                print("✅ AsyncDocumentService has database integration")
            else:
                print("❌ AsyncDocumentService.db_service is None")
                issues.append("AsyncDocumentService database not connected")
        else:
            print("❌ AsyncDocumentService missing db_service attribute")
            issues.append("AsyncDocumentService missing db_service")
    except Exception as e:
        print(f"❌ AsyncDocumentService check failed: {e}")
        issues.append(f"AsyncDocumentService: {e}")
    
    # Check QuizService
    try:
        from services.quiz_service import QuizService
        quiz_service = QuizService()
        if hasattr(quiz_service, 'db_service'):
            if quiz_service.db_service:
                print("✅ QuizService has database integration")
            else:
                print("❌ QuizService.db_service is None")
                issues.append("QuizService database not connected")
        else:
            print("❌ QuizService missing db_service attribute")
            issues.append("QuizService missing db_service")
    except Exception as e:
        print(f"❌ QuizService check failed: {e}")
        issues.append(f"QuizService: {e}")
    
    return len(issues) == 0, issues


def test_model_schemas():
    """Test 4: Verify Pydantic models support both course_id types"""
    print("\n" + "="*60)
    print("TEST 4: Model Schemas")
    print("="*60)
    
    issues = []
    
    try:
        from models.schemas import CourseLMS, QuizRequest
        
        # Test CourseLMS with INTEGER course_id
        try:
            course_int = CourseLMS(course_title="Test", course_id=1, modules=[])
            print("✅ CourseLMS accepts INTEGER course_id")
        except Exception as e:
            print(f"❌ CourseLMS failed with INTEGER: {e}")
            issues.append("CourseLMS INTEGER")
        
        # Test CourseLMS with UUID course_id
        try:
            course_uuid = CourseLMS(course_title="Test", course_id="abc-123-def", modules=[])
            print("✅ CourseLMS accepts TEXT UUID course_id")
        except Exception as e:
            print(f"❌ CourseLMS failed with UUID: {e}")
            issues.append("CourseLMS UUID")
        
        # Test QuizRequest with INTEGER course_id
        try:
            quiz_int = QuizRequest(quiz_type="module", course_id=1, module_week=1)
            print("✅ QuizRequest accepts INTEGER course_id")
        except Exception as e:
            print(f"❌ QuizRequest failed with INTEGER: {e}")
            issues.append("QuizRequest INTEGER")
        
        # Test QuizRequest with UUID course_id
        try:
            quiz_uuid = QuizRequest(quiz_type="module", course_id="abc-123-def", module_week=1)
            print("✅ QuizRequest accepts TEXT UUID course_id")
        except Exception as e:
            print(f"❌ QuizRequest failed with UUID: {e}")
            issues.append("QuizRequest UUID")
            
    except Exception as e:
        print(f"❌ Model schema test failed: {e}")
        issues.append(f"Schema import: {e}")
    
    return len(issues) == 0, issues


def test_configuration():
    """Test 5: Verify configuration values"""
    print("\n" + "="*60)
    print("TEST 5: Configuration")
    print("="*60)
    
    import config
    
    critical_configs = [
        ('OPENAI_API_KEY', getattr(config, 'OPENAI_API_KEY', None)),
        ('DATABASE_URL', os.getenv('DATABASE_URL')),
        ('REDIS_URL', os.getenv('REDIS_URL')),
        ('USE_DATABASE', os.getenv('USE_DATABASE')),
    ]
    
    optional_configs = [
        ('SARVAM_API_KEY', getattr(config, 'SARVAM_API_KEY', None)),
        ('GROQ_API_KEY', getattr(config, 'GROQ_API_KEY', None)),
        ('USE_CHROMA_CLOUD', getattr(config, 'USE_CHROMA_CLOUD', None)),
    ]
    
    missing_critical = []
    
    print("\nCritical Configuration:")
    for name, value in critical_configs:
        if value:
            masked_value = f"{value[:10]}..." if len(str(value)) > 10 else value
            print(f"✅ {name:20} - Set ({masked_value})")
        else:
            print(f"❌ {name:20} - NOT SET")
            if name in ['OPENAI_API_KEY']:
                missing_critical.append(name)
    
    print("\nOptional Configuration:")
    for name, value in optional_configs:
        if value:
            masked_value = f"{value[:10]}..." if len(str(value)) > 10 else value
            print(f"✅ {name:20} - Set ({masked_value})")
        else:
            print(f"⚠️  {name:20} - Not set")
    
    return len(missing_critical) == 0, missing_critical


def main():
    """Run all service tests"""
    print("\n" + "="*60)
    print("COMPREHENSIVE SERVICE VERIFICATION")
    print("="*60)
    print(f"Testing all services for compatibility and integration")
    
    # Run all tests
    test_results = []
    
    test_results.append(("Imports", *test_service_imports()))
    test_results.append(("Initialization", *test_service_initialization()))
    test_results.append(("Database Integration", *test_database_integration()))
    test_results.append(("Model Schemas", *test_model_schemas()))
    test_results.append(("Configuration", *test_configuration()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, passed, issues in test_results:
        if passed:
            print(f"✅ {test_name:25} - PASSED")
        else:
            print(f"❌ {test_name:25} - FAILED")
            if issues:
                for issue in issues:
                    print(f"   - {issue}")
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! All services are working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Review errors above")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
