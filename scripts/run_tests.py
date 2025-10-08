#!/usr/bin/env python3
"""
Test Runner Script
Runs the complete test suite with coverage reporting
"""

import subprocess
import sys
import os

def run_tests():
    """Run the test suite with coverage"""
    print("🧪 Running Nifty Options Trader Test Suite")
    print("=" * 50)
    
    # Change to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # Run tests with coverage
    try:
        print("📊 Running tests with coverage...")
        subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-v", 
            "--cov=.", 
            "--cov-report=html", 
            "--cov-report=term"
        ], check=True)
        
        print("\n✅ All tests passed!")
        print("📄 HTML coverage report generated in htmlcov/")
        
    except subprocess.CalledProcessError:
        print("❌ Some tests failed")
        return False
    
    return True

def run_linting():
    """Run code quality checks"""
    print("\n🔍 Running code quality checks...")
    
    # Run flake8
    try:
        subprocess.run([sys.executable, "-m", "flake8", ".", "--max-line-length=120"], check=True)
        print("✅ Flake8 passed")
    except subprocess.CalledProcessError:
        print("⚠️  Flake8 found issues")
    
    # Run mypy
    try:
        subprocess.run([sys.executable, "-m", "mypy", ".", "--ignore-missing-imports"], check=True)
        print("✅ MyPy passed")
    except subprocess.CalledProcessError:
        print("⚠️  MyPy found issues")

if __name__ == "__main__":
    success = run_tests()
    run_linting()
    sys.exit(0 if success else 1)