"""Organization model - Public company and account-level data."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Index, String, text
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    """Public company and account-level data.

    Stores public business data, not private contact details.
    Private contact details remain in source systems (Teamleader, Exact, etc.).
    """

    __tablename__ = "organizations"
    __table_args__ = (
        Index("ix_organizations_uid", "uid"),
        Index("ix_organizations_kbo", "kbo_number"),
        Index("ix_organizations_nace", "nace_code"),
        Index("ix_organizations_city", "city"),
        {"comment": "Public company data - PII lives in source systems"},
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=UUID,
        server_default=text("gen_random_uuid()"),
    )
    uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Canonical UID for this organization",
    )
    uid_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="kbo_number, teamleader_company_id, etc.",
    )
    kbo_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )
    vat_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    legal_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    legal_form: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    nace_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        index=True,
    )
    nace_description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    employee_count: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    company_size: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    annual_revenue: Mapped[Decimal | None] = mapped_column(
        NUMERIC(15, 2),
        nullable=True,
    )
    website_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    city: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        index=True,
    )
    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    province: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="BE",
        server_default="BE",
    )
    geo_latitude: Mapped[Decimal | None] = mapped_column(
        NUMERIC(10, 8),
        nullable=True,
    )
    geo_longitude: Mapped[Decimal | None] = mapped_column(
        NUMERIC(11, 8),
        nullable=True,
    )
    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Source system that provided this record",
    )
    source_record_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="ID in the source system",
    )

    def __str__(self) -> str:
        return f"{self.legal_name} ({self.uid})"
