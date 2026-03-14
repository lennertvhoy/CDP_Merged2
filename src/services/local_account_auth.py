"""PostgreSQL-backed local account auth for the operator shell."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

from src.core.database_url import resolve_database_url
from src.core.logger import get_logger
from src.services.runtime_support_schema import ensure_runtime_support_schema

logger = get_logger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]

PASSWORD_HASH_SCHEME = "scrypt"
PASSWORD_MIN_LENGTH = 12
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_SALT_BYTES = 16


class LocalAccountStoreError(RuntimeError):
    """Base error for local account storage failures."""


class LocalAccountExistsError(LocalAccountStoreError):
    """Raised when a new local account conflicts with an existing identifier."""


class LocalAccountNotFoundError(LocalAccountStoreError):
    """Raised when mutating a local account that does not exist."""


@dataclass(slots=True)
class LocalAccount:
    """Stored local account metadata for shell authentication."""

    account_id: str
    identifier: str
    display_name: str | None
    password_hash: str
    is_admin: bool
    is_active: bool
    account_metadata: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None
    last_login_at: datetime | None


def normalize_local_account_identifier(identifier: str) -> str | None:
    """Normalize the account identifier to the canonical auth/user truth."""
    normalized = identifier.strip().lower()
    return normalized or None


def normalize_local_account_display_name(display_name: str | None) -> str | None:
    if display_name is None:
        return None
    normalized = display_name.strip()
    return normalized or None


def _encode_base64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode_base64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def hash_local_account_password(password: str) -> str:
    """Hash a local-account password using stdlib scrypt."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Local account passwords must be at least {PASSWORD_MIN_LENGTH} characters."
        )

    salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return (
        f"{PASSWORD_HASH_SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}"
        f"${_encode_base64(salt)}${_encode_base64(derived_key)}"
    )


def verify_local_account_password(password: str, encoded_hash: str) -> bool:
    """Verify a plaintext password against a stored scrypt hash."""
    if not password or not encoded_hash:
        return False

    try:
        scheme, raw_n, raw_r, raw_p, raw_salt, raw_hash = encoded_hash.split("$", maxsplit=5)
        if scheme != PASSWORD_HASH_SCHEME:
            return False

        derived_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_decode_base64(raw_salt),
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(_decode_base64(raw_hash)),
        )
    except Exception:
        return False

    return hmac.compare_digest(derived_key, _decode_base64(raw_hash))


