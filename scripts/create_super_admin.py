"""Create a SUPER_ADMIN user.

Runnable from the backend container:

    python -m scripts.create_super_admin --username admin@example.com --password 'secret'

The username is stored as the user's email, which is the login identifier
for both the API and the SQLAdmin panel.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.database import AsyncSessionLocal, engine
from app.core.exceptions import ConflictError
from app.models.user import User, UserRole
from app.services.user_management_service import UserManagementService

MIN_PASSWORD_LENGTH = 8


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a SUPER_ADMIN user.")
    parser.add_argument(
        "--username",
        "-u",
        required=True,
        help="Login username (stored as the user email)",
    )
    parser.add_argument(
        "--password",
        "-p",
        required=True,
        help=f"Password (at least {MIN_PASSWORD_LENGTH} characters)",
    )
    return parser.parse_args(argv)


def validate_credentials(username: str, password: str) -> str:
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    return username


async def create_super_admin(username: str, password: str) -> User:
    username = validate_credentials(username, password)

    async with AsyncSessionLocal() as session:
        service = UserManagementService(session)
        user = await service.create(
            email=username,
            password=password,
            role=UserRole.SUPER_ADMIN,
        )
        await session.commit()
        return user


async def _run(username: str, password: str) -> int:
    try:
        user = await create_super_admin(username, password)
    except (ConflictError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    print(f"Created SUPER_ADMIN {user.email} ({user.id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(_run(args.username, args.password))


if __name__ == "__main__":
    raise SystemExit(main())
