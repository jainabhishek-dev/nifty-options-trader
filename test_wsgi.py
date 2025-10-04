#!/usr/bin/env python3
"""
Test WSGI setup locally
"""
import sys
import os

# Add current directory to path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")

try:
    from web_ui.app import app
    print("✅ Flask app imported successfully")
    
    # Test app creation
    with app.app_context():
        print("✅ App context created successfully")
        
    print("✅ WSGI setup is working")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()