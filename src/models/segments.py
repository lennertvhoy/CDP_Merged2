"""Segment models - Canonical segment definitions and memberships."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SegmentDefinition(Base):
    """Canonical segment definitions stored in PostgreSQL, not just Tracardi.

    Segment logic lives here as SQL or metadata. Tracardi receives
    only the operational projection for activation.
    """

    __tablename__ = "segment_definitions"
    __table_args__ = ({"comment": "Canonical segment definitions"},)

    segment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=UUID,
        server_default=text("gen_random_uuid()"),
    )
    segment_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    segment_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    definition_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="sql, metadata, rule_graph",
    )
    definition_sql: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    definition_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    owner: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    refresh_schedule: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="true",
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


class SegmentMembership(Base):
    """Segment membership tracking with projection state.

    Tracks who belongs to which segment and whether that membership
    has been projected to Tracardi for activation.
    """

    __tablename__ = "segment_memberships"
    __table_args__ = (
        Index("ix_segment_memberships_uid", "uid", "calculated_at"),
        {"comment": "Segment memberships with projection tracking"},
    )

    segment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("segment_definitions.segment_id", ondelete="CASCADE"),
        primary_key=True,
    )
    uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        primary_key=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )
    membership_reason: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    projected_to_tracardi: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    projected_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
