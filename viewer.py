#!/usr/bin/env python3
import uvicorn
import webbrowser
import sys
import time
from threading import Timer

def open_browser():
    """Wait for server to start then open browser"""
    time.sleep(1.5)
    print("🌍 Opening browser...")
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("-" * 50)
    print("📚 GitBook Local Viewer is starting...")
    print("   URL: http://localhost:8000")
    print("-" * 50)
    
    # Schedule browser opening
    Timer(1.5, open_browser).start()
    
    try:
        # Run server
        # Explicitly reload is False for production-like feel
        uvicorn.run("web_server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
    except KeyboardInterrupt:
        print("\n👋 Stopping viewer...")
        sys.exit(0)
