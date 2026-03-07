#!/usr/bin/env python3
"""Verify Teamleader OAuth refresh flow and a minimal live CRM read."""

from __future__ import annotations

import sys

from src.services.teamleader import TEAMLEADER_ENV_PATH, TeamleaderClient, load_teamleader_env_file


def summarize(record: dict | None, *keys: str) -> str:
    """Return the first available field value from a record."""
    if not record:
        return "null"
    for key in keys:
        value = record.get(key)
        if value:
            return str(value)
    return "null"


def main() -> int:
    """Run the Teamleader access verification."""
    load_teamleader_env_file(TEAMLEADER_ENV_PATH)

    if not TEAMLEADER_ENV_PATH.exists():
        print("❌ .env.teamleader not found")
        return 1

    print("=" * 60)
    print("Teamleader Access Verification")
    print("=" * 60)

    try:
        client = TeamleaderClient.from_env()
        access_token = client.refresh_access_token()
        print("✅ Refresh-token exchange succeeded")
        print(f"   Access token length: {len(access_token)}")
    except Exception as exc:
        print(f"❌ Refresh-token exchange failed: {exc}")
        return 1

    endpoints = [
        ("companies.list", ("name",)),
        ("contacts.list", ("first_name", "name")),
        ("deals.list", ("title", "name")),
        ("events.list", ("title",)),
    ]

    success = True
    for endpoint, label_keys in endpoints:
        try:
            first = client.first_record(endpoint)
            count = 1 if first else 0
            print(f"✅ {endpoint} returned {count} record(s) on the first page")
            print(f"   First id: {summarize(first, 'id')}")
            print(f"   First label: {summarize(first, *label_keys)}")
        except Exception as exc:
            success = False
            print(f"❌ {endpoint} failed: {exc}")

    print("=" * 60)
    print("Verification Complete")
    print("=" * 60)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
