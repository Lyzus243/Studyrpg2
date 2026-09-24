from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_async_session
from app.models import User, BossBattle, Quest
from app.models_feedback import Feedback
from fastapi.templating import Jinja2Templates
from pathlib import Path
import logging
import os
from dotenv import load_dotenv
from app.routers.auth import get_current_user_optional, get_current_user, create_access_token, verify_token
from datetime import timedelta
from jose import jwt, JWTError
# In admin.py, replace the duplicate functions with:
from app.admin_auth import verify_admin_token, require_admin

# Remove the local definitions of these functions
# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Admin credentials from .env (same as admin.py)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Lyzus308")  # ✅ ADD DEFAULT
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234567")  # ✅ ADD DEFAULT
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "pumlezerti@necub.com")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGO", "HS256")

# Setup templates directory
BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "static" / "templates" / "admin"
templates = Jinja2Templates(directory=TEMPLATE_DIR)

admin_ui = APIRouter()


@admin_ui.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """
    Admin login page (served via Jinja template).
    """
    try:
        return templates.TemplateResponse("admin/login.html", {"request": request})
    except Exception:
        # Fallback inline HTML if template not found - FIXED
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Login - StudyRPG</title>
            <style>
                body {
                    background: #36393f;
                    font-family: 'Whitney', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    color: #ffffff;
                }
                .login-container {
                    background: #2f3136;
                    padding: 2rem;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    min-width: 400px;
                }
                .form-group { margin-bottom: 1rem; }
                input {
                    width: 100%;
                    padding: 12px;
                    border: 1px solid #202225;
                    border-radius: 4px;
                    background: #40444b;
                    color: white;
                    font-size: 1rem;
                    box-sizing: border-box;
                }
                button {
                    width: 100%;
                    background: #7289da;
                    color: white;
                    padding: 12px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: background 0.3s ease;
                }
                button:hover {
                    background: #677bc4;
                }
                button:disabled {
                    background: #4e5d94;
                    cursor: not-allowed;
                }
                h1 { color: #7289da; text-align: center; }
                .error { color: #ed4245; text-align: center; margin-bottom: 1rem; }
                .success { color: #43b581; text-align: center; margin-bottom: 1rem; }
                a { color: #7289da; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
        <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="/static/css/journey.css?v=1">
        <script src="/static/js/journey.js?v=1" defer></script>
        </head>
        <body>
            <div class="login-container">
                <h1>🐉 Admin Portal Login</h1>
                <div id="error-message" class="error" style="display: none;"></div>
                <div id="success-message" class="success" style="display: none;"></div>
                <form id="login-form">
                    <div class="form-group">
                        <input type="text" id="username" placeholder="Username" required>
                    </div>
                    <div class="form-group">
                        <input type="password" id="password" placeholder="Password" required>
                    </div>
                    <button type="submit" id="login-btn">Login to Admin Portal</button>
                </form>
                <div style="text-align: center; margin-top: 1rem;">
                    <a href="/">← Back to StudyRPG</a>
                </div>
            </div>
            <script>
                document.getElementById('login-form').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;
                    const errorDiv = document.getElementById('error-message');
                    const successDiv = document.getElementById('success-message');
                    const loginBtn = document.getElementById('login-btn');
                    
                    // Hide previous messages
                    errorDiv.style.display = 'none';
                    successDiv.style.display = 'none';
                    
                    // Disable button during login
                    loginBtn.disabled = true;
                    loginBtn.textContent = 'Logging in...';
                    
                    try {
                       const response = await fetch('/admin/api/login', {
                            method: 'POST',
                            credentials: 'same-origin', // ✅ REQUIRED
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded'
                            },
                            body: new URLSearchParams({
                                'username': username,
                                'password': password
                            })
                        });

                        if (response.ok) {
                            const data = await response.json();
                            
                            // Show success message
                            successDiv.textContent = 'Login successful! Redirecting...';
                            successDiv.style.display = 'block';
                            
                            // Redirect to dashboard after short delay
                            setTimeout(() => {
                                window.location.href = '/admin/dashboard';
                            }, 500);
                        } else {
                            const errorData = await response.json();
                            errorDiv.textContent = errorData.detail || 'Login failed';
                            errorDiv.style.display = 'block';
                            
                            // Re-enable button
                            loginBtn.disabled = false;
                            loginBtn.textContent = 'Login to Admin Portal';
                        }
                    } catch (error) {
                        console.error('Login error:', error);
                        errorDiv.textContent = 'Login failed. Please try again.';
                        errorDiv.style.display = 'block';
                        
                        // Re-enable button
                        loginBtn.disabled = false;
                        loginBtn.textContent = 'Login to Admin Portal';
                    }
                });
            </script>
        </body>
        </html>
        """)

@admin_ui.post("/admin/api/login")
async def admin_api_login(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_async_session)
):
    """
    API endpoint for admin login that returns JSON with token
    """
    try:
        logger.info(f"Login attempt for username: {username}")
        
        # Validate admin credentials
        if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
            logger.warning(f"Invalid credentials for username: {username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check if admin user exists in database
        result = await db.execute(select(User).where(User.username == ADMIN_USERNAME))
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            logger.info("Admin user not found in DB, creating...")
            # Create admin user if it doesn't exist
            from app.routers.auth import get_password_hash
            admin_user = User(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                is_active=True,
                is_verified=True,
                role="admin"
            )
            db.add(admin_user)
            await db.commit()
            await db.refresh(admin_user)
            logger.info(f"Admin user created: {admin_user.username}")

        # Create access token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": admin_user.username},
            expires_delta=access_token_expires
        )

        logger.info(f"Login successful for {admin_user.username}, token created")

        response = JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 1800,
            "user": {
                "id": admin_user.id,
                "username": admin_user.username,
            }
        })

        # Set cookie for server-side requests
        response.set_cookie(
            key="admin_token",
            value=access_token,
            max_age=1800,
            path="/",
            httponly=False,    # still accessible to JS
            samesite="Lax",    # allows normal same-site navigations
            secure=False       # fine for localhost; set True in production (HTTPS)
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin API login error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@admin_ui.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
    """
    Admin dashboard that renders the base_admin.html template
    """
    require_admin(current_user)

    # Get counts with error handling
    try:
        quests_count = (await db.execute(select(func.count()).select_from(Quest))).scalar_one()
    except Exception as e:
        logger.warning(f"Failed to get quests count: {e}")
        quests_count = 0

    try:
        users_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    except Exception as e:
        logger.warning(f"Failed to get users count: {e}")
        users_count = 0

    try:
        feedback_count = (await db.execute(select(func.count()).select_from(Feedback))).scalar_one()
    except Exception as e:
        logger.warning(f"Failed to get feedback count: {e}")
        feedback_count = 0

    try:
        return templates.TemplateResponse("base_admin.html", {
            "request": request,
            "user": current_user,
            "quests": quests_count,
            "users": users_count,
            "feedback": feedback_count,
        })
    except Exception as e:
        logger.error(f"Failed to render base_admin.html template: {e}")
        # Fallback HTML - FIXED
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Dashboard - StudyRPG</title>
            <style>
                body {{
                    background: #36393f;
                    font-family: 'Whitney', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    margin: 0;
                    color: #ffffff;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 2rem;
                }}
                .dashboard-header {{
                    text-align: center;
                    margin-bottom: 2rem;
                    color: #7289da;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 1rem;
                    margin-bottom: 2rem;
                }}
                .stat-card {{
                    background: #2f3136;
                    padding: 1.5rem;
                    border-radius: 8px;
                    text-align: center;
                    border-left: 4px solid #7289da;
                }}
                .stat-number {{
                    font-size: 2rem;
                    font-weight: bold;
                    color: #7289da;
                }}
                .nav-links {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 1rem;
                    justify-content: center;
                }}
                .nav-link {{
                    background: #7289da;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 4px;
                    transition: background 0.3s ease;
                }}
                .nav-link:hover {{
                    background: #677bc4;
                }}
            </style>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
        <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="/static/css/journey.css?v=1">
        <script src="/static/js/journey.js?v=1" defer></script>
        </head>
        <body>
            <div class="container">
                <div class="dashboard-header">
                    <h1>🐉 StudyRPG Admin Dashboard</h1>
                    <p>Welcome, {current_user.username}!</p>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{users_count}</div>
                        <div>Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{quests_count}</div>
                        <div>Total Quests</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{feedback_count}</div>
                        <div>Feedback Items</div>
                    </div>
                </div>

                <div class="nav-links">
                    <a href="/admin/boss-battles" class="nav-link">Boss Battles</a>
                    <a href="/admin" class="nav-link">Admin API</a>
                    <a href="/" class="nav-link">← Back to StudyRPG</a>
                </div>
            </div>
        </body>
        </html>
        """)

