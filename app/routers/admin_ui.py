from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_async_session
from app.models import User, BossBattle
from fastapi.templating import Jinja2Templates
from pathlib import Path
import logging
from app.routers.auth import get_current_user_optional, get_current_user

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Setup templates directory
BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "static" / "templates" / "admin"
templates = Jinja2Templates(directory=TEMPLATE_DIR)

admin_ui = APIRouter()

def require_admin(user: User | None):
    """
    Role-based admin check (no hard-coded username).
    """
    if not user or getattr(user, "role", "user") not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Admin access only")

@admin_ui.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """
    Admin login page (served via Jinja template).
    The template should contain JS that calls /auth/token and stores Bearer token.
    """
    try:
        return templates.TemplateResponse("admin/login.html", {"request": request})
    except Exception:
        # Fallback inline HTML if template not found
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Login - StudyRPG</title>
            <style>
                body {
                    background: linear-gradient(135deg, #1a1a2e 0%, #1e3c72 25%, #e52d27 60%, #ffb347 85%, #6df0ff 100%);
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    color: white;
                }
                .login-container {
                    background: rgba(30, 60, 114, 0.9);
                    padding: 2rem;
                    border-radius: 16px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
                    border: 2px solid rgba(255, 179, 71, 0.3);
                    min-width: 400px;
                }
                .form-group { margin-bottom: 1rem; }
                input {
                    width: 100%;
                    padding: 12px;
                    border: 1px solid rgba(255, 179, 71, 0.4);
                    border-radius: 8px;
                    background: rgba(26, 26, 46, 0.6);
                    color: white;
                    font-size: 1rem;
                }
                button {
                    width: 100%;
                    background: linear-gradient(to right, #e52d27, #ff6b35);
                    color: white;
                    padding: 12px;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }
                button:hover {
                    background: linear-gradient(to right, #ff4c4c, #ff8c5a);
                    transform: translateY(-2px);
                }
                h1 { color: #ffb347; text-align: center; }
                .error { color: #ff4c4c; text-align: center; margin-bottom: 1rem; }
                a { color: #6df0ff; }
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
                        const response = await fetch('/auth/token', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                            body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
                        });
                        if (response.ok) {
                            const data = await response.json();
                            localStorage.setItem('admin_token', data.access_token);
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

from sqlalchemy import func
from app.models import Quest, User
from app.models_feedback import Feedback  # if Feedback is in a separate file

@admin_ui.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/admin/login")
    require_admin(current_user)

    # Get counts
    quests_count = (await db.execute(select(func.count()).select_from(Quest))).scalar_one()
    users_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    feedback_count = (await db.execute(select(func.count()).select_from(Feedback))).scalar_one()

    return templates.TemplateResponse("base_admin.html", {
        "request": request,
        "user": current_user,
        "quests": quests_count,
        "users": users_count,
        "feedback": feedback_count,
    })



@admin_ui.get("/admin/boss-battles", response_class=HTMLResponse)
async def admin_boss_battles_page(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_optional)
):
    """
    Boss battles admin list page.
    """
    if not current_user:
        return RedirectResponse(url="/admin/login")
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
        <div class="admin-section">
            <h3>Boss Battles ({len(boss_battles)})</h3>
            <table>
                <thead>
                    <tr><th>Name</th><th>Health</th><th>Status</th><th>Difficulty</th><th>Actions</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """)

@admin_ui.get("/admin/debug")
async def admin_debug(current_user: User = Depends(get_current_user_optional)):
    """
    Simple debug endpoint to confirm who is logged in and their role.
    """
    return {
        "user": getattr(current_user, "username", None),
        "role": getattr(current_user, "role", None),
        "is_verified": getattr(current_user, "is_verified", None),
        "is_banned": getattr(current_user, "is_banned", None),
    }
