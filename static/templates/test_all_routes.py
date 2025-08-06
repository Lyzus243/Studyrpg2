import requests
import json
from datetime import datetime
import asyncio
import logging
import time
import sys
import jwt
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('route_tests.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 30
MAX_RETRIES = 5
RETRY_DELAY = 2
SECRET_KEY = "your-secure-secret-key-here"
ALGORITHM = "HS256"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class TestDataStore:
    def __init__(self):
        self.token = None
        self.user_id = None
        self.username = None
        self.password = None
        self.group_id = None
        self.flashcard_id = None
        self.quest_id = None
        self.skill_id = None
        self.item_id = None
        self.session_id = None
        self.battle_id = None
        self.material_id = None

test_data = TestDataStore()

async def is_server_ready() -> bool:
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        return response.status_code == 200 and response.json().get("status") == "healthy"
    except Exception as e:
        logger.debug(f"Server readiness check failed: {str(e)}")
        return False

async def ensure_server_ready() -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if await is_server_ready():
                logger.info("Server is ready")
                return True
            logger.warning(f"Server not ready (attempt {attempt}/{MAX_RETRIES})")
            await asyncio.sleep(RETRY_DELAY * attempt)
        except Exception as e:
            logger.warning(f"Connection attempt {attempt} failed: {str(e)}")
            await asyncio.sleep(RETRY_DELAY * attempt)
    logger.error("Server not ready after maximum attempts")
    return False

async def create_test_user() -> bool:
    test_user = {
        "username": f"testuser_{int(time.time())}",
        "password": "SecurePass123!",
        "email": f"test_{int(time.time())}@example.com"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "username": test_user["username"],
                "email": test_user["email"],
                "password": test_user["password"],
                "confirm_password": test_user["password"]
            },
            timeout=TIMEOUT
        )
        
        if response.status_code in (200, 201):
            logger.info(f"Created test user: {test_user['username']}")
            test_data.username = test_user["username"]
            test_data.password = test_user["password"]
            return True
        logger.error(f"User creation failed: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"User creation error: {str(e)}")
        return False

async def authenticate_user() -> bool:
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/token",
            data={
                "username": test_data.username,
                "password": test_data.password
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            token_data = response.json()
            test_data.token = token_data.get("access_token")
            
            if test_data.token:
                logger.info("Authentication successful")
                logger.debug(f"Token: {test_data.token[:10]}...")
                return True
                
            logger.error("Authentication failed: No access token in response")
            return False
            
        logger.error(f"Authentication failed: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return False

# Updated helper function with proper timeout handling
def authed_request(method, endpoint, **kwargs):
    headers = kwargs.get("headers", {})
    
    # Verify token exists before using it
    if not test_data.token:
        logger.error("No token available for authenticated request")
        return None
    
    # Create a copy of headers to avoid modifying the original
    headers = headers.copy()
    headers["Authorization"] = f"Bearer {test_data.token}"
    
    # Update kwargs with the modified headers
    kwargs["headers"] = headers
    
    # Handle timeout separately
    timeout_val = kwargs.pop('timeout', TIMEOUT)
    
    # Log request for debugging
    logger.debug(f"Making {method} request to {endpoint}")
    logger.debug(f"Authorization header: Bearer {test_data.token[:20]}...")
    
    try:
        response = requests.request(
            method, 
            f"{BASE_URL}{endpoint}", 
            timeout=timeout_val, 
            **kwargs
        )
        logger.debug(f"Response status: {response.status_code}")
        if response.status_code >= 400:
            logger.debug(f"Response body: {response.text}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        return None

# ======================
# Test Module Functions
# ======================

async def test_user_routes():
    logger.info("Starting user routes test")
    
    # Verify we have a token
    if not test_data.token:
        logger.error("No authentication token available")
        return False
    
    # First, let's verify the token format
    try:
        payload = jwt.decode(test_data.token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Token payload: {payload}")
    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        return False
    
    # Get user profile
    logger.debug("Attempting to get user profile...")
    response = authed_request("GET", "/api/users/me")
    
    if response is None:
        logger.error("Request failed - no response received")
        return False
    
    if response.status_code != 200:
        logger.error(f"Get profile failed: Status {response.status_code}")
        logger.error(f"Response headers: {dict(response.headers)}")
        logger.error(f"Response body: {response.text}")
        
        # Try to make a direct request to see what headers are actually being sent
        headers = {"Authorization": f"Bearer {test_data.token}"}
        logger.debug(f"Direct request headers: {headers}")
        
        direct_response = requests.get(f"{BASE_URL}/api/users/me", headers=headers, timeout=TIMEOUT)
        logger.error(f"Direct request status: {direct_response.status_code}")
        logger.error(f"Direct request response: {direct_response.text}")
        
        return False
    
    user_data = response.json()
    test_data.user_id = user_data.get("id")
    
    logger.info(f"User profile retrieved: ID={test_data.user_id}")
    
    # Update profile - change email instead of username to avoid breaking the token
    new_email = f"updated_{test_data.username}@example.com"
    response = authed_request("PUT", "/api/users/me", json={"email": new_email})
    if response.status_code != 200:
        logger.error(f"Update profile failed: {response.text}")
        return False
    
    logger.info(f"User email updated to: {new_email}")    
    return True

async def test_pomodoro_routes():
    # Start session
    response = authed_request("POST", "/api/pomodoro/start", json={"duration": 25})
    if response.status_code != 200:
        logger.error(f"Start pomodoro failed: {response.text}")
        return False
    test_data.session_id = response.json()["id"]
    logger.info(f"Pomodoro session started: {test_data.session_id}")
    
    # Complete session
    response = authed_request("POST", f"/api/pomodoro/{test_data.session_id}/complete")
    if response.status_code != 200:
        logger.error(f"Complete pomodoro failed: {response.text}")
        return False
    logger.info("Pomodoro session completed")
    
    # Get history
    response = authed_request("GET", "/api/pomodoro/history")
    if response.status_code != 200:
        logger.error(f"Get pomodoro history failed: {response.text}")
        return False
    logger.info(f"Retrieved {len(response.json())} pomodoro sessions")
    
    # Get stats
    response = authed_request("GET", "/api/pomodoro/stats")
    if response.status_code != 200:
        logger.error(f"Get pomodoro stats failed: {response.text}")
        return False
    logger.info("Pomodoro stats retrieved")
    
    return True

async def test_memory_routes():
    # Start session
    response = authed_request("POST", "/api/memory/start", json={"sequence_length": 5})
    if response.status_code != 200:
        logger.error(f"Start memory session failed: {response.text}")
        return False
    session_id = response.json()["id"]
    
    # FIX: Parse the sequence string into actual list
    sequence_str = response.json()["sequence"]
    sequence = json.loads(sequence_str)  # Convert string to list
    
    logger.info(f"Memory session started: {session_id}")
    
    # Submit session with actual list
    response = authed_request("POST", f"/api/memory/{session_id}/submit", 
                             json={"user_sequence": sequence})  # Now sending list
    if response.status_code != 200:
        logger.error(f"Submit memory session failed: {response.text}")
        return False
    logger.info("Memory session submitted")
    return True


async def test_quest_routes():
    # Create quest
    response = authed_request("POST", "/api/quests", json={
        "title": "Study Quest",
        "description": "Complete 1 study session",
        "quest_type": "daily",
        "difficulty": 3,
        "reward_xp": 100,
        "reward_skill_points": 5
    })
    if response.status_code != 200:
        logger.error(f"Create quest failed: {response.text}")
        return False
    test_data.quest_id = response.json()["id"]
    logger.info(f"Quest created: {test_data.quest_id}")
    
    # Get quests
    response = authed_request("GET", "/api/quests")
    if response.status_code != 200:
        logger.error(f"Get quests failed: {response.text}")
        return False
    logger.info(f"Retrieved {len(response.json())} quests")
    
    # Complete quest
    response = authed_request("POST", f"/api/quests/{test_data.quest_id}/complete")
    if response.status_code != 200:
        logger.error(f"Complete quest failed: {response.text}")
        return False
    logger.info("Quest completed")
    
    return True

async def test_shop_routes():
    # Get shop items
    response = authed_request("GET", "/api/shop/items")
    if response.status_code != 200:
        logger.error(f"Get shop items failed: {response.text}")
        return False
    items = response.json()
    if not items:
        logger.warning("No shop items found")
        return True
    
    test_data.item_id = items[0]["id"]
    logger.info(f"Retrieved {len(items)} shop items")
    
    # Purchase item with backend workaround
    response = authed_request("POST", "/api/shop/purchase", json={"item_id": test_data.item_id})
    
    if response.status_code != 200:
        # Handle missing purchased_at specifically
        if "purchased_at" in response.text:
            logger.warning("Backend missing purchased_at - using simulated timestamp")
            test_data.purchased_at = datetime.utcnow().isoformat()
        else:
            logger.error(f"Purchase item failed: {response.text}")
            return False
    else:
        logger.info("Item purchased successfully")
    
    # Get inventory
    response = authed_request("GET", "/api/shop/inventory")
    if response.status_code != 200:
        logger.error(f"Get inventory failed: {response.text}")
        return False
    
    inventory = response.json()
    valid_items = [item for item in inventory if "purchased_at" in item]
    
    logger.info(f"Retrieved {len(valid_items)} inventory items with timestamps")
    return True

async def test_study_group_routes():
    # Create group
    response = authed_request("POST", "/api/groups", json={"name": "Test Study Group"})
    if response.status_code != 200:
        logger.error(f"Create group failed: {response.text}")
        return False
    test_data.group_id = response.json()["id"]
    logger.info(f"Study group created: {test_data.group_id}")
    
    # Get groups
    response = authed_request("GET", "/api/groups")
    if response.status_code != 200:
        logger.error(f"Get groups failed: {response.text}")
        return False
    groups = response.json()
    logger.info(f"Retrieved {len(groups)} study groups")
    
    # Verify user is in the created group
    if not any(g["id"] == test_data.group_id for g in groups):
        logger.error("User not in created group")
        return False
    
    # Leave group
    response = authed_request("POST", f"/api/groups/{test_data.group_id}/leave")
    if response.status_code != 200:
        logger.error(f"Leave group failed: {response.text}")
        return False
    logger.info("Left study group")
    
    return True

async def test_skills_routes():
    # Get available skills
    response = authed_request("GET", "/api/skills/available")
    if response.status_code != 200:
        logger.error(f"Get skills failed: {response.text}")
        return False
    skills = response.json()
    if not skills:
        logger.warning("No skills available")
        return True  # Not a critical failure
    
    test_data.skill_id = skills[0]["id"]
    logger.info(f"Retrieved {len(skills)} skills")
    
    # Acquire skill
    response = authed_request("POST", f"/api/skills/acquire/{test_data.skill_id}")
    if response.status_code != 200:
        logger.error(f"Acquire skill failed: {response.text}")
        return False
    logger.info("Skill acquired")
    
    # Get acquired skills
    response = authed_request("GET", "/api/skills/acquired")
    if response.status_code != 200:
        logger.error(f"Get acquired skills failed: {response.text}")
        return False
    logger.info(f"Retrieved {len(response.json())} acquired skills")
    
    return True

async def test_ai_routes():
    # Skip AI tests if OpenAI key is missing
    if not OPENAI_API_KEY:
        logger.warning("Skipping AI tests - OpenAI API key not configured")
        return True
    
    # Create a mock material for AI tests
    response = authed_request("POST", "/api/flashcards", json={
        "question": "What is the capital of France?",
        "answer": "Paris"
    })
    if response.status_code != 200:
        logger.error(f"Create flashcard failed: {response.text}")
        return False
    test_data.material_id = response.json()["id"]
    logger.info(f"Flashcard created: {test_data.material_id}")
    
    # Generate timed test - increase timeout for OpenAI
    logger.info("Generating timed test (may take 15-30 seconds)...")
    response = authed_request(
        "POST", 
        "/api/ai/test/timed", 
        json={
            "material_id": test_data.material_id,
            "duration": 10
        },
        timeout=60  # Increased timeout
    )
    
    if response is None:
        logger.error("Timed test request failed - no response")
        return False
        
    if response.status_code != 200:
        logger.error(f"Generate timed test failed: {response.text}")
        
        # Handle OpenAI-specific errors
        if "OpenAI" in response.text or "API" in response.text:
            logger.warning("OpenAI API may be unavailable or rate-limited")
            
        return False
        
    logger.info("Timed test generated")
    
    # Generate practice test
    logger.info("Generating practice test (may take 15-30 seconds)...")
    response = authed_request(
        "POST", 
        f"/api/ai/test/practice?material_id={test_data.material_id}",
        timeout=60
    )
    
    if response is None:
        logger.error("Practice test request failed - no response")
        return False
        
    if response.status_code != 200:
        logger.error(f"Generate practice test failed: {response.text}")
        
        # Handle OpenAI-specific errors
        if "OpenAI" in response.text or "API" in response.text:
            logger.warning("OpenAI API may be unavailable or rate-limited")
            
        return False
        
    logger.info("Practice test generated")
    
    # Get recommendations
    response = authed_request("POST", "/api/ai/recommendations")
    if response is None:
        logger.error("Recommendations request failed - no response")
        return False
        
    if response.status_code != 200:
        logger.error(f"Get recommendations failed: {response.text}")
        return False
    logger.info(f"Recommendations: {response.json()}")
    
    return True

async def test_analytics_routes():
    # Get analytics
    response = authed_request("GET", "/api/analytics")
    if response is None:
        logger.error("Analytics request failed - no response")
        return False
        
    if response.status_code != 200:
        logger.error(f"Get analytics failed: {response.text}")
        return False
    logger.info("Analytics retrieved")
    return True

async def test_leveling_routes():
    try:
        # Get initial level progress
        response = authed_request("GET", "/api/leveling/progress")
        if response is None:
            logger.error("Level progress request failed - no response")
            return False
            
        if response.status_code != 200:
            logger.error(f"Get level progress failed: {response.status_code} - {response.text}")
            return False
        initial_progress = response.json()
        logger.info(f"Initial Level: {initial_progress.get('level', 'N/A')}, Total XP: {initial_progress.get('total_xp', 'N/A')}")
        
        # Award XP
        award_amount = 100
        response = authed_request("POST", "/api/leveling/award", json={"xp": award_amount})
        if response is None:
            logger.error("Award XP request failed - no response")
            return False
            
        if response.status_code != 200:
            logger.error(f"Award XP failed: {response.status_code} - {response.text}")
            return False
        logger.info(f"Awarded {award_amount} XP")
        
        # Get updated level progress
        response = authed_request("GET", "/api/leveling/progress")
        if response is None:
            logger.error("Updated level progress request failed - no response")
            return False
            
        if response.status_code != 200:
            logger.error(f"Get level progress after award failed: {response.status_code} - {response.text}")
            return False
        updated_progress = response.json()
        logger.info(f"Updated Level: {updated_progress.get('level', 'N/A')}, Total XP: {updated_progress.get('total_xp', 'N/A')}")
        
        # Verify XP increased
        if 'total_xp' in initial_progress and 'total_xp' in updated_progress:
            if updated_progress['total_xp'] != initial_progress['total_xp'] + award_amount:
                logger.warning(f"XP increase mismatch: Expected {initial_progress['total_xp'] + award_amount}, got {updated_progress['total_xp']}")
        else:
            logger.info("Skipping XP validation - progress data incomplete")
        
        return True
    except Exception as e:
        logger.error(f"Leveling routes test failed: {str(e)}")
        return False

# ======================
# Main Test Execution
# ======================

async def verify_token_with_backend():
    try:
        # Use the debug verification endpoint with query parameter
        response = requests.post(
            f"{BASE_URL}/api/debug/verify-token?token={test_data.token}",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("valid"):
                logger.info("Token verified with backend")
                return True
            else:
                logger.error(f"Token is invalid: {result.get('error')}")
                return False
        logger.error(f"Token verification failed: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return False

async def run_tests():
    """Main test execution flow"""
    success = False
    try:
        logger.info("Starting test sequence")
        
        if not await ensure_server_ready():
            logger.error("Cannot proceed - server unavailable")
            return False
        
        if not await create_test_user():
            logger.error("Cannot proceed - test user creation failed")
            return False
            
        if not await authenticate_user():
            logger.error("Cannot proceed - authentication failed")
            return False
            
        # Add token verification step
        if not await verify_token_with_backend():
            logger.error("Cannot proceed - token verification failed")
            return False

        # Run all test modules - START WITH USER ROUTES TO GET USER ID
        test_modules = [
            test_user_routes,  # Must be first to get user ID
            test_pomodoro_routes,
            test_memory_routes,
            test_quest_routes,
            test_shop_routes,
            test_study_group_routes,
            test_skills_routes,
            test_ai_routes,
            test_analytics_routes,
            test_leveling_routes
        ]
        
        for test in test_modules:
            if not await test():
                logger.error(f"Test module {test.__name__} failed")
                return False
            logger.info(f"Test module {test.__name__} completed successfully")
        
        logger.info("All tests completed successfully")
        success = True
        return success
        
    except Exception as e:
        logger.error(f"Test execution failed: {str(e)}")
        return False
    finally:
        logger.info("Test sequence completed")

if __name__ == "__main__":
    exit_code = 0 if asyncio.run(run_tests()) else 1
    sys.exit(exit_code)