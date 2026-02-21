"""
Connection Monitoring Utilities for WebSocket Connection Stability

This module provides helper functions to detect normal vs abnormal disconnections,
connection state checking utilities for WebSocket handlers, and safe chunk sending
with connection validation.

Requirements addressed: 1.1, 3.1, 4.3
"""

import logging
from typing import Optional, Union
from datetime import datetime
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, ConnectionClosedError
import websockets

# Configure logging
logger = logging.getLogger(__name__)

def is_normal_closure(exception: Exception) -> bool:
    """
    Check if a WebSocket exception represents a normal closure (codes 1000, 1001).
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if the exception represents a normal closure, False otherwise
        
    Requirements: 1.1 - Distinguish between normal closures and actual errors
    """
    if isinstance(exception, ConnectionClosedOK):
        return True
    
    if isinstance(exception, ConnectionClosed):
        # Check for normal closure codes: 1000 (OK) and 1001 (going away)
        return exception.code in (1000, 1001)
    
    # Check error message for normal closure indicators
    error_msg = str(exception).lower()
    normal_indicators = [
        "code = 1000",
        "code = 1001", 
        "going away",
        "normal closure"
    ]
    
    return any(indicator in error_msg for indicator in normal_indicators)

def is_abnormal_disconnection(exception: Exception) -> bool:
    """
    Check if a WebSocket exception represents an abnormal disconnection.
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if the exception represents an abnormal disconnection, False otherwise
        
    Requirements: 1.1 - Distinguish between normal closures and actual errors
    """
    return not is_normal_closure(exception)

def get_disconnection_emoji(exception: Exception) -> str:
    """
    Get appropriate emoji for disconnection type for logging.
    
    Args:
        exception: The exception to get emoji for
        
    Returns:
        str: Emoji representing the disconnection type
        
    Requirements: 1.1 - Provide clear visual indicators for different disconnection types
    """
    if is_normal_closure(exception):
        return "🔌"  # Normal disconnection
    else:
        return "❌"  # Error disconnection

def is_client_connected(websocket) -> bool:
    """
    Check if WebSocket client is still connected.
    
    Args:
        websocket: The WebSocket connection to check
        
    Returns:
        bool: True if client is connected, False otherwise
        
    Requirements: 3.1 - Connection state checking utilities for WebSocket handlers
    """
    if not websocket:
        return False
    
    try:
        # Check if WebSocket is closed or closing
        if hasattr(websocket, 'closed') and websocket.closed:
            return False
        
        if hasattr(websocket, 'state'):
            # WebSocket states: CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3
            return websocket.state == 1  # Only OPEN state is considered connected
        
        # Fallback check for different WebSocket implementations
        if hasattr(websocket, 'open'):
            return websocket.open
        
        return True
        
    except Exception as e:
        logger.debug(f"Error checking connection state: {e}")
        return False

def is_client_disconnected(websocket) -> bool:
    """
    Check if WebSocket client is disconnected.
    
    Args:
        websocket: The WebSocket connection to check
        
    Returns:
        bool: True if client is disconnected, False otherwise
        
    Requirements: 3.1 - Connection state checking utilities for WebSocket handlers
    """
    return not is_client_connected(websocket)

def should_continue_streaming(websocket) -> bool:
    """
    Check if streaming should continue based on connection state.
    
    Args:
        websocket: The WebSocket connection to check
        
    Returns:
        bool: True if streaming should continue, False otherwise
        
    Requirements: 3.1 - Connection state validation before sending chunks
    """
    return is_client_connected(websocket)

async def send_chunk_safely(websocket, chunk_data: dict, client_id: str = "unknown") -> bool:
    """
    Safely send a chunk to the WebSocket client with connection validation.
    
    Args:
        websocket: The WebSocket connection
        chunk_data: The data to send as a dictionary
        client_id: Client identifier for logging
        
    Returns:
        bool: True if chunk was sent successfully, False if client disconnected
        
    Requirements: 3.1 - Safe chunk sending with connection validation
    """
    if not is_client_connected(websocket):
        logger.info(f"🔌 Client {client_id} already disconnected - skipping chunk")
        return False
    
    try:
        import json
        await websocket.send(json.dumps(chunk_data))
        return True
        
    except ConnectionClosed as e:
        log_disconnection(client_id, e, "while sending chunk")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending chunk to {client_id}: {e}")
        return False

