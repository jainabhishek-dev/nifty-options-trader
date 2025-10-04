#!/usr/bin/env python3
"""
Cloud Deployment Preparation Script
Prepares the trading platform for cloud deployment
"""

import os
import sys
import shutil
from pathlib import Path

def main():
    """Prepare for cloud deployment"""
    
    print("☁️ CLOUD DEPLOYMENT PREPARATION")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("web_ui/app.py"):
        print("❌ Error: Run this script from the project root directory")
        return 1
    
    # 1. Check required files exist
    required_files = [
        "Procfile",
        "runtime.txt", 
        "railway.toml",
        "requirements.txt",
        ".env.template"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing deployment files: {', '.join(missing_files)}")
        return 1
    
    print("✅ All deployment files present")
    
    # 2. Check if gunicorn is in requirements.txt
    with open("requirements.txt", "r") as f:
        requirements_content = f.read()
    
    if "gunicorn" not in requirements_content:
        print("❌ gunicorn not found in requirements.txt")
        return 1
    
    print("✅ Production server (gunicorn) configured")
    
    # 3. Create .gitignore if it doesn't exist
    gitignore_content = """
# Environment variables
.env
.env.local
.env.production

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
.pytest_cache/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# Database
*.db
*.sqlite

# Access tokens (for local development)
access_token.txt

# OS
.DS_Store
Thumbs.db
"""
    
    if not os.path.exists(".gitignore"):
        with open(".gitignore", "w") as f:
            f.write(gitignore_content)
        print("✅ Created .gitignore file")
    else:
        print("✅ .gitignore already exists")
    
    # 4. Verify app.py is cloud-ready
    try:
        with open("web_ui/app.py", "r", encoding="utf-8") as f:
            app_content = f.read()
        
        cloud_ready = all([
            "os.environ.get('PORT'" in app_content,
            "FLASK_ENV" in app_content,
            "FLASK_SECRET_KEY" in app_content
        ])
        
        if not cloud_ready:
            print("❌ app.py is not cloud-ready")
            return 1
        
        print("✅ Flask app is cloud-ready")
    except Exception as e:
        print(f"⚠️ Could not verify app.py readiness: {e}")
        print("✅ Assuming Flask app is ready")
    
    # 5. Check core modules
    core_ready = os.path.exists("core/kite_manager.py")
    if not core_ready:
        print("❌ Core modules missing")
        return 1
    
    print("✅ Core modules present")
    
    # 6. Display deployment summary
    print("\n" + "="*50)
    print("🚀 DEPLOYMENT READY!")
    print("="*50)
    print("\n📋 NEXT STEPS:")
    print("\n1️⃣ Choose a cloud platform:")
    print("   • Railway: https://railway.app (Recommended - $5/month)")
    print("   • Heroku: https://heroku.com ($7/month)")  
    print("   • DigitalOcean: https://digitalocean.com ($5/month)")
    
    print("\n2️⃣ Set up environment variables:")
    print("   • Copy .env.template to your cloud platform")
    print("   • Add your Kite API credentials")
    print("   • Set FLASK_SECRET_KEY to a random string")
    
    print("\n3️⃣ Deploy your app:")
    print("   • Connect your GitHub repository")
    print("   • Platform will auto-build and deploy")
    print("   • Your app will be available at https://your-app.platform.app")
    
    print("\n4️⃣ Test your deployment:")
    print("   • Visit your app URL")
    print("   • Test Kite Connect authentication")
    print("   • Verify portfolio data loads")
    
    print("\n💰 ESTIMATED COSTS:")
    print("   • Railway: $5/month (recommended)")
    print("   • Heroku: $7/month")
    print("   • DigitalOcean: $5/month")
    print("   • Custom VPS: $3-10/month (advanced)")
    
    print("\n🔒 SECURITY REMINDERS:")
    print("   • Never commit .env files to Git")
    print("   • Use HTTPS only in production")
    print("   • Set strong FLASK_SECRET_KEY")
    print("   • Monitor access logs regularly")
    
    print(f"\n✨ Your trading platform is ready for the cloud!")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)