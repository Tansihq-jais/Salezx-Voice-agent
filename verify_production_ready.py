#!/usr/bin/env python3
"""
Production Readiness Verification Script

Checks that the codebase is properly cleaned up and ready for production deployment.
"""
import os
import sys
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_file_not_exists(path, description):
    """Check that a file/directory does NOT exist (should be deleted)"""
    if not os.path.exists(path):
        print(f"{GREEN}✓{RESET} {description}: Not found (good)")
        return True
    else:
        print(f"{RED}✗{RESET} {description}: Still exists at {path}")
        return False

def check_file_exists(path, description):
    """Check that a file/directory DOES exist (should be present)"""
    if os.path.exists(path):
        print(f"{GREEN}✓{RESET} {description}: Found")
        return True
    else:
        print(f"{RED}✗{RESET} {description}: Missing at {path}")
        return False

def main():
    print("=" * 60)
    print("Production Readiness Verification")
    print("=" * 60)
    print()
    
    base_dir = Path("voice_agent")
    checks_passed = 0
    checks_failed = 0
    
    # Check that development artifacts are removed
    print("Checking development artifacts are removed...")
    print("-" * 60)
    
    artifacts_to_remove = [
        (base_dir / ".git", "Git repository"),
        (base_dir / ".vscode", "VSCode config"),
        (base_dir / ".kiro", "Kiro config"),
        (base_dir / ".hypothesis", "Hypothesis test cache"),
        (base_dir / ".pytest_cache", "Pytest cache"),
        (base_dir / "__pycache__", "Python cache"),
        (base_dir / ".gitignore", "Git ignore file"),
        (base_dir / ".env.example", "Environment example"),
        (base_dir / "ai_studio_code.py", "Demo code"),
        (base_dir / "campaign_orchestrator.py", "Legacy orchestrator"),
        (base_dir / "lead_store.py", "Legacy lead store"),
        (base_dir / "start_livekit.sh", "Dev startup script (sh)"),
        (base_dir / "start_livekit.bat", "Dev startup script (bat)"),
        (base_dir / "frontend" / "src", "Frontend source"),
        (base_dir / "frontend" / "node_modules", "Node modules"),
        (base_dir / "frontend" / "package.json", "Package.json"),
        (base_dir / "frontend" / "vite.config.js", "Vite config"),
        (base_dir / "frontend" / ".gitignore", "Frontend gitignore"),
    ]
    
    for path, desc in artifacts_to_remove:
        if check_file_not_exists(path, desc):
            checks_passed += 1
        else:
            checks_failed += 1
    
    print()
    
    # Check that essential files are present
    print("Checking essential files are present...")
    print("-" * 60)
    
    essential_files = [
        (base_dir / "main.py", "Main FastAPI server"),
        (base_dir / "config.py", "Configuration"),
        (base_dir / "campaign_orchestrator_pg.py", "Campaign orchestrator (PG)"),
        (base_dir / "livekit_handler.py", "LiveKit handler"),
        (base_dir / "exotel_handler.py", "Exotel handler"),
        (base_dir / "gemini_bridge.py", "Gemini bridge"),
        (base_dir / "db.py", "MongoDB connection"),
        (base_dir / "pg_db.py", "PostgreSQL connection"),
        (base_dir / "billing.py", "Billing system"),
        (base_dir / "call_insights.py", "Call insights"),
        (base_dir / "requirements.txt", "Python dependencies"),
        (base_dir / "README.md", "Documentation"),
        (base_dir / "PRODUCTION_DEPLOYMENT.md", "Deployment guide"),
        (base_dir / "frontend" / "dist", "Built frontend"),
        (base_dir / ".env", "Environment config"),
    ]
    
    for path, desc in essential_files:
        if check_file_exists(path, desc):
            checks_passed += 1
        else:
            checks_failed += 1
    
    print()
    
    # Check for any remaining test files
    print("Checking for test files...")
    print("-" * 60)
    test_files = list(base_dir.rglob("*test*.py")) + list(base_dir.rglob("test_*"))
    if not test_files:
        print(f"{GREEN}✓{RESET} No test files found (good)")
        checks_passed += 1
    else:
        print(f"{RED}✗{RESET} Found test files:")
        for f in test_files:
            print(f"  - {f}")
        checks_failed += 1
    
    print()
    
    # Check for __pycache__ directories
    print("Checking for cache directories...")
    print("-" * 60)
    cache_dirs = list(base_dir.rglob("__pycache__")) + list(base_dir.rglob(".pytest_cache"))
    if not cache_dirs:
        print(f"{GREEN}✓{RESET} No cache directories found (good)")
        checks_passed += 1
    else:
        print(f"{RED}✗{RESET} Found cache directories:")
        for d in cache_dirs:
            print(f"  - {d}")
        checks_failed += 1
    
    print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    total_checks = checks_passed + checks_failed
    print(f"Total checks: {total_checks}")
    print(f"{GREEN}Passed: {checks_passed}{RESET}")
    if checks_failed > 0:
        print(f"{RED}Failed: {checks_failed}{RESET}")
    else:
        print(f"Failed: {checks_failed}")
    
    print()
    
    if checks_failed == 0:
        print(f"{GREEN}✓ Codebase is production-ready!{RESET}")
        return 0
    else:
        print(f"{RED}✗ Some checks failed. Please review and fix.{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