def log_disconnection(client_id: str, exception: Exception, context: str = "") -> None:
    """
    Log disconnection with appropriate emoji and message.
    
    Args:
        client_id: Client identifier
        exception: The disconnection exception
        context: Additional context for the log message
        
    Requirements: 1.1 - Distinguish between normal closures and actual errors in logging
    """
    emoji = get_disconnection_emoji(exception)
    
    if is_normal_closure(exception):
        if hasattr(exception, 'code'):
            logger.info(f"{emoji} Client {client_id} disconnected normally (code {exception.code}) {context}")
        else:
            logger.info(f"{emoji} Client {client_id} disconnected normally {context}")
    else:
        if hasattr(exception, 'code'):
            logger.warning(f"{emoji} Client {client_id} disconnected with error (code {exception.code}) {context}")
        else:
            logger.error(f"{emoji} Client {client_id} disconnected with error: {exception} {context}")

def get_connection_status(websocket, client_id: str) -> dict:
    """
    Get detailed connection status information.
    
    Args:
        websocket: The WebSocket connection
        client_id: Client identifier
        
    Returns:
        dict: Connection status information
        
    Requirements: 4.3 - Detailed diagnostic information for connection issues
    """
    status = {
        "client_id": client_id,
        "is_connected": is_client_connected(websocket),
        "timestamp": datetime.utcnow().isoformat(),
        "state": "unknown",
        "closed": None,
        "open": None
    }
    
    if websocket:
        try:
            if hasattr(websocket, 'state'):
                state_names = {0: "CONNECTING", 1: "OPEN", 2: "CLOSING", 3: "CLOSED"}
                status["state"] = state_names.get(websocket.state, f"UNKNOWN({websocket.state})")
            
            if hasattr(websocket, 'closed'):
                status["closed"] = websocket.closed
                
            if hasattr(websocket, 'open'):
                status["open"] = websocket.open
                
        except Exception as e:
            status["error"] = str(e)
    
    return status

def validate_connection_before_operation(websocket, client_id: str, operation: str) -> bool:
    """
    Validate connection state before performing an operation.
    
    Args:
        websocket: The WebSocket connection
        client_id: Client identifier
        operation: Description of the operation being performed
        
    Returns:
        bool: True if connection is valid for operation, False otherwise
        
    Requirements: 3.1 - Connection state validation before operations
    """
    if not is_client_connected(websocket):
        logger.info(f"🔌 Client {client_id} disconnected - skipping {operation}")
        return False
    
    return True

class ConnectionStateMonitor:
    """
    Monitor connection state and provide utilities for connection management.
    
    Requirements: 3.1, 4.3 - Connection state monitoring and diagnostic information
    """
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.connection_start_time = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.chunks_sent = 0
        self.bytes_sent = 0
        self.normal_disconnections = 0
        self.error_disconnections = 0
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def record_chunk_sent(self, chunk_size: int):
        """Record that a chunk was sent successfully."""
        self.chunks_sent += 1
        self.bytes_sent += chunk_size
        self.update_activity()
    
    def record_disconnection(self, exception: Exception):
        """Record a disconnection event."""
        if is_normal_closure(exception):
            self.normal_disconnections += 1
        else:
            self.error_disconnections += 1
    
    def get_metrics(self) -> dict:
        """Get connection metrics."""
        now = datetime.utcnow()
        session_duration = (now - self.connection_start_time).total_seconds()
        time_since_activity = (now - self.last_activity).total_seconds()
        
        return {
            "client_id": self.client_id,
            "session_duration_seconds": session_duration,
            "time_since_last_activity_seconds": time_since_activity,
            "chunks_sent": self.chunks_sent,
            "bytes_sent": self.bytes_sent,
            "normal_disconnections": self.normal_disconnections,
            "error_disconnections": self.error_disconnections,
            "total_disconnections": self.normal_disconnections + self.error_disconnections
        }
    
    def is_healthy_connection(self, max_idle_seconds: int = 300) -> bool:
        """
        Check if connection is healthy based on activity.
        
        Args:
            max_idle_seconds: Maximum idle time before considering connection stale
            
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        now = datetime.utcnow()
        idle_time = (now - self.last_activity).total_seconds()
        return idle_time <= max_idle_seconds

def create_connection_monitor(client_id: str) -> ConnectionStateMonitor:
    """
    Create a new connection state monitor for a client.
    
    Args:
        client_id: Client identifier
        
    Returns:
        ConnectionStateMonitor: New monitor instance
        
    Requirements: 4.3 - Connection monitoring utilities
    """
    return ConnectionStateMonitor(client_id)