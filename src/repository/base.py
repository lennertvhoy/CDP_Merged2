"""Base repository class for 360 Data Model.

Provides common CRUD operations and query patterns.
"""

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations.

    Usage:
        repo = BaseRepository[Organization](Organization, session)
        org = repo.get_by_id(org_id)
    """

    def __init__(self, model: type[ModelType], session: Session) -> None:
        """Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Database session
        """
        self.model = model
        self.session = session

    def get_by_id(self, id_: UUID) -> ModelType | None:
        """Get entity by primary key.

        Args:
            id_: Primary key UUID

        Returns:
            Entity or None if not found
        """
        return self.session.get(self.model, id_)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[ModelType]:
        """Get all entities with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of entities
        """
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars().all())

    def create(self, entity: ModelType) -> ModelType:
        """Create new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with generated fields
        """
        self.session.add(entity)
        self.session.flush()  # Flush to get generated fields
        return entity

    def update(self, entity: ModelType) -> ModelType:
        """Update existing entity.

        Args:
            entity: Entity to update

        Returns:
            Updated entity
        """
        self.session.merge(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelType) -> None:
        """Delete entity.

        Args:
            entity: Entity to delete
        """
        self.session.delete(entity)

    def count(self) -> int:
        """Get total count of entities.

        Returns:
            Total count
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        return self.session.execute(stmt).scalar() or 0

    def exists(self, id_: UUID) -> bool:
        """Check if entity exists.

        Args:
            id_: Primary key UUID

        Returns:
            True if exists, False otherwise
        """
        # Get the primary key column from the model's table
        pk_columns = self.model.__table__.primary_key.columns  # type: ignore[attr-defined]
        if not pk_columns:
            return False
        pk_column = list(pk_columns)[0]

        stmt = select(self.model).where(pk_column == id_).limit(1)
        result = self.session.execute(stmt).scalar_one_or_none()
        return result is not None
