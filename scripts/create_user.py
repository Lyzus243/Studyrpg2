#!/usr/bin/env python3
"""
Create StudyRPG accounts straight from the terminal, no signup form,
no email verification step.

Single account:
    python scripts/create_user.py --username maya --email maya@example.com --password Str0ngPass!23

Make it an admin:
    python scripts/create_user.py --username admin2 --email admin2@example.com --password Str0ngPass!23 --admin

Bulk test accounts (creates tester1..tester5, all with the same password):
    python scripts/create_user.py --count 5 --prefix tester --password Str0ngPass!23

Run this from the project root (same folder as requirements.txt), with
your virtualenv active and the same DATABASE_URL your app uses (if you
don't set one, it falls back to the same ./app.db the app itself uses
by default).
"""
import argparse
import asyncio
import logging
import sys
import warnings
from datetime import datetime, timezone

sys.path.insert(0, ".")  # so `app.*` imports work when run from the project root

# app/init_db.py's engine is created with echo=True (which logs every SQL
# statement) and the app's models have some pre-existing, harmless SQLAlchemy
# relationship-overlap warnings. Neither is useful noise for this script.
logging.disable(logging.INFO)
warnings.filterwarnings("ignore")

from app.init_db import init_db
from app.database import async_session_maker
from app.routers.auth import get_password_hash
from app import models
from sqlalchemy import select


async def create_one(session, username: str, email: str, password: str, is_admin: bool) -> bool:
    existing = await session.execute(
        select(models.User).where(
            (models.User.username == username) | (models.User.email == email)
        )
    )
    if existing.scalars().first():
        print(f"  skipped {username} ({email}) - username or email already exists")
        return False

    user = models.User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_verified=True,      # the whole point: skip the email-verification step
        xp=0,
        skill_points=100,
        streak=0,
        level=1,
        currency=100,
        last_active=datetime.now(timezone.utc),
        avatar_url=None,
        role="admin" if is_admin else "user",
    )
    session.add(user)
    await session.commit()
    print(f"  created {username} ({email}){' [admin]' if is_admin else ''} - password: {password}")
    return True


async def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--username", help="Username for a single account")
    p.add_argument("--email", help="Email for a single account")
    p.add_argument("--password", required=True, help="Password to use (required)")
    p.add_argument("--admin", action="store_true", help="Give this account the admin role")
    p.add_argument("--count", type=int, help="Create N test accounts instead of one named account")
    p.add_argument("--prefix", default="tester", help="Username/email prefix for --count mode (default: tester)")
    args = p.parse_args()

    if not args.count and not (args.username and args.email):
        p.error("either pass --username and --email for one account, or --count for bulk test accounts")

    await init_db()  # safe to call every time - only creates tables that don't already exist

    async with async_session_maker() as session:
        created = 0
        if args.count:
            for i in range(1, args.count + 1):
                username = f"{args.prefix}{i}"
                email = f"{args.prefix}{i}@example.com"
                if await create_one(session, username, email, args.password, args.admin):
                    created += 1
        else:
            if await create_one(session, args.username, args.email, args.password, args.admin):
                created += 1

    print(f"\nDone - {created} account(s) created, ready to log in immediately (no email verification needed).")


if __name__ == "__main__":
    asyncio.run(main())
