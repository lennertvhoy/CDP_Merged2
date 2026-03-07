"""Identity models - UID bridge and merge reconciliation."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SourceIdentityLink(Base):
    """UID bridge across systems without copying raw PII.

    Connects source system IDs to canonical UIDs while keeping
    private contact details in the source systems.
    """

    __tablename__ = "source_identity_links"
    __table_args__ = (
        Index("ix_identity_links_uid", "uid"),
        Index("ix_identity_links_tracardi", "tracardi_profile_id"),
        UniqueConstraint(
            "source_system",
            "source_entity_type",
            "source_record_id",
            name="uq_identity_link_source",
        ),
        {"comment": "UID bridge - PII stays in source systems"},
    )

    identity_link_id: Mapped[UUID] = mapped_column(
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
    subject_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="organization, contact, household, user",
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="teamleader, exact, autotask, etc.",
    )
    source_entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="company, person, ticket_requester, etc.",
    )
    source_record_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    tracardi_profile_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    valid_from: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class IdentityMergeEvent(Base):
    """Track identity merges and splits for reconciliation.

        When upstream systems merge or split records, this table
    captures the event for downstream reconciliation.
    """

    __tablename__ = "identity_merge_events"
    __table_args__ = (
        Index("ix_identity_merge_surviving_uid", "surviving_uid", "event_at"),
        Index("ix_identity_merge_losing_uid", "losing_uid", "event_at"),
        {"comment": "Identity merge/split events for reconciliation"},
    )

    identity_merge_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=UUID,
        server_default=text("gen_random_uuid()"),
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    source_entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    losing_source_record_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    surviving_source_record_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    losing_uid: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    surviving_uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="merge, split, remap",
    )
    event_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    reconciliation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    event_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
