"""Audit models - Record reads, mutations, tool actions, and downstream activations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class AuditLog(Base):
    """Audit log for reads, mutations, tool actions, and downstream activations.

    Partitioned by event_timestamp for performance.
    Captures who did what, when, and with what result.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_timestamp", "event_timestamp"),
        Index("ix_audit_log_actor", "actor_type", "actor_id"),
        Index("ix_audit_log_resource", "resource_type", "resource_id"),
        {"comment": "Audit log - partitioned by event_timestamp"},
    )

    audit_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=UUID,
        server_default=text("gen_random_uuid()"),
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="read, mutation, tool_call, activation",
    )
    event_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    actor_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="user, agent, system, workflow",
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="organization, segment, profile",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    action_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="create, update, delete, query, project",
    )
    action_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="success, failure, pending",
    )
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
        comment="Structured details of the action",
    )
