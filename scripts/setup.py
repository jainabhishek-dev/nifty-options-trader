#!/usr/bin/env python3
"""
Setup Script for Nifty Options Trader
Installs dependencies and sets up the development environment
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"📦 {description}...")
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"✅ {description} completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}: {e}")
        return False
    return True

def setup_environment():
    """Set up the development environment"""
    print("🚀 Setting up Nifty Options Trader Development Environment")
    print("=" * 60)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    
    print(f"✅ Python {sys.version} detected")
    
    # Install dependencies
    if not run_command("pip install -r requirements.txt", "Installing dependencies"):
        return False
    
    # Install development dependencies
    dev_deps = ["pytest", "pytest-cov", "black", "flake8", "mypy"]
    for dep in dev_deps:
        if not run_command(f"pip install {dep}", f"Installing {dep}"):
            print(f"⚠️ Failed to install {dep}, continuing...")
    
    # Create necessary directories
    directories = [
        "logs",
        "data/database",
        "backtest_results"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"📁 Created directory: {directory}")
    
    # Copy environment template
    if os.path.exists(".env.template") and not os.path.exists(".env"):
        import shutil
        shutil.copy(".env.template", ".env")
        print("📄 Created .env file from template")
        print("⚠️  Please configure your API keys in .env file")
    
    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Configure your Kite Connect API keys in .env file")
    print("2. Run tests: python -m pytest tests/")
    print("3. Start the application: python web_ui/app.py")
    
    return True

if __name__ == "__main__":
    success = setup_environment()
    sys.exit(0 if success else 1)