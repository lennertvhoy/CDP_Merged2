"""Event models - Normalized behavioral and operational facts."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class EventFact(Base):
    """Normalized behavioral and operational facts.

    Stores references and derived metrics, not raw private message bodies.
    Partitioned by occurred_at for performance.
    """

    __tablename__ = "event_facts"
    __table_args__ = (
        Index("ix_event_facts_uid", "uid", "occurred_at"),
        Index("ix_event_facts_org", "organization_uid", "occurred_at"),
        Index("ix_event_facts_type", "event_type", "occurred_at"),
        {"comment": "Behavioral events - partitioned by occurred_at"},
    )

    event_id: Mapped[UUID] = mapped_column(
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
    organization_uid: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    event_channel: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    event_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="website, resend, flexmail, tracardi, support, crm",
    )
    source_event_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )
    event_value: Mapped[Decimal | None] = mapped_column(
        NUMERIC,
        nullable=True,
    )
    attributes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
