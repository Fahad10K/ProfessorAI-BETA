#!/usr/bin/env python3
"""
Clear Vectorstore Script - Safely removes old vectorstore data to fix Windows file lock issues
"""

import os
import shutil
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clear_vectorstore():
    """Clear all vectorstore data to resolve file lock issues."""
    
    # Import config to get paths
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import config
    
    logging.info("Starting vectorstore cleanup...")
    
    # Paths to clear
    paths_to_clear = [
        config.VECTORSTORE_DIR,
        config.CHROMA_DB_PATH,
        config.FAISS_DB_PATH
    ]
    
    for path in paths_to_clear:
        if os.path.exists(path):
            logging.info(f"Clearing path: {path}")
            try:
                # Try multiple times with delays for Windows
                for attempt in range(5):
                    try:
                        shutil.rmtree(path)
                        logging.info(f"Successfully cleared: {path}")
                        break
                    except Exception as e:
                        logging.warning(f"Attempt {attempt+1} failed for {path}: {e}")
                        if attempt < 4:
                            time.sleep(1.0 * (attempt + 1))
                        else:
                            logging.error(f"Could not clear {path} after 5 attempts")
            except Exception as e:
                logging.error(f"Error clearing {path}: {e}")
        else:
            logging.info(f"Path does not exist: {path}")
    
    # Recreate the directories
    logging.info("Recreating directories...")
    try:
        os.makedirs(config.VECTORSTORE_DIR, exist_ok=True)
        os.makedirs(config.CHROMA_DB_PATH, exist_ok=True)
        os.makedirs(config.FAISS_DB_PATH, exist_ok=True)
        logging.info("Directories recreated successfully")
    except Exception as e:
        logging.error(f"Error recreating directories: {e}")
    
    logging.info("Vectorstore cleanup completed!")

if __name__ == "__main__":
    clear_vectorstore()
