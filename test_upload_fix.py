"""
Quick test script to validate the ChromaDB upload fix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fix_chroma_upload import ChromaDBCloudUploadFix
from core.cloud_vectorizer import CloudVectorizer
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_upload_fix():
    """Test the upload fix with a small document set"""
    try:
        # Initialize vectorizer
        vectorizer = CloudVectorizer()
        
        # Create test documents
        from langchain.schema import Document
        test_docs = [
            Document(page_content=f"Test document {i}", metadata={"source": "test.pdf", "page": i})
            for i in range(5)  # Small test set
        ]
        
        # Test the fix
        upload_fix = ChromaDBCloudUploadFix(vectorizer)
        success = upload_fix.upload_documents_with_fixes(test_docs)
        
        if success:
            print("✅ Upload fix test PASSED")
        else:
            print("❌ Upload fix test FAILED")
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_upload_fix()
