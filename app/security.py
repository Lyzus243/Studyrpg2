"""
security.py — Centralised security utilities for StudyRPG
Covers:
  • JWT blacklisting on logout
  • Login attempt tracking + account lockout
  • Audit logging
  • IDOR ownership verification helpers
  • SQLi / XSS input sanitisation
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
# ──────────────────────────────────────────────────────────────────────────


# ── JWT Blacklist ──────────────────────────────────────────────────────────

def generate_jti() -> str:
    """Generate a unique JWT ID (jti claim)."""
    return str(uuid.uuid4())


async def blacklist_token(db: AsyncSession, jti: str, expires_at: datetime) -> None:
    """Add a JWT jti to the blacklist so it cannot be reused after logout."""
    entry = models.TokenBlacklist(jti=jti, expires_at=expires_at)
    db.add(entry)
    await db.commit()
    logger.info(f"Token blacklisted: {jti}")


async def is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    """Return True if the token has been blacklisted."""
    result = await db.execute(
        select(models.TokenBlacklist).where(models.TokenBlacklist.jti == jti)
    )
    return result.scalar_one_or_none() is not None


async def purge_expired_blacklist(db: AsyncSession) -> None:
    """Remove expired blacklist entries (call periodically)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(models.TokenBlacklist).where(models.TokenBlacklist.expires_at < now)
    )
    for entry in result.scalars().all():
        await db.delete(entry)
    await db.commit()


# ── Login Attempt Tracking ─────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def record_login_attempt(
    db: AsyncSession,
    username: str,
    success: bool,
    request: Optional[Request] = None,
) -> None:
    """Record a login attempt and enforce lockout on repeated failures."""
    ip = _get_client_ip(request) if request else None
    attempt = models.LoginAttempt(username=username, ip_address=ip, success=success)
    db.add(attempt)

    if not success:
        await _increment_lockout(db, username)
    else:
        await _clear_lockout(db, username)

    await db.commit()


async def _increment_lockout(db: AsyncSession, username: str) -> None:
    result = await db.execute(
        select(models.AccountLockout).where(models.AccountLockout.username == username)
    )
    lockout = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if lockout:
        lockout.failed_attempts += 1
        lockout.last_attempt_at = now
        if lockout.failed_attempts >= MAX_FAILED_ATTEMPTS:
            lockout.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            logger.warning(f"Account locked: {username} ({lockout.failed_attempts} failed attempts)")
    else:
        db.add(models.AccountLockout(
            username=username,
            failed_attempts=1,
            locked_until=now + timedelta(minutes=LOCKOUT_MINUTES * 10),  # far future; only activates at threshold
            last_attempt_at=now,
        ))


async def _clear_lockout(db: AsyncSession, username: str) -> None:
    result = await db.execute(
        select(models.AccountLockout).where(models.AccountLockout.username == username)
    )
    lockout = result.scalar_one_or_none()
    if lockout:
        lockout.failed_attempts = 0
        lockout.locked_until = datetime.now(timezone.utc)


async def check_account_locked(db: AsyncSession, username: str) -> None:
    """Raise 429 if the account is currently locked out."""
    result = await db.execute(
        select(models.AccountLockout).where(models.AccountLockout.username == username)
    )
    lockout = result.scalar_one_or_none()
    if not lockout:
        return

    now = datetime.now(timezone.utc)
    locked_until = lockout.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    if lockout.failed_attempts >= MAX_FAILED_ATTEMPTS and now < locked_until:
        remaining = int((locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {remaining} minute(s).",
        )


# ── Audit Logging ──────────────────────────────────────────────────────────

async def audit(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    resource: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[dict] = None,
) -> None:
    """Write an audit log entry."""
    ip = _get_client_ip(request) if request else None
    ua = request.headers.get("User-Agent") if request else None
    entry = models.AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        ip_address=ip,
        user_agent=ua,
        details=details,
    )
    db.add(entry)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to write audit log")


# ── IDOR Ownership Verification ────────────────────────────────────────────

async def verify_resource_owner(
    db: AsyncSession,
    model_class,
    resource_id: int,
    current_user_id: int,
    owner_field: str = "user_id",
) -> object:
    """
    Fetch a resource and verify the current user owns it.
    Raises 404 if not found, 403 if ownership mismatch.
    """
    result = await db.execute(
        select(model_class).where(model_class.id == resource_id)
    )
    resource = result.scalar_one_or_none()

    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    owner_id = getattr(resource, owner_field, None)
    if owner_id != current_user_id:
        logger.warning(
            f"IDOR attempt: user {current_user_id} tried to access "
            f"{model_class.__tablename__} #{resource_id} owned by {owner_id}"
        )
        raise HTTPException(status_code=403, detail="Access denied")

    return resource


# ── Input Sanitisation ─────────────────────────────────────────────────────

_DANGEROUS_PATTERNS = re.compile(
    r"(--|;|\/\*|\*\/|xp_|UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO|DELETE\s+FROM|UPDATE\s+\w+\s+SET)",
    re.IGNORECASE,
)


def sanitise_input(value: str, max_length: int = 500) -> str:
    """
    Escape HTML entities, strip leading/trailing whitespace,
    enforce max length, and reject obvious SQLi patterns.
    """
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="Invalid input type")
    value = value.strip()[:max_length]
    value = html.escape(value)
    if _DANGEROUS_PATTERNS.search(value):
        logger.warning(f"Suspicious input blocked: {value[:80]}")
        raise HTTPException(status_code=400, detail="Invalid input detected")
    return value


def sanitise_username(username: str) -> str:
    """Only allow alphanumeric + underscore, 3–30 chars."""
    username = username.strip()
    if not re.match(r"^[a-zA-Z0-9_]{3,30}$", username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3–30 characters: letters, numbers, underscores only.",
        )
    return username


def sanitise_email(email: str) -> str:
    """Basic email sanity check."""
    email = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    return email
