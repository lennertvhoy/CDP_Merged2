"""Idempotent local/runtime support schema bootstrap for PostgreSQL-first tooling."""

from __future__ import annotations

from typing import Any

from src.core.logger import get_logger
from src.services.postgresql_client import PostgreSQLClient

logger = get_logger(__name__)

SUPPORT_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS activation_projection_state (
    projection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    target_system VARCHAR(50) NOT NULL,
    projected_entity_type VARCHAR(50) NOT NULL,
    projected_entity_key VARCHAR(100) NOT NULL,
    projection_hash VARCHAR(128),
    projection_status VARCHAR(50) NOT NULL,
    last_error TEXT,
    projected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (target_system, projected_entity_type, projected_entity_key)
);

CREATE INDEX IF NOT EXISTS idx_projection_state_uid
    ON activation_projection_state(uid, target_system, projected_at DESC);
CREATE INDEX IF NOT EXISTS idx_projection_state_status
    ON activation_projection_state(projection_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_projection_state_target
    ON activation_projection_state(target_system, projection_status);

CREATE TABLE IF NOT EXISTS segment_definitions (
    segment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    segment_key VARCHAR(100) NOT NULL UNIQUE,
    segment_name VARCHAR(200) NOT NULL,
    description TEXT,
    definition_type VARCHAR(50) NOT NULL,
    definition_sql TEXT,
    definition_json JSONB,
    owner VARCHAR(100),
    refresh_schedule VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_segment_definitions_active
    ON segment_definitions(is_active, segment_key);

CREATE TABLE IF NOT EXISTS segment_memberships (
    segment_id UUID NOT NULL REFERENCES segment_definitions(segment_id) ON DELETE CASCADE,
    uid VARCHAR(100) NOT NULL,
    calculated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    membership_reason JSONB DEFAULT '{}'::jsonb,
    projected_to_tracardi BOOLEAN NOT NULL DEFAULT FALSE,
    projected_at TIMESTAMP,
    PRIMARY KEY (segment_id, uid)
);

CREATE INDEX IF NOT EXISTS idx_segment_memberships_uid
    ON segment_memberships(uid, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_segment_memberships_projected
    ON segment_memberships(projected_to_tracardi, projected_at)
    WHERE projected_to_tracardi = FALSE;

CREATE TABLE IF NOT EXISTS source_identity_links (
    identity_link_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uid VARCHAR(100) NOT NULL,
    subject_type VARCHAR(50) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    tracardi_profile_id VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, source_entity_type, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_identity_links_uid
    ON source_identity_links(uid, is_primary DESC);
CREATE INDEX IF NOT EXISTS idx_identity_links_tracardi
    ON source_identity_links(tracardi_profile_id)
    WHERE tracardi_profile_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_identity_links_source
    ON source_identity_links(source_system, source_entity_type, source_record_id);

CREATE TABLE IF NOT EXISTS app_chat_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_chat_users_identifier
    ON app_chat_users(identifier);

CREATE TABLE IF NOT EXISTS app_chat_threads (
    thread_id VARCHAR(255) PRIMARY KEY,
    user_id UUID REFERENCES app_chat_users(user_id) ON DELETE SET NULL,
    name VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_chat_threads_user_updated
    ON app_chat_threads(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_chat_threads_updated
    ON app_chat_threads(updated_at DESC);

CREATE TABLE IF NOT EXISTS app_chat_steps (
    step_id VARCHAR(255) PRIMARY KEY,
    thread_id VARCHAR(255) REFERENCES app_chat_threads(thread_id) ON DELETE CASCADE,
    parent_step_id VARCHAR(255) REFERENCES app_chat_steps(step_id) ON DELETE CASCADE,
    step_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_chat_steps_thread_created
    ON app_chat_steps(thread_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_app_chat_steps_parent
    ON app_chat_steps(parent_step_id);

CREATE TABLE IF NOT EXISTS app_chat_elements (
    element_id VARCHAR(255) PRIMARY KEY,
    thread_id VARCHAR(255) REFERENCES app_chat_threads(thread_id) ON DELETE CASCADE,
    step_id VARCHAR(255) REFERENCES app_chat_steps(step_id) ON DELETE CASCADE,
    element_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_chat_elements_thread_created
    ON app_chat_elements(thread_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_app_chat_elements_step
    ON app_chat_elements(step_id);

CREATE TABLE IF NOT EXISTS app_chat_feedback (
    feedback_id VARCHAR(255) PRIMARY KEY,
    thread_id VARCHAR(255) REFERENCES app_chat_threads(thread_id) ON DELETE CASCADE,
    step_id VARCHAR(255) REFERENCES app_chat_steps(step_id) ON DELETE CASCADE,
    value SMALLINT NOT NULL CHECK (value IN (0, 1)),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_chat_feedback_thread
    ON app_chat_feedback(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_chat_feedback_step
    ON app_chat_feedback(step_id);
"""

_BOOTSTRAPPED_CONNECTIONS: set[str] = set()


async def ensure_runtime_support_schema(
    client: Any | None = None,
    connection_url: str | None = None,
) -> bool:
    """Create the PostgreSQL-first support tables required by local/runtime tooling."""

    effective_url = connection_url or getattr(client, "connection_url", None) or "<default>"
    if effective_url in _BOOTSTRAPPED_CONNECTIONS:
        return True

    owned_client: PostgreSQLClient | None = None
    db_client = client

    if db_client is None:
        owned_client = PostgreSQLClient(connection_url=connection_url)
        db_client = owned_client

    try:
        if hasattr(db_client, "ensure_connected"):
            await db_client.ensure_connected()
        else:
            await db_client.connect()

        pool = getattr(db_client, "pool", None)
        if pool is None:
            logger.warning("runtime_support_schema_no_pool")
            return False

        async with pool.acquire() as conn:
            await conn.execute(SUPPORT_SCHEMA_SQL)

        _BOOTSTRAPPED_CONNECTIONS.add(effective_url)
        logger.info("runtime_support_schema_ensured", connection_key=effective_url)
        return True
    except Exception as exc:
        logger.warning(
            "runtime_support_schema_failed",
            connection_key=effective_url,
            error=str(exc),
        )
        return False
    finally:
        if owned_client is not None:
            await owned_client.disconnect()


__all__ = ["ensure_runtime_support_schema"]
