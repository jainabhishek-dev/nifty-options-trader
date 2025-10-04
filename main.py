#!/usr/bin/env python3
"""
Personal Nifty Options Trading Platform
Main launcher for the web-based trading platform
"""

import os
import sys
import webbrowser
import time
from threading import Timer

def main():
    """Launch the trading platform"""
    
    print("🚀 PERSONAL NIFTY OPTIONS TRADING PLATFORM")
    print("=" * 60)
    print("Phase 1: Foundation & Core Architecture")
    print("Features: Portfolio Dashboard, Kite Integration, Web UI")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("web_ui/app.py"):
        print("❌ Error: Please run this script from the project root directory")
        print("Current directory:", os.getcwd())
        input("Press Enter to exit...")
        return 1
    
    # Check for required files
    required_files = [
        "config/settings.py",
        "core/kite_manager.py", 
        "web_ui/app.py"
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"❌ Missing required file: {file_path}")
            input("Press Enter to exit...")
            return 1
    
    print("✅ All required files found")
    print("🌐 Starting web dashboard...")
    print("📊 Dashboard will open at: http://localhost:5000")
    print("🔑 You'll need to authenticate with Kite Connect first")
    print("-" * 60)
    
    # Open browser after a short delay
    def open_browser():
        webbrowser.open('http://localhost:5000')
    
    Timer(2.0, open_browser).start()
    
    try:
        # Change to web_ui directory and run the Flask app
        os.chdir("web_ui")
        os.system(f"{sys.executable} app.py")
        
    except KeyboardInterrupt:
        print("\n🛑 Platform stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Error starting platform: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)