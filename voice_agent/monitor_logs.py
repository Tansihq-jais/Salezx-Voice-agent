#!/usr/bin/env python3
"""
Real-time log monitor for debugging Exotel calls.
Shows WebSocket connections, call events, and errors.
"""
import sys
import time
import logging
from datetime import datetime

# Configure logging to show everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

def monitor():
    print("=" * 80)
    print("🔍 EXOTEL CALL MONITOR")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nWatching for:")
    print("  • /exoml endpoint calls")
    print("  • WebSocket connections")
    print("  • Call status callbacks")
    print("  • Gemini bridge events")
    print("\nPress Ctrl+C to stop\n")
    print("-" * 80)
    
    # Import after logging is configured
    from main import app
    import uvicorn
    
    # Run server with detailed logging
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
    )

if __name__ == "__main__":
    try:
        monitor()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("Monitor stopped")
        print("=" * 80)
        sys.exit(0)
