"""Projection state models - Track what has been projected to downstream systems."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ActivationProjectionState(Base):
    """Track what has been projected into Tracardi and other downstream systems.

    Enables idempotent projection with hash-based change detection.
    """

    __tablename__ = "activation_projection_state"
    __table_args__ = (
        UniqueConstraint(
            "target_system",
            "projected_entity_type",
            "projected_entity_key",
            name="uq_projection_target",
        ),
        {"comment": "Projection state for idempotent sync"},
    )

    projection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=UUID,
        server_default=text("gen_random_uuid()"),
    )
    uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    target_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="tracardi, resend, flexmail",
    )
    projected_entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    projected_entity_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    projection_hash: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Hash of projected content for change detection",
    )
    projection_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="pending, projected, failed",
    )
    projected_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
