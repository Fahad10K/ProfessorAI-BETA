#!/usr/bin/env python3
"""
ProfAI WebSocket Server Startup Script
Starts both the FastAPI server and WebSocket server for optimal performance
"""

import asyncio
import threading
import time
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

  
if hasattr(sys, '_clear_type_cache'):
    sys._clear_type_cache()

# Clear any existing module cache for our services
modules_to_clear = [mod for mod in sys.modules if 'sarvam' in mod.lower()]
for mod in modules_to_clear:
    del sys.modules[mod]

def start_fastapi_server(host, port):
    """Start FastAPI server in a separate thread with proper async handling."""
    try:
        import uvicorn
        from app import app
        
        print(f"🚀 Starting FastAPI server on http://{host}:{port}")
        # Create completely isolated event loop for FastAPI thread
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run without loop parameter to avoid ProactorEventLoop error
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except Exception as e:
        print(f"❌ FastAPI startup error: {e}")
        import traceback
        traceback.print_exc()

async def start_websocket_server_async(host, port):
    """Start WebSocket server asynchronously."""
    from websocket_server import start_websocket_server
    
    print(f"🌐 Starting WebSocket server on ws://{host}:{port}")
    await start_websocket_server(host, port)

def main():
    """Main startup function."""
    fastapi_host = os.getenv("HOST", "0.0.0.0")
    fastapi_port = int(os.getenv("PORT", 5001))
    websocket_host = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
    websocket_port = int(os.getenv("WEBSOCKET_PORT", 8765))

    print("=" * 60)
    print("🎓 ProfAI - High Performance Server")
    print("=" * 60)

    try:
        import socket
        import subprocess

        def check_port(host, port, name):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                print(f"⚠️  Warning: Port {port} ({name}) appears to be in use.")
                return False
            return True

        if not check_port(fastapi_host, fastapi_port, "FastAPI") or not check_port(websocket_host, websocket_port, "WebSocket"):
            if input("\nContinue anyway? (y/N): ").lower().strip() != 'y':
                sys.exit(1)

        # Start FastAPI server using threading (fallback method)
        print("\n🚀 Starting FastAPI server...")
        fastapi_thread = threading.Thread(target=start_fastapi_server, args=(fastapi_host, fastapi_port), daemon=True)
        fastapi_thread.start()
        
        # Give FastAPI time to start
        print("Waiting for FastAPI server to initialize...")
        time.sleep(10) 
        
        print("\n" + "=" * 60)
        print("✅ FastAPI server is running.")
        print(f"   - 📱 Web UI: http://{fastapi_host}:{fastapi_port}")
        print(f"   - 🧪 WebSocket Test: http://{fastapi_host}:{fastapi_port}/profai-websocket-test")
        print("=" * 60)

        print("\n🌐 Starting WebSocket server...")
        asyncio.run(start_websocket_server_async(websocket_host, websocket_port))

    except KeyboardInterrupt:
        print("\n🛑 Shutting down servers...")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
