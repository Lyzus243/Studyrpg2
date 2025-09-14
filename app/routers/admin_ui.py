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

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Admin credentials from .env (same as admin.py)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@studyrpg.com")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGO", "HS256")
# Setup templates directory
BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "static" / "templates" / "admin"
templates = Jinja2Templates(directory=TEMPLATE_DIR)

admin_ui = APIRouter()


# Update the verify_admin_token function to check both Authorization header and cookies
async def verify_admin_token(request: Request, db: AsyncSession = Depends(get_async_session)):
    """
    Verify admin token from Authorization header or cookie and return DB User model.
    """
    auth_header = request.headers.get("Authorization")
    token = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.cookies.get("admin_token")

    if not token:
        logger.info("No admin token found in header or cookies")
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        # Decode the token directly instead of calling the verify endpoint
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        if not username:
            logger.warning("No username found in token payload")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # Fetch the real user model from DB
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("No DB user found for username from token: %s", username)
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # Verify admin using current_user.username (explicit)
        if user.username != ADMIN_USERNAME:
            logger.warning("User %s is not configured admin (expected: %s)", user.username, ADMIN_USERNAME)
            raise HTTPException(status_code=403, detail="Admin access only")

        logger.info("Admin authentication successful for user: %s", user.username)
        return user

    except JWTError as e:
        logger.warning("JWTError when verifying admin token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except Exception as e:
        logger.error("Unexpected error verifying admin token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

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
        logger.warning(f"Failed to get feedback count (table may not exist): {e}")
        feedback_count = 0

    try:
        # Render the template with all required context data
        return templates.TemplateResponse("base_admin.html", {
            "request": request,
            "user": current_user,
            "quests": quests_count,
            "users": users_count,
            "feedback": feedback_count,
        })
    except Exception as e:
        logger.error(f"Failed to render base_admin.html template: {e}")
        # Fallback HTML if template not found - FIXED JavaScript
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Dashboard - StudyRPG</title>
            <style>
                body {{
                    background: #36393f; /* Discord dark gray */
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
                    color: #7289da; /* Discord blurple */
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 1rem;
                    margin-bottom: 2rem;
                }}
                .stat-card {{
                    background: #2f3136; /* Discord darker gray */
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
            <script>
                // Function to add Authorization header to all fetch requests - FIXED
                const originalFetch = window.fetch;
                window.fetch = function(...args) {{
                    const [url, options = {{}}] = args;
                    const token = localStorage.getItem('admin_token');
                    
                    if (token) {{
                        options.headers = {{
                            ...options.headers,
                            'Authorization': 'Bearer ' + token
                        }};
                    }}
                    
                    return originalFetch(url, options);
                }};
            </script>
        </body>
        </html>
        """)


def require_admin(user: User):
    """
    Check if user is admin based on .env credentials (same logic as admin.py)
    """
    if not user:
        logger.warning("No user provided to admin check")
        raise HTTPException(status_code=403, detail="Admin access only")

    # Check if username matches admin username from .env
    if user.username != ADMIN_USERNAME:
        logger.warning(f"Admin access denied for user: {user.username} (expected: {ADMIN_USERNAME})")
        raise HTTPException(status_code=403, detail="Admin access only")

    logger.info(f"✅ Admin access granted for user: {user.username}")
    return True


@admin_ui.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """
    Admin login page (served via Jinja template).
    The template should contain JS that calls /auth/token and stores Bearer token.
    """
    try:
        return templates.TemplateResponse("admin/login.html", {"request": request})
    except Exception:
        # Fallback inline HTML if template not found - FIXED JavaScript
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Login - StudyRPG</title>
            <style>
                body {
                    background: #36393f; /* Discord dark gray */
                    font-family: 'Whitney', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    color: #ffffff;
                }
                .login-container {
                    background: #2f3136; /* Discord darker gray */
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
                }
                button {
                    width: 100%;
                    background: #7289da; /* Discord blurple */
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
                h1 { color: #7289da; text-align: center; }
                .error { color: #ed4245; text-align: center; margin-bottom: 1rem; }
                a { color: #7289da; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="login-container">
                <h1>🐉 Admin Portal Login</h1>
                <div id="error-message" class="error" style="display: none;"></div>
                <form id="login-form">
                    <div class="form-group">
                        <input type="text" id="username" placeholder="Username" required>
                    </div>
                    <div class="form-group">
                        <input type="password" id="password" placeholder="Password" required>
                    </div>
                    <button type="submit">Login to Admin Portal</button>
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
                    try {
                        const response = await fetch('/admin/api/login', {
                            method: 'POST',
                            headers: { 
                                'Content-Type': 'application/x-www-form-urlencoded' 
                            },
                            body: 'username=' + encodeURIComponent(username) + '&password=' + encodeURIComponent(password)
                        });
                        if (response.ok) {
                            const data = await response.json();
                            localStorage.setItem('admin_token', data.access_token);
                            // Also set a cookie for server-side requests - FIXED
                            document.cookie = 'admin_token=' + data.access_token + '; path=/; max-age=1800';
                            window.location.href = '/admin/dashboard';
                        } else {
                            const errorData = await response.json();
                            errorDiv.textContent = errorData.detail || 'Login failed';
                            errorDiv.style.display = 'block';
                        }
                    } catch (error) {
                        errorDiv.textContent = 'Login failed. Please try again.';
                        errorDiv.style.display = 'block';
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
        # Validate admin credentials
        if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check if admin user exists in database
        result = await db.execute(select(User).where(User.username == ADMIN_USERNAME))
        admin_user = result.scalar_one_or_none()

        if not admin_user:
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

        # Create access token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": admin_user.username},
            expires_delta=access_token_expires
        )

        response = JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 1800,  # 30 minutes in seconds
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
            httponly=True,
            samesite="lax"
        )

        return response

    except Exception as e:
        logger.error(f"Admin API login error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")


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
        # FIXED JavaScript in fallback HTML
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
            <script>
                // Function to add Authorization header to all fetch requests - FIXED
                const originalFetch = window.fetch;
                window.fetch = function(...args) {{
                    const [url, options = {{}}] = args;
                    const token = localStorage.getItem('admin_token');
                    
                    if (token) {{
                        options.headers = {{
                            ...options.headers,
                            'Authorization': 'Bearer ' + token
                        }};
                    }}
                    
                    return originalFetch(url, options);
                }};
            </script>
        </body>
        </html>
        """)


@admin_ui.get("/admin/debug")
async def admin_debug(current_user: User = Depends(verify_admin_token)):
    """
    Debug endpoint to confirm who is logged in and admin validation.
    """
    is_admin = current_user.username == ADMIN_USERNAME

    return {
        "user": current_user.username,
        "authenticated": True,
        "is_admin": is_admin,
        "admin_username_expected": ADMIN_USERNAME,
        "admin_configured": bool(ADMIN_USERNAME and ADMIN_PASSWORD),
        "role": getattr(current_user, "role", None),
        "is_verified": getattr(current_user, "is_verified", None),
        "is_banned": getattr(current_user, "is_banned", None),
    }


@admin_ui.post("/admin/login", response_class=HTMLResponse)
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """
    Handle admin login form submission and return JavaScript to store token
    """
    try:
        # Validate admin credentials
        if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
            return HTMLResponse("""
            <script>
                alert('Invalid admin credentials');
                window.location.href = '/admin/login';
            </script>
            """)

        # Create token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )

        # Return HTML with JavaScript that stores token and redirects - FIXED
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login Success</title>
        </head>
        <body>
            <script>
                // Store token in localStorage
                localStorage.setItem('admin_token', '{access_token}');
                // Also set a cookie for server-side requests - FIXED
                document.cookie = 'admin_token={access_token}; path=/; max-age=1800';

                // Redirect to dashboard
                window.location.href = '/admin/dashboard';
            </script>
        </body>
        </html>
        """)

    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        return HTMLResponse("""
        <script>
            alert('Login failed. Please try again.');
            window.location.href = '/admin/login';
        </script>
        """)