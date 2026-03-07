"""Base model classes for CDP 360 Data Model."""

from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all models."""

    metadata = metadata

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}

    def __repr__(self) -> str:
        """String representation."""
        pk_columns = self.__table__.primary_key.columns  # type: ignore[attr-defined]
        pk_values = [getattr(self, col.name) for col in pk_columns]
        pk_str = ", ".join(str(v) for v in pk_values)
        return f"<{self.__class__.__name__}({pk_str})>"


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class UIDMixin:
    """Mixin for UID-based entities."""

    uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Canonical UID across systems",
    )
