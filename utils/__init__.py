"""
Utilities package for ProfAI WebSocket server.

This package contains utility modules for connection monitoring,
error handling, and other common functionality.
"""

from .connection_monitor import (
    is_normal_closure,
    is_abnormal_disconnection,
    get_disconnection_emoji,
    is_client_connected,
    is_client_disconnected,
    should_continue_streaming,
    send_chunk_safely,
    log_disconnection,
    get_connection_status,
    validate_connection_before_operation,
    ConnectionStateMonitor,
    create_connection_monitor
)

__all__ = [
    'is_normal_closure',
    'is_abnormal_disconnection', 
    'get_disconnection_emoji',
    'is_client_connected',
    'is_client_disconnected',
    'should_continue_streaming',
    'send_chunk_safely',
    'log_disconnection',
    'get_connection_status',
    'validate_connection_before_operation',
    'ConnectionStateMonitor',
    'create_connection_monitor'
]