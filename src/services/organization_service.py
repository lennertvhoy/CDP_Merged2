"""Organization Service - Bridge between 360 Data Model and existing search.

This service provides a high-level interface for organization operations,
integrating the SQLAlchemy-based 360 models with the existing asyncpg-based
search infrastructure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.logger import get_logger
from src.models.database import db_session_scope
from src.repository.organization import OrganizationRepository

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class OrganizationService:
    """Service layer for organization operations.

    Provides business logic and coordinates between repositories
    and external services.
    """

    def __init__(self) -> None:
        """Initialize service."""
        self._logger = logger

    async def get_by_uid(self, uid: str) -> dict[str, Any] | None:
        """Get organization by UID.

        Args:
            uid: Canonical UID

        Returns:
            Organization data as dict or None
        """
        try:
            with db_session_scope() as session:
                repo = OrganizationRepository(session)
                org = repo.get_by_uid(uid)
                return org.to_dict() if org else None
        except Exception as e:
            self._logger.error(f"Error getting organization by UID: {e}")
            return None

    async def get_by_kbo(self, kbo_number: str) -> dict[str, Any] | None:
        """Get organization by KBO number.

        Args:
            kbo_number: Belgian KBO number

        Returns:
            Organization data as dict or None
        """
        try:
            with db_session_scope() as session:
                repo = OrganizationRepository(session)
                org = repo.get_by_kbo(kbo_number)
                return org.to_dict() if org else None
        except Exception as e:
            self._logger.error(f"Error getting organization by KBO: {e}")
            return None

    async def search_by_name(self, name_pattern: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search organizations by name.

        Args:
            name_pattern: Name pattern to search
            limit: Maximum results

        Returns:
            List of organization dicts
        """
        try:
            with db_session_scope() as session:
                repo = OrganizationRepository(session)
                orgs = repo.search_by_name(name_pattern, limit)
                return [org.to_dict() for org in orgs]
        except Exception as e:
            self._logger.error(f"Error searching organizations: {e}")
            return []

    async def get_by_city(self, city: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get organizations by city.

        Args:
            city: City name
            limit: Maximum results

        Returns:
            List of organization dicts
        """
        try:
            with db_session_scope() as session:
                repo = OrganizationRepository(session)
                orgs = repo.get_by_city(city, limit)
                return [org.to_dict() for org in orgs]
        except Exception as e:
            self._logger.error(f"Error getting organizations by city: {e}")
            return []

    async def get_stats_by_city(self) -> list[dict[str, Any]]:
        """Get organization count by city.

        Returns:
            List of city stats
        """
        try:
            with db_session_scope() as session:
                repo = OrganizationRepository(session)
                return repo.get_stats_by_city()
        except Exception as e:
            self._logger.error(f"Error getting city stats: {e}")
            return []

    async def get_stats_by_nace(self) -> list[dict[str, Any]]:
        """Get organization count by NACE code.

        Returns:
            List of NACE stats
        """
        try:
            with db_session_scope() as session:
                repo = OrganizationRepository(session)
                return repo.get_stats_by_nace()
        except Exception as e:
            self._logger.error(f"Error getting NACE stats: {e}")
            return []

    async def sync_from_company_record(self, company_data: dict[str, Any]) -> str | None:
        """Sync a company record from the existing companies table.

        This bridges the existing companies table (KBO data) with the
        new organizations table (360 Data Model).

        Args:
            company_data: Company data from companies table

        Returns:
            UID of created/updated organization or None
        """

        try:
            with db_session_scope() as session:
                repo = OrganizationRepository(session)

                # Generate canonical UID from KBO
                kbo = company_data.get("enterprise_number", "")
                uid = f"kbo:{kbo}" if kbo else f"company:{company_data.get('id')}"

                # Check if exists
                org = repo.get_by_uid(uid)

                if org is None:
                    # Create new organization
                    from src.models.organization import Organization

                    org = Organization(
                        uid=uid,
                        uid_type="kbo_number" if kbo else "internal",
                        kbo_number=kbo,
                        legal_name=company_data.get("company_name", "Unknown"),
                        nace_code=company_data.get("nace_code"),
                        city=company_data.get("city"),
                        postal_code=company_data.get("zip_code"),
                        website_url=company_data.get("website"),
                        source_system="kbo_import",
                        source_record_id=str(company_data.get("id", "")),
                    )
                    repo.create(org)
                    self._logger.info(f"Created organization: {uid}")
                else:
                    # Update existing
                    if company_data.get("company_name"):
                        org.legal_name = company_data["company_name"]
                    if company_data.get("nace_code"):
                        org.nace_code = company_data["nace_code"]
                    if company_data.get("city"):
                        org.city = company_data["city"]
                    if company_data.get("website"):
                        org.website_url = company_data["website"]
                    repo.update(org)
                    self._logger.info(f"Updated organization: {uid}")

                session.commit()
                return uid

        except Exception as e:
            self._logger.error(f"Error syncing company to organization: {e}")
            return None
