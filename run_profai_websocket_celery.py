"""
Production Entry Point with Celery
Runs FastAPI + WebSocket server using distributed Celery workers
"""

import logging
import uvicorn
from websocket_server import run_websocket_server_in_thread
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO if not config.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    # Start WebSocket server in background thread
    logging.info("Starting WebSocket server...")
    websocket_thread = run_websocket_server_in_thread()
    
    # Start FastAPI server (production version with Celery)
    logging.info(f"Starting FastAPI server on {config.HOST}:{config.PORT}...")
    uvicorn.run(
        "app_celery:app",  # Use Celery version
        host=config.HOST,
        port=config.PORT,
        reload=False,  # No reload in production
        log_level="info",
        access_log=True
    )
