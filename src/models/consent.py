"""Consent and privacy models - Immutable consent ledger and PII resolution audit."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ConsentEvent(Base):
    """Immutable consent and suppression events by UID and purpose.

    Records consent grants, revocations, and suppressions for compliance.
    This is an append-only ledger - never update, only append new events.
    """

    __tablename__ = "consent_events"
    __table_args__ = (
        Index("ix_consent_events_uid", "uid", "purpose", "event_at"),
        {"comment": "Immutable consent ledger - append only"},
    )

    consent_event_id: Mapped[UUID] = mapped_column(
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
    purpose: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="marketing_email, tracking, sms, etc.",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="granted, revoked, suppressed",
    )
    lawful_basis: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="consent, legitimate_interest, contract, etc.",
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    source_record_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    event_at: Mapped[datetime] = mapped_column(
        nullable=False,
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


class PIIResolutionAudit(Base):
    """Audit log for authorized PII resolution at activation time.

    When a campaign or operational send resolves private contact coordinates,
    record the authorized resolution event without copying the raw destination
    into general-purpose analytical logs.
    """

    __tablename__ = "pii_resolution_audit"
    __table_args__ = (
        Index("ix_pii_resolution_audit_uid", "uid", "approved_at"),
        {"comment": "Audit for authorized PII resolution"},
    )

    pii_resolution_audit_id: Mapped[UUID] = mapped_column(
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
    purpose: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="marketing_send, support_callback, invoice_delivery",
    )
    destination_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="email, phone, address",
    )
    resolver_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="teamleader, exact, controlled_api",
    )
    resolved_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    workflow_reference: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    approved_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
