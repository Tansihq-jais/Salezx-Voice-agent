#!/usr/bin/env python3
"""
Diagnostic script to verify Exotel integration is configured correctly.
"""
import os
import sys
import httpx
from config import (
    EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_SID,
    EXOTEL_CALLER_ID, EXOTEL_SUBDOMAIN, PUBLIC_URL,
    GEMINI_API_KEY, DATABASE_URL, MONGODB_URI
)

def check(name: str, value: str, required: bool = True) -> bool:
    """Check if a config value is set."""
    if value and value != "your-project-id" and value != "path/to/your-service-account-key.json":
        print(f"  ✓ {name}: {value[:30]}{'...' if len(value) > 30 else ''}")
        return True
    elif required:
        print(f"  ✗ {name}: NOT SET")
        return False
    else:
        print(f"  ⚠ {name}: NOT SET (optional)")
        return True

def main():
    print("=" * 80)
    print("🔍 EXOTEL INTEGRATION DIAGNOSTICS")
    print("=" * 80)
    
    all_ok = True
    
    # Check Exotel config
    print("\n1. Exotel Configuration:")
    all_ok &= check("API Key", EXOTEL_API_KEY)
    all_ok &= check("API Token", EXOTEL_API_TOKEN)
    all_ok &= check("SID", EXOTEL_SID)
    all_ok &= check("Caller ID", EXOTEL_CALLER_ID)
    all_ok &= check("Subdomain", EXOTEL_SUBDOMAIN)
    
    # Check public URL
    print("\n2. Public URL:")
    all_ok &= check("PUBLIC_URL", PUBLIC_URL)
    
    if PUBLIC_URL.startswith("http://localhost"):
        print("  ⚠ WARNING: Using localhost - Exotel won't be able to reach your server!")
        print("    You need ngrok or a public domain.")
        all_ok = False
    
    # Check Gemini
    print("\n3. Gemini API:")
    all_ok &= check("API Key", GEMINI_API_KEY)
    
    # Check databases
    print("\n4. Databases:")
    all_ok &= check("PostgreSQL", DATABASE_URL)
    all_ok &= check("MongoDB", MONGODB_URI)
    
    # Test /exoml endpoint
    print("\n5. Testing /exoml Endpoint:")
    try:
        response = httpx.get("http://localhost:8000/exoml?lead_name=Test", timeout=5)
        if response.status_code == 200:
            content = response.text
            if "<?xml" in content and "<Voicebot" in content:
                print("  ✓ /exoml returns valid XML")
                ws_url = content.split('url="')[1].split('"')[0][:50]
                print(f"  ✓ WebSocket URL: {ws_url}...")
            else:
                print("  ✗ /exoml returns invalid format (not XML)")
                print(f"    Response: {content[:100]}")
                all_ok = False
        else:
            print(f"  ✗ /exoml returned status {response.status_code}")
            all_ok = False
    except httpx.ConnectError:
        print("  ✗ Server not running on localhost:8000")
        print("    Start server with: python -m uvicorn main:app --host 0.0.0.0 --port 8000")
        all_ok = False
    except Exception as e:
        print(f"  ✗ Error testing /exoml: {e}")
        all_ok = False
    
    # Test health endpoint
    print("\n6. Testing Health Endpoint:")
    try:
        response = httpx.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Server is healthy")
            print(f"    - PostgreSQL: {data.get('postgres', 'unknown')}")
            print(f"    - MongoDB: {data.get('mongo', 'unknown')}")
            print(f"    - Gemini: {data.get('gemini', 'unknown')}")
        else:
            print(f"  ✗ Health check failed: {response.status_code}")
            all_ok = False
    except Exception as e:
        print(f"  ✗ Error testing health: {e}")
        all_ok = False
    
    # Summary
    print("\n" + "=" * 80)
    if all_ok:
        print("✅ ALL CHECKS PASSED")
        print("\nNext steps:")
        print("1. Ensure ngrok is running: ngrok http 8000")
        print("2. Update Exotel app to use: https://your-ngrok-url/exoml")
        print("3. Make a test call: python test_call.py 9098471077 Tanishq")
    else:
        print("❌ SOME CHECKS FAILED")
        print("\nFix the issues above before making test calls.")
    print("=" * 80)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
