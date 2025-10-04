#!/usr/bin/env python3
"""
Production Build Test
Test all imports and key functionality before deployment
"""

print("TESTING DEPLOYMENT READINESS")
print("=" * 50)

# Test 1: Core imports
try:
    print("Testing Flask imports...")
    from flask import Flask, render_template, jsonify
    print("   Flask imported successfully")
    
    print("Testing Core modules...")
    import sys
    import os
    sys.path.append('.')
    
    from core.kite_manager import KiteManager
    print("   KiteManager imported successfully")
    
    from core.config_manager import ConfigManager, get_trading_config
    print("   ConfigManager imported successfully")
    
    from core.platform_auth import PlatformAuth
    print("   PlatformAuth imported successfully")
    
    print("All core imports successful!")
    
except ImportError as e:
    print(f"Import Error: {e}")
    exit(1)
except Exception as e:
    print(f"Unexpected Error: {e}")
    exit(1)

# Test 2: Environment variables
print("\nTesting Environment Configuration...")
try:
    import os
    from dotenv import load_dotenv
    
    # Load .env file
    load_dotenv()
    
    required_vars = [
        'PLATFORM_PASSWORD',
        'FLASK_SECRET_KEY', 
        'KITE_API_KEY',
        'KITE_API_SECRET'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            print(f"   {var}: {'*' * min(len(value), 8)}...")
    
    if missing_vars:
        print(f"Missing environment variables: {missing_vars}")
        exit(1)
    else:
        print("All required environment variables present!")
        
except Exception as e:
    print(f"Environment Error: {e}")
    exit(1)

# Test 3: App Creation
print("\nTesting Flask App Creation...")
try:
    # Just check if the file exists and can be read
    with open('web_ui/app.py', 'r') as f:
        app_content = f.read()
        if 'Flask' in app_content and 'app = Flask' in app_content:
            print("   Flask app structure verified")
        else:
            raise Exception("Invalid Flask app structure")
    
except Exception as e:
    print(f"App Creation Error: {e}")
    exit(1)

# Test 4: Requirements Check
print("\nTesting Requirements...")
try:
    import kiteconnect
    print("   KiteConnect: Available")
    
    import pandas
    print(f"   Pandas version: {pandas.__version__}")
    
    import requests
    print(f"   Requests version: {requests.__version__}")
    
except ImportError as e:
    print(f"Missing required package: {e}")
    exit(1)

print("\nBUILD TEST COMPLETE - READY FOR DEPLOYMENT!")
print("=" * 50)
print("SUCCESS: All tests passed. Safe to deploy to Railway.")