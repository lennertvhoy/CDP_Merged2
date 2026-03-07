"""Organization repository for 360 Data Model.

Provides organization-specific queries and operations.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.organization import Organization
from src.repository.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization entity.

    Provides organization-specific queries beyond basic CRUD.
    """

    def __init__(self, session: Session) -> None:
        """Initialize repository.

        Args:
            session: Database session
        """
        super().__init__(Organization, session)

    def get_by_uid(self, uid: str) -> Organization | None:
        """Get organization by canonical UID.

        Args:
            uid: Canonical UID

        Returns:
            Organization or None if not found
        """
        stmt = select(Organization).where(Organization.uid == uid)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_kbo(self, kbo_number: str) -> Organization | None:
        """Get organization by KBO number.

        Args:
            kbo_number: Belgian KBO number

        Returns:
            Organization or None if not found
        """
        stmt = select(Organization).where(Organization.kbo_number == kbo_number)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_source(self, source_system: str, source_record_id: str) -> Organization | None:
        """Get organization by source system reference.

        Args:
            source_system: Source system name (e.g., 'teamleader', 'exact')
            source_record_id: ID in the source system

        Returns:
            Organization or None if not found
        """
        stmt = select(Organization).where(
            Organization.source_system == source_system,
            Organization.source_record_id == source_record_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def search_by_name(self, name_pattern: str, limit: int = 20) -> list[Organization]:
        """Search organizations by legal name pattern.

        Args:
            name_pattern: Name pattern to search (SQL LIKE pattern)
            limit: Maximum results

        Returns:
            List of matching organizations
        """
        stmt = (
            select(Organization)
            .where(Organization.legal_name.ilike(f"%{name_pattern}%"))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_by_city(self, city: str, limit: int = 100) -> list[Organization]:
        """Get organizations in a specific city.

        Args:
            city: City name
            limit: Maximum results

        Returns:
            List of organizations in the city
        """
        stmt = select(Organization).where(Organization.city.ilike(city)).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_by_nace(self, nace_code: str, limit: int = 100) -> list[Organization]:
        """Get organizations by NACE code.

        Args:
            nace_code: NACE industry code
            limit: Maximum results

        Returns:
            List of organizations with the NACE code
        """
        stmt = select(Organization).where(Organization.nace_code == nace_code).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_by_nace_prefix(self, nace_prefix: str, limit: int = 100) -> list[Organization]:
        """Get organizations by NACE code prefix.

        Args:
            nace_prefix: NACE code prefix (e.g., '62' for IT services)
            limit: Maximum results

        Returns:
            List of organizations with matching NACE prefix
        """
        stmt = (
            select(Organization).where(Organization.nace_code.startswith(nace_prefix)).limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_with_website(self, limit: int = 100) -> list[Organization]:
        """Get organizations that have a website.

        Args:
            limit: Maximum results

        Returns:
            List of organizations with websites
        """
        stmt = select(Organization).where(Organization.website_url.isnot(None)).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_by_company_size(self, size_category: str, limit: int = 100) -> list[Organization]:
        """Get organizations by size category.

        Args:
            size_category: Size category (e.g., 'small', 'medium', 'large')
            limit: Maximum results

        Returns:
            List of organizations in the size category
        """
        stmt = select(Organization).where(Organization.company_size == size_category).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_stats_by_city(self) -> list[dict[str, Any]]:
        """Get organization count statistics by city.

        Returns:
            List of dicts with city and count
        """
        from sqlalchemy import func

        stmt = (
            select(Organization.city, func.count().label("count"))
            .where(Organization.city.isnot(None))
            .group_by(Organization.city)
            .order_by(func.count().desc())
        )
        results = self.session.execute(stmt).all()
        return [{"city": row[0], "count": row[1]} for row in results]

    def get_stats_by_nace(self) -> list[dict[str, Any]]:
        """Get organization count statistics by NACE code.

        Returns:
            List of dicts with nace_code, nace_description, and count
        """
        from sqlalchemy import func

        stmt = (
            select(
                Organization.nace_code,
                Organization.nace_description,
                func.count().label("count"),
            )
            .where(Organization.nace_code.isnot(None))
            .group_by(Organization.nace_code, Organization.nace_description)
            .order_by(func.count().desc())
        )
        results = self.session.execute(stmt).all()
        return [
            {"nace_code": row[0], "nace_description": row[1], "count": row[2]} for row in results
        ]
