"""Promote an existing user to SUPER_ADMIN.

Runnable from the backend container:

    python -m scripts.promote_super_admin --username admin@example.com

The username is the user's email, which is the login identifier for both
the API and the SQLAdmin panel.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.database import AsyncSessionLocal, engine
from app.core.exceptions import NotFoundException
from app.models.user import User, UserRole
from app.services.user_management_service import UserManagementService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote an existing user to SUPER_ADMIN.")
    parser.add_argument(
        "--username",
        "-u",
        required=True,
        help="Login username (the user email)",
    )
    return parser.parse_args(argv)


def validate_username(username: str) -> str:
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty")
    return username


async def promote_super_admin(username: str) -> tuple[User, str]:
    username = validate_username(username)

    async with AsyncSessionLocal() as session:
        service = UserManagementService(session)
        user = await service.get_by_email(username)
        if not user:
            raise NotFoundException(f"User not found: {username}")

        previous_role = user.role
        if previous_role == UserRole.SUPER_ADMIN.value:
            return user, previous_role

        user = await service.update(user.id, role=UserRole.SUPER_ADMIN)
        await session.commit()
        return user, previous_role


async def _run(username: str) -> int:
    try:
        user, previous_role = await promote_super_admin(username)
    except (NotFoundException, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    if previous_role == UserRole.SUPER_ADMIN.value:
        print(f"{user.email} is already SUPER_ADMIN ({user.id})")
    else:
        print(f"Promoted {user.email} from {previous_role} to SUPER_ADMIN ({user.id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(_run(args.username))


if __name__ == "__main__":
    raise SystemExit(main())
