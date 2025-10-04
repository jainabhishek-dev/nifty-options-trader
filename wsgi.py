#!/usr/bin/env python3
"""
WSGI Entry Point for Production Deployment
Proper production entry point for the trading platform
"""

import os
import sys
import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app from the existing app.py
from web_ui.app import app

# Configure for production
app.config['ENV'] = 'production'
app.config['DEBUG'] = False

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)