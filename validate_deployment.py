#!/usr/bin/env python3
"""
Deployment Validation Script
Comprehensive pre-deployment checks
"""

import os
import sys
import subprocess
from pathlib import Path

def check_files_exist():
    """Check if all required deployment files exist"""
    print("Checking deployment files...")
    
    required_files = [
        'requirements.txt',
        'Procfile', 
        'railway.toml',
        'web_ui/app.py',
        'core/kite_manager.py',
        'core/config_manager.py',
        'core/platform_auth.py',
        '.env.template',
        '.gitignore'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
        else:
            print(f"   ✓ {file_path}")
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    print("✅ All deployment files present")
    return True

def check_requirements_syntax():
    """Check requirements.txt syntax"""
    print("\nChecking requirements.txt syntax...")
    
    try:
        with open('requirements.txt', 'r') as f:
            lines = f.readlines()
        
        problematic_packages = ['pywin32', 'pywinpty', 'jupyter', 'ipython', 'notebook']
        windows_packages = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                package_name = line.split('==')[0].lower()
                if any(prob in package_name for prob in problematic_packages):
                    windows_packages.append(line)
        
        if windows_packages:
            print(f"⚠️  Windows-specific packages found: {windows_packages}")
            print("   These may cause deployment issues on Linux servers")
        else:
            print("✅ No Windows-specific packages detected")
        
        return len(windows_packages) == 0
        
    except Exception as e:
        print(f"❌ Error reading requirements.txt: {e}")
        return False

def check_procfile():
    """Check Procfile syntax"""
    print("\nChecking Procfile...")
    
    try:
        with open('Procfile', 'r') as f:
            content = f.read().strip()
        
        print(f"   Procfile content: {content}")
        
        if 'web:' not in content:
            print("❌ Procfile missing 'web:' process type")
            return False
        
        if 'app.py' not in content or 'web_ui' not in content:
            print("⚠️  Procfile might not reference correct app path")
        
        print("✅ Procfile syntax looks good")
        return True
        
    except Exception as e:
        print(f"❌ Error reading Procfile: {e}")
        return False

def check_gitignore():
    """Check .gitignore for security"""
    print("\nChecking .gitignore security...")
    
    try:
        with open('.gitignore', 'r') as f:
            content = f.read()
        
        security_items = ['.env', 'access_token.txt', '__pycache__', '*.pyc']
        missing_items = []
        
        for item in security_items:
            if item not in content:
                missing_items.append(item)
            else:
                print(f"   ✓ {item} ignored")
        
        if missing_items:
            print(f"⚠️  Missing security items in .gitignore: {missing_items}")
        else:
            print("✅ Security items properly ignored")
        
        return len(missing_items) == 0
        
    except Exception as e:
        print(f"❌ Error reading .gitignore: {e}")
        return False

def main():
    """Run all deployment checks"""
    print("DEPLOYMENT VALIDATION")
    print("=" * 50)
    
    checks = [
        check_files_exist,
        check_requirements_syntax,
        check_procfile,
        check_gitignore
    ]
    
    all_passed = True
    for check in checks:
        if not check():
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 SUCCESS: All deployment checks passed!")
        print("✅ Ready to commit and deploy to Railway")
    else:
        print("❌ FAILURE: Some checks failed")
        print("🔧 Please fix issues before deploying")
        sys.exit(1)

if __name__ == "__main__":
    main()