def _parse_json_field(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _row_to_local_account(row: dict[str, Any]) -> LocalAccount:
    return LocalAccount(
        account_id=str(row["account_id"]),
        identifier=str(row["identifier"]),
        display_name=row.get("display_name"),
        password_hash=str(row["password_hash"]),
        is_admin=bool(row.get("is_admin")),
        is_active=bool(row.get("is_active")),
        account_metadata=_parse_json_field(row.get("account_metadata")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        last_login_at=row.get("last_login_at"),
    )


class LocalAccountStore:
    """Repo-owned PostgreSQL account store for shell password auth."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or resolve_database_url(REPO_ROOT)
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self.pool is not None:
            return

        await ensure_runtime_support_schema(connection_url=self.database_url)
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def _fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        await self.connect()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
        return dict(row) if row is not None else None

    async def _fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        await self.connect()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]

    async def create_account(
        self,
        *,
        identifier: str,
        password: str,
        display_name: str | None = None,
        is_admin: bool = False,
        is_active: bool = True,
        account_metadata: dict[str, Any] | None = None,
    ) -> LocalAccount:
        normalized_identifier = normalize_local_account_identifier(identifier)
        if normalized_identifier is None:
            raise ValueError("Local account identifier must not be empty.")

        password_hash = hash_local_account_password(password)
        normalized_display_name = normalize_local_account_display_name(display_name)

        try:
            row = await self._fetchrow(
                """
                INSERT INTO app_auth_local_accounts (
                    identifier,
                    display_name,
                    password_hash,
                    is_admin,
                    is_active,
                    account_metadata,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING
                    account_id::text AS account_id,
                    identifier,
                    display_name,
                    password_hash,
                    is_admin,
                    is_active,
                    account_metadata,
                    created_at,
                    updated_at,
                    last_login_at
                """,
                normalized_identifier,
                normalized_display_name,
                password_hash,
                is_admin,
                is_active,
                json.dumps(account_metadata or {}),
            )
        except asyncpg.UniqueViolationError as exc:
            raise LocalAccountExistsError(
                f"Local account {normalized_identifier!r} already exists."
            ) from exc

        if row is None:
            raise LocalAccountStoreError(
                f"Failed to create local account {normalized_identifier!r}."
            )
        return _row_to_local_account(row)

    async def get_account(
        self,
        identifier: str,
        *,
        include_inactive: bool = False,
    ) -> LocalAccount | None:
        normalized_identifier = normalize_local_account_identifier(identifier)
        if normalized_identifier is None:
            return None

        clauses = ["identifier = $1"]
        if not include_inactive:
            clauses.append("is_active = TRUE")

        row = await self._fetchrow(
            f"""
            SELECT
                account_id::text AS account_id,
                identifier,
                display_name,
                password_hash,
                is_admin,
                is_active,
                account_metadata,
                created_at,
                updated_at,
                last_login_at
            FROM app_auth_local_accounts
            WHERE {" AND ".join(clauses)}
            """,
            normalized_identifier,
        )
        return _row_to_local_account(row) if row else None

    async def list_accounts(self, *, include_inactive: bool = True) -> list[LocalAccount]:
        clauses = []
        if not include_inactive:
            clauses.append("is_active = TRUE")

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = await self._fetch(
            f"""
            SELECT
                account_id::text AS account_id,
                identifier,
                display_name,
                password_hash,
                is_admin,
                is_active,
                account_metadata,
                created_at,
                updated_at,
                last_login_at
            FROM app_auth_local_accounts
            {where_clause}
            ORDER BY identifier ASC
            """
        )
        return [_row_to_local_account(row) for row in rows]

    async def update_password(self, identifier: str, password: str) -> LocalAccount:
        normalized_identifier = normalize_local_account_identifier(identifier)
        if normalized_identifier is None:
            raise ValueError("Local account identifier must not be empty.")

        row = await self._fetchrow(
            """
            UPDATE app_auth_local_accounts
            SET password_hash = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE identifier = $1
            RETURNING
                account_id::text AS account_id,
                identifier,
                display_name,
                password_hash,
                is_admin,
                is_active,
                account_metadata,
                created_at,
                updated_at,
                last_login_at
            """,
            normalized_identifier,
            hash_local_account_password(password),
        )
        if row is None:
            raise LocalAccountNotFoundError(
                f"Local account {normalized_identifier!r} does not exist."
            )
        return _row_to_local_account(row)

    async def set_account_active(self, identifier: str, *, is_active: bool) -> LocalAccount:
        normalized_identifier = normalize_local_account_identifier(identifier)
        if normalized_identifier is None:
            raise ValueError("Local account identifier must not be empty.")

        row = await self._fetchrow(
            """
            UPDATE app_auth_local_accounts
            SET is_active = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE identifier = $1
            RETURNING
                account_id::text AS account_id,
                identifier,
                display_name,
                password_hash,
                is_admin,
                is_active,
                account_metadata,
                created_at,
                updated_at,
                last_login_at
            """,
            normalized_identifier,
            is_active,
        )
        if row is None:
            raise LocalAccountNotFoundError(
                f"Local account {normalized_identifier!r} does not exist."
            )
        return _row_to_local_account(row)

    async def set_display_name(self, identifier: str, *, display_name: str | None) -> LocalAccount:
        """Update the display name for a local account."""
        normalized_identifier = normalize_local_account_identifier(identifier)
        if normalized_identifier is None:
            raise ValueError("Local account identifier must not be empty.")

        normalized_display_name = normalize_local_account_display_name(display_name)

        row = await self._fetchrow(
            """
            UPDATE app_auth_local_accounts
            SET display_name = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE identifier = $1
            RETURNING
                account_id::text AS account_id,
                identifier,
                display_name,
                password_hash,
                is_admin,
                is_active,
                account_metadata,
                created_at,
                updated_at,
                last_login_at
            """,
            normalized_identifier,
            normalized_display_name,
        )
        if row is None:
            raise LocalAccountNotFoundError(
                f"Local account {normalized_identifier!r} does not exist."
            )
        return _row_to_local_account(row)

    async def set_admin(self, identifier: str, *, is_admin: bool) -> LocalAccount:
        """Update the admin status for a local account."""
        normalized_identifier = normalize_local_account_identifier(identifier)
        if normalized_identifier is None:
            raise ValueError("Local account identifier must not be empty.")

        row = await self._fetchrow(
            """
            UPDATE app_auth_local_accounts
            SET is_admin = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE identifier = $1
            RETURNING
                account_id::text AS account_id,
                identifier,
                display_name,
                password_hash,
                is_admin,
                is_active,
                account_metadata,
                created_at,
                updated_at,
                last_login_at
            """,
            normalized_identifier,
            is_admin,
        )
        if row is None:
            raise LocalAccountNotFoundError(
                f"Local account {normalized_identifier!r} does not exist."
            )
        return _row_to_local_account(row)

    async def count_admin_accounts(self) -> int:
        """Count the number of active admin accounts."""
        row = await self._fetchrow(
            """
            SELECT COUNT(*) AS count
            FROM app_auth_local_accounts
            WHERE is_admin = TRUE AND is_active = TRUE
            """
        )
        return row["count"] if row else 0

    async def record_successful_login(self, identifier: str) -> None:
        normalized_identifier = normalize_local_account_identifier(identifier)
        if normalized_identifier is None:
            return

        await self._fetchrow(
            """
            UPDATE app_auth_local_accounts
            SET last_login_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE identifier = $1
            RETURNING account_id
            """,
            normalized_identifier,
        )


async def authenticate_local_account(
    identifier: str,
    password: str,
    *,
    store: LocalAccountStore | None = None,
) -> LocalAccount | None:
    """Authenticate a local account against the PostgreSQL-backed store."""
    normalized_identifier = normalize_local_account_identifier(identifier)
    if normalized_identifier is None or not password:
        return None

    account_store = store or LocalAccountStore()
    owns_store = store is None
    try:
        account = await account_store.get_account(normalized_identifier)
        if account is None or not verify_local_account_password(password, account.password_hash):
            return None
        await account_store.record_successful_login(normalized_identifier)
        return account
    finally:
        if owns_store:
            await account_store.close()


__all__ = [
    "LocalAccount",
    "LocalAccountExistsError",
    "LocalAccountNotFoundError",
    "LocalAccountStore",
    "LocalAccountStoreError",
    "PASSWORD_MIN_LENGTH",
    "authenticate_local_account",
    "hash_local_account_password",
    "normalize_local_account_display_name",
    "normalize_local_account_identifier",
    "verify_local_account_password",
]
