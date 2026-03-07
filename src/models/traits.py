"""Trait models - Durable analytical traits with provenance."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ProfileTrait(Base):
    """Durable analytical traits used by chatbot and canonical segments.

    Stores traits with provenance - where they came from and how reliable they are.
    """

    __tablename__ = "profile_traits"
    __table_args__ = (
        Index("ix_profile_traits_uid_name", "uid", "trait_name", "effective_at"),
        Index("ix_profile_traits_name", "trait_name", "effective_at"),
        {"comment": "Analytical traits with provenance"},
    )

    trait_id: Mapped[UUID] = mapped_column(
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
    trait_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    trait_value_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    trait_value_number: Mapped[Decimal | None] = mapped_column(
        NUMERIC,
        nullable=True,
    )
    trait_value_boolean: Mapped[bool | None] = mapped_column(
        nullable=True,
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        NUMERIC(5, 4),
        nullable=True,
        comment="Confidence score 0.0000 to 1.0000",
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="intelligence_layer, tracardi_projection, batch_model",
    )
    source_reference: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    effective_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    def get_value(self) -> str | Decimal | bool | None:
        """Get the trait value regardless of type."""
        if self.trait_value_text is not None:
            return self.trait_value_text
        if self.trait_value_number is not None:
            return self.trait_value_number
        return self.trait_value_boolean
