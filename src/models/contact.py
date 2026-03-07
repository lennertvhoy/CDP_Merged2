"""Contact models - Business relationships without PII storage."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ContactRole(Base):
    """Business relationships and decision roles.

    Stores role information without direct private contact coordinates.
    Contact details remain in source systems.
    """

    __tablename__ = "contact_roles"
    __table_args__ = (
        Index("ix_contact_roles_org", "organization_uid"),
        Index("ix_contact_roles_contact", "contact_uid"),
        UniqueConstraint(
            "organization_uid",
            "contact_uid",
            "source_system",
            "source_record_id",
            name="uq_contact_role",
        ),
        {"comment": "Contact roles - PII stays in source systems"},
    )

    contact_role_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=UUID,
        server_default=text("gen_random_uuid()"),
    )
    organization_uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    contact_uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    role_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    department: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    seniority: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    is_decision_maker: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    source_record_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
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
