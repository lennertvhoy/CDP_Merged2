#!/usr/bin/env python3
"""CLI tool to create a local account for the operator shell."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.services.local_account_auth import (
    LocalAccountStore,
    LocalAccountExistsError,
    PASSWORD_MIN_LENGTH,
)


def main():
    parser = argparse.ArgumentParser(description="Create a local account for the operator shell")
    parser.add_argument("identifier", help="Account identifier (email or username)")
    parser.add_argument("--password", "-p", required=True, help=f"Password (min {PASSWORD_MIN_LENGTH} chars)")
    parser.add_argument("--display-name", "-d", help="Display name (optional)")
    parser.add_argument("--admin", "-a", action="store_true", help="Make account an admin")
    parser.add_argument("--inactive", action="store_true", help="Create as inactive account")
    
    args = parser.parse_args()
    
    if len(args.password) < PASSWORD_MIN_LENGTH:
        print(f"Error: Password must be at least {PASSWORD_MIN_LENGTH} characters", file=sys.stderr)
        sys.exit(1)
    
    async def create():
        store = LocalAccountStore()
        try:
            account = await store.create_account(
                identifier=args.identifier,
                password=args.password,
                display_name=args.display_name,
                is_admin=args.admin,
                is_active=not args.inactive,
            )
            print(f"Account created successfully:")
            print(f"  ID: {account.account_id}")
            print(f"  Identifier: {account.identifier}")
            print(f"  Display Name: {account.display_name or '(none)'}")
            print(f"  Admin: {account.is_admin}")
            print(f"  Active: {account.is_active}")
        except LocalAccountExistsError:
            print(f"Error: Account '{args.identifier}' already exists", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            await store.close()
    
    asyncio.run(create())


if __name__ == "__main__":
    main()
