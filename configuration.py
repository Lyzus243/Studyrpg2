#!/usr/bin/env python3
"""
admin_debug.py - Debug and fix admin authentication issues
Run this to identify and resolve admin auth problems
"""
import os
import requests
import json
from dotenv import load_dotenv
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Lyzus308")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

print("=== ADMIN AUTHENTICATION DEBUG ===\n")

# Step 1: Check environment variables
print("1. Environment Variables:")
print(f"   ADMIN_USERNAME: {ADMIN_USERNAME}")
print(f"   ADMIN_PASSWORD: {'SET' if ADMIN_PASSWORD else 'MISSING'}")
print(f"   SECRET_KEY: {'SET' if SECRET_KEY else 'MISSING'}")
print(f"   JWT_ALGO: {JWT_ALGO}")
print(f"   BASE_URL: {BASE_URL}")

if not all([ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY]):
    print("\n❌ CRITICAL: Missing required environment variables!")
    exit(1)

# Step 2: Test server connectivity
print(f"\n2. Server Connectivity Test:")
try:
    response = requests.get(f"{BASE_URL}/docs", timeout=5)
    print(f"   Server status: ✅ ONLINE (Status: {response.status_code})")
except Exception as e:
    print(f"   Server status: ❌ OFFLINE - {e}")
    print("   Make sure your FastAPI server is running!")
    exit(1)

# Step 3: Test login endpoints
print(f"\n3. Testing Login Endpoints:")
session = requests.Session()

login_endpoints = [
    ("/admin/api/login", "form"),
    ("/auth/token", "form"), 
    ("/admin/login", "json"),
    ("/login", "form")
]

token = None
for endpoint, method in login_endpoints:
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "form":
            data = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
            resp = session.post(url, data=data, timeout=8)
        else:
            data = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
            resp = session.post(url, json=data, timeout=8)
        
        print(f"   {endpoint} ({method}): Status {resp.status_code}")
        
        if resp.status_code in (200, 201):
            try:
                json_data = resp.json()
                # Look for token in response
                for key in ["access_token", "token", "accessToken"]:
                    if key in json_data:
                        token = json_data[key]
                        print(f"   ✅ Got token from {endpoint}")
                        break
            except:
                pass
                
        if resp.status_code >= 400:
            try:
                error = resp.json()
                print(f"      Error: {error.get('detail', 'Unknown error')}")
            except:
                print(f"      Error: {resp.text[:100]}")
                
    except Exception as e:
        print(f"   {endpoint}: ❌ Failed - {e}")

if not token:
    print(f"\n❌ FAILED: Could not obtain token from any login endpoint")
    print("   This suggests either:")
    print("   - Server is not running properly")
    print("   - Admin credentials are incorrect")
    print("   - Login endpoints are not configured")
    exit(1)

# Step 4: Validate token
print(f"\n4. Token Validation:")
try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
    print(f"   ✅ Token signature valid")
    print(f"   Subject (username): {payload.get('sub')}")
    print(f"   Expires: {datetime.fromtimestamp(payload.get('exp', 0))}")
    
    if payload.get('sub') != ADMIN_USERNAME:
        print(f"   ⚠️  WARNING: Token subject doesn't match admin username")
        
except JWTError as e:
    print(f"   ❌ Token validation failed: {e}")
except Exception as e:
    print(f"   ❌ Token decode error: {e}")

# Step 5: Test admin endpoints with Bearer token
print(f"\n5. Testing Admin Endpoints:")
headers = {"Authorization": f"Bearer {token}"}

test_endpoints = [
    "/admin/debug/env-check",
    "/admin/debug/auth-test", 
    "/admin/stats",
    "/admin/users"
]

for endpoint in test_endpoints:
    url = f"{BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        print(f"   {endpoint}: Status {resp.status_code}")
        
        if resp.status_code == 200:
            print(f"   ✅ SUCCESS")
        elif resp.status_code == 401:
            try:
                error = resp.json()
                print(f"   ❌ UNAUTHORIZED: {error.get('detail')}")
            except:
                print(f"   ❌ UNAUTHORIZED: {resp.text[:100]}")
        elif resp.status_code == 403:
            print(f"   ❌ FORBIDDEN: Admin check failed")
        else:
            print(f"   ❌ ERROR: {resp.status_code}")
            
    except Exception as e:
        print(f"   {endpoint}: ❌ Request failed - {e}")

# Step 6: Test browser-style authentication (cookies)
print(f"\n6. Testing Browser/Cookie Authentication:")

# Try to get dashboard with cookies (after login)
dashboard_resp = session.get(f"{BASE_URL}/admin/dashboard")
print(f"   /admin/dashboard (cookies): Status {dashboard_resp.status_code}")

if dashboard_resp.status_code == 200:
    print(f"   ✅ Cookie auth working")
elif dashboard_resp.status_code == 401:
    print(f"   ❌ Cookie auth failed - no session cookie set")
else:
    print(f"   ❌ Dashboard error: {dashboard_resp.status_code}")

# Generate a fresh long-lived token for testing
print(f"\n7. Generated Fresh Token (30 days):")
fresh_payload = {
    "sub": ADMIN_USERNAME,
    "exp": datetime.now(timezone.utc) + timedelta(days=30)
}
fresh_token = jwt.encode(fresh_payload, SECRET_KEY, algorithm=JWT_ALGO)
print(f"   TEST_TOKEN={fresh_token}")
print(f"   Add this to your .env file for testing")

print(f"\n=== DEBUG COMPLETE ===")
print(f"\nNext steps:")
print(f"1. If login endpoints failed: Check your server logs")
print(f"2. If token validation failed: Check SECRET_KEY matches server")
print(f"3. If admin endpoints failed: Check verify_admin_token function")
print(f"4. If browser fails: Check cookie handling in admin_ui.py")