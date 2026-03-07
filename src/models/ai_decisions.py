"""AI Decision models - Provenance for AI-enriched tags and recommendations."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class AIDecision(Base):
    """Explicit provenance for AI-enriched tags and recommendations.

    Tracks what the AI decided, when, with what confidence, and why.
    Enables auditability and reproducibility of AI-driven insights.
    """

    __tablename__ = "ai_decisions"
    __table_args__ = (
        Index("ix_ai_decisions_uid", "uid", "decided_at"),
        Index("ix_ai_decisions_name", "decision_name", "decided_at"),
        {"comment": "AI decision provenance for auditability"},
    )

    ai_decision_id: Mapped[UUID] = mapped_column(
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
    decision_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="tag_assignment, nba, classification",
    )
    decision_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="pref_contact_morning, interest_low_maintenance, etc.",
    )
    decision_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        NUMERIC(5, 4),
        nullable=True,
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="intelligence_layer",
        server_default="intelligence_layer",
    )
    source_content_hash: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Hash of source content for reproducibility",
    )
    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    decided_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )
    explanation: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured explanation of the decision",
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