@admin_ui.get("/admin/boss-battles", response_class=HTMLResponse)
async def admin_boss_battles_page(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(verify_admin_token)
):
    """
    Boss battles admin list page.
    """
    require_admin(current_user)

    boss_result = await db.execute(select(BossBattle))
    boss_battles = boss_result.scalars().all()

    try:
        return templates.TemplateResponse("admin/boss-battles.html", {
            "request": request,
            "boss_battles": boss_battles,
            "user": current_user
        })
    except Exception:
        rows = "".join(
            f"<tr><td>{b.name}</td><td>{b.health}</td><td>{'Active' if getattr(b, 'is_active', False) else 'Inactive'}</td>"
            f"<td>{getattr(b, 'difficulty', 'Normal')}</td><td>Edit | Activate | Delete</td></tr>"
            for b in boss_battles
        )
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Boss Battles - Admin</title>
            <style>
                body {{
                    background: #36393f;
                    font-family: 'Whitney', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    margin: 0;
                    color: #ffffff;
                    padding: 2rem;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    background: #2f3136;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                th, td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #40444b;
                }}
                th {{
                    background: #7289da;
                    font-weight: bold;
                }}
                .back-link {{
                    display: inline-block;
                    margin-bottom: 1rem;
                    color: #7289da;
                    text-decoration: none;
                }}
                .back-link:hover {{
                    text-decoration: underline;
                }}
            </style>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
        <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="/static/css/journey.css?v=1">
        <script src="/static/js/journey.js?v=1" defer></script>
        </head>
        <body>
            <div class="container">
                <a href="/admin/dashboard" class="back-link">← Back to Dashboard</a>
                <h2>Boss Battles Management ({len(boss_battles)})</h2>
                <table>
                    <thead>
                        <tr><th>Name</th><th>Health</th><th>Status</th><th>Difficulty</th><th>Actions</th></tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </body>
        </html>
        """)

@admin_ui.get("/admin/debug")
async def debug_admin(request: Request):
    """Debug endpoint to check token status"""
    token_cookie = request.cookies.get("admin_token")
    token_local = request.headers.get("Authorization")
    return {
        "has_cookie": bool(token_cookie),
        "has_auth_header": bool(token_local),
        "cookie_token": token_cookie[:20] + "..." if token_cookie else None,
    }