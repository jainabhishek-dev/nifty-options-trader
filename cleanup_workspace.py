#!/usr/bin/env python3
"""
Cleanup script for workspace rebuild
Removes all debug, test, and documentation files
"""

import os
import shutil
from pathlib import Path

def cleanup_workspace():
    """Remove unnecessary files and folders"""
    
    print("🧹 CLEANING WORKSPACE FOR REBUILD")
    print("=" * 50)
    
    # Files to remove
    files_to_remove = [
        # Debug files
        "debug_instruments.py",
        "debug_nifty.py", 
        "config_check.py",
        "system_diagnostics.py",
        "optimize_system.py",
        
        # Test files
        "test_complete_system.py",
        "test_enhanced_gemini.py", 
        "test_gemini_25.py",
        "test_gemini_direct.py",
        "test_gemini_interactive.py",
        "test_minimal.py",
        
        # Old dashboard files
        "desktop_dashboard.py",
        "real_time_dashboard.py",
        "launch_dashboard.py",
        
        # Status and documentation
        "status.py",
        "AI_PIPELINE_FIXES_COMPLETE.md",
        "DATABASE_DASHBOARD_COMPLETE.md", 
        "GEMINI_PYLANCE_FIXES.md",
        "GEMINI_REASONING_ENHANCEMENT_COMPLETE.md",
        "GEMINI_SECURITY_SETUP.md",
        "MOCK_DATA_REMOVAL_COMPLETE.md",
        "PYLANCE_FIXES.md",
        "PAPER_LIVE_SEPARATION_GUIDE.md",
        "TRADING_SYSTEM_LAUNCH_GUIDE.md",
        "UI_OPTIONS.md",
    ]
    
    # Directories to remove
    dirs_to_remove = [
        "intelligence",  # AI implementation - will rebuild later
        "tests",         # Old test directory
        "__pycache__",   # Python cache
        "logs",          # Old log files
        "python",        # Unclear directory
    ]
    
    # Clean files
    removed_files = 0
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"✅ Removed file: {file_path}")
                removed_files += 1
            except Exception as e:
                print(f"❌ Failed to remove {file_path}: {e}")
        else:
            print(f"⚠️  File not found: {file_path}")
    
    # Clean directories
    removed_dirs = 0
    for dir_path in dirs_to_remove:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"✅ Removed directory: {dir_path}/")
                removed_dirs += 1
            except Exception as e:
                print(f"❌ Failed to remove {dir_path}: {e}")
        else:
            print(f"⚠️  Directory not found: {dir_path}")
    
    # Clean data directories (keep structure, remove files)
    data_dirs = ["data/historical", "data/live", "data/news"]
    for data_dir in data_dirs:
        if os.path.exists(data_dir):
            for file in os.listdir(data_dir):
                file_path = os.path.join(data_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"✅ Cleaned data file: {file_path}")
    
    print(f"\n📊 CLEANUP SUMMARY:")
    print(f"   Files removed: {removed_files}")
    print(f"   Directories removed: {removed_dirs}")
    print(f"   Workspace cleaned and ready for rebuild!")
    
    # Show remaining useful files
    print(f"\n📁 KEPT USEFUL FILES:")
    useful_files = [
        "main.py",
        "auth_handler.py", 
        "requirements.txt",
        "access_token.txt",
        ".env",
        "README.md",
        "REBUILD_PLAN.md"
    ]
    
    for file in useful_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
    
    print(f"\n📁 KEPT USEFUL DIRECTORIES:")
    useful_dirs = ["config/", "database/", "utils/", "strategies/", "risk_management/", "backtest/", "data/", "venv/"]
    for dir_name in useful_dirs:
        if os.path.exists(dir_name):
            print(f"   ✅ {dir_name}")

if __name__ == "__main__":
    cleanup_workspace()
    print(f"\n🎉 WORKSPACE CLEANUP COMPLETE!")
    print(f"Ready to start Phase 1 implementation!")