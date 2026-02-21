"""
ChromaDB Cloud Upload Fix - Addresses all known issues with large PDF uploads
Based on ChromaDB documentation and best practices for free tier usage.
"""

import time
import logging
from typing import List
from langchain.schema import Document

class ChromaDBCloudUploadFix:
    """
    Handles ChromaDB Cloud uploads with proper rate limiting and error handling.
    Addresses the core issues causing upload failures.
    """
    
    def __init__(self, vectorizer):
        self.vectorizer = vectorizer
        self.batch_size = 200  # Conservative batch size for free tier
        self.rate_limit_delay = 2.0  # Seconds between batches
        self.max_retries = 3
        
    def upload_documents_with_fixes(self, documents: List[Document], collection_name: str = "profai_documents"):
        """
        Upload documents with all known fixes applied:
        1. Proper batching (200 docs per batch)
        2. Rate limiting between batches
        3. Exponential backoff on failures
        4. Progress tracking
        5. Partial failure recovery
        """
        
        total_docs = len(documents)
        logging.info(f"Starting upload of {total_docs} documents in batches of {self.batch_size}")
        
        successful_batches = 0
        failed_batches = []
        
        # Process in batches
        for i in range(0, total_docs, self.batch_size):
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_docs + self.batch_size - 1) // self.batch_size
            
            batch = documents[i:i + self.batch_size]
            batch_size_actual = len(batch)
            
            logging.info(f"Processing batch {batch_num}/{total_batches}: {batch_size_actual} documents")
            
            # Try uploading this batch with retries
            success = self._upload_batch_with_retry(batch, batch_num)
            
            if success:
                successful_batches += 1
                logging.info(f"✅ Batch {batch_num} uploaded successfully")
            else:
                failed_batches.append(batch_num)
                logging.error(f"❌ Batch {batch_num} failed after all retries")
            
            # Rate limiting - wait between batches to avoid hitting rate limits
            if i + self.batch_size < total_docs:  # Don't wait after the last batch
                logging.info(f"Waiting {self.rate_limit_delay}s before next batch...")
                time.sleep(self.rate_limit_delay)
        
        # Summary
        logging.info(f"Upload completed: {successful_batches}/{total_batches} batches successful")
        if failed_batches:
            logging.warning(f"Failed batches: {failed_batches}")
            return False
        
        return True
    
    def _upload_batch_with_retry(self, batch: List[Document], batch_num: int) -> bool:
        """Upload a single batch with exponential backoff retry logic."""
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Extract texts and metadatas
                texts = [doc.page_content for doc in batch]
                metadatas = [doc.metadata for doc in batch]
                
                # Use the existing vectorizer's add_texts method
                self.vectorizer.vector_store.add_texts(
                    texts=texts,
                    metadatas=metadatas
                )
                
                return True
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a quota/rate limit error
                if "quota" in error_msg or "rate" in error_msg or "limit" in error_msg:
                    wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                    logging.warning(f"Batch {batch_num}, attempt {attempt}: Rate limit hit. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # Check if it's a timeout error
                elif "timeout" in error_msg or "connection" in error_msg:
                    wait_time = 5 * attempt  # Linear backoff for connection issues
                    logging.warning(f"Batch {batch_num}, attempt {attempt}: Connection issue. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                else:
                    # Unknown error - log and retry once more
                    logging.error(f"Batch {batch_num}, attempt {attempt}: Unknown error: {e}")
                    if attempt < self.max_retries:
                        time.sleep(2)
                        continue
        
        return False

# Usage example for integration:
"""
# In your existing upload code, replace the problematic section with:

from fix_chroma_upload import ChromaDBCloudUploadFix

# Initialize the fix
upload_fix = ChromaDBCloudUploadFix(your_vectorizer_instance)

# Upload with all fixes applied
success = upload_fix.upload_documents_with_fixes(documents)

if success:
    logging.info("All documents uploaded successfully!")
else:
    logging.error("Some batches failed. Check logs for details.")
"""
