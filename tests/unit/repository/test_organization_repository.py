"""Unit tests for OrganizationRepository.

Tests repository logic using mocks. Integration tests with PostgreSQL
should be in tests/integration/.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.models.organization import Organization
from src.repository.organization import OrganizationRepository


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return create_autospec(Session, instance=True)


@pytest.fixture
def repository(mock_session: Session) -> OrganizationRepository:
    """Create an OrganizationRepository instance with mock session."""
    return OrganizationRepository(mock_session)


@pytest.fixture
def sample_organization() -> Organization:
    """Create a sample organization for tests."""
    org = Organization(
        organization_id=uuid4(),
        uid="kbo:1234.567.890",
        uid_type="kbo_number",
        kbo_number="1234.567.890",
        vat_number="BE1234567890",
        legal_name="Test Company NV",
        legal_form="NV",
        nace_code="6201",
        nace_description="Computer programming",
        employee_count=50,
        company_size="medium",
        city="Brussels",
        postal_code="1000",
        country_code="BE",
        source_system="test",
        source_record_id="test-123",
    )
    return org


class TestOrganizationRepository:
    """Tests for OrganizationRepository."""

    def test_init(self, mock_session: Session):
        """Test repository initialization."""
        repo = OrganizationRepository(mock_session)
        assert repo.model == Organization
        assert repo.session == mock_session

    def test_get_by_id(
        self,
        repository: OrganizationRepository,
        mock_session: Session,
        sample_organization: Organization,
    ):
        """Test getting organization by ID."""
        mock_session.get.return_value = sample_organization

        result = repository.get_by_id(sample_organization.organization_id)

        mock_session.get.assert_called_once_with(Organization, sample_organization.organization_id)
        assert result == sample_organization

    def test_get_by_uid(
        self,
        repository: OrganizationRepository,
        mock_session: Session,
        sample_organization: Organization,
    ):
        """Test getting organization by UID."""
        # Mock the execute chain
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_organization
        mock_session.execute.return_value = mock_result

        result = repository.get_by_uid("kbo:1234.567.890")

        assert result == sample_organization
        mock_session.execute.assert_called_once()

    def test_get_by_uid_not_found(self, repository: OrganizationRepository, mock_session: Session):
        """Test getting non-existent organization by UID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = repository.get_by_uid("non-existent")

        assert result is None

    def test_get_by_kbo(
        self,
        repository: OrganizationRepository,
        mock_session: Session,
        sample_organization: Organization,
    ):
        """Test getting organization by KBO number."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_organization
        mock_session.execute.return_value = mock_result

        result = repository.get_by_kbo("1234.567.890")

        assert result == sample_organization

    def test_get_by_source(
        self,
        repository: OrganizationRepository,
        mock_session: Session,
        sample_organization: Organization,
    ):
        """Test getting organization by source system reference."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_organization
        mock_session.execute.return_value = mock_result

        result = repository.get_by_source("test", "test-123")

        assert result == sample_organization

    def test_create(
        self,
        repository: OrganizationRepository,
        mock_session: Session,
        sample_organization: Organization,
    ):
        """Test creating an organization."""
        result = repository.create(sample_organization)

        mock_session.add.assert_called_once_with(sample_organization)
        mock_session.flush.assert_called_once()
        assert result == sample_organization

    def test_update(
        self,
        repository: OrganizationRepository,
        mock_session: Session,
        sample_organization: Organization,
    ):
        """Test updating an organization."""
        result = repository.update(sample_organization)

        mock_session.merge.assert_called_once_with(sample_organization)
        mock_session.flush.assert_called_once()
        assert result == sample_organization

    def test_delete(
        self,
        repository: OrganizationRepository,
        mock_session: Session,
        sample_organization: Organization,
    ):
        """Test deleting an organization."""
        repository.delete(sample_organization)

        mock_session.delete.assert_called_once_with(sample_organization)

    def test_get_all(self, repository: OrganizationRepository, mock_session: Session):
        """Test getting all organizations with pagination."""
        orgs = [
            MagicMock(spec=Organization),
            MagicMock(spec=Organization),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orgs
        mock_session.execute.return_value = mock_result

        result = repository.get_all(limit=10, offset=0)

        assert result == orgs
        mock_session.execute.assert_called_once()

    def test_count(self, repository: OrganizationRepository, mock_session: Session):
        """Test counting organizations."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute.return_value = mock_result

        result = repository.count()

        assert result == 42

    def test_search_by_name(self, repository: OrganizationRepository, mock_session: Session):
        """Test searching organizations by name."""
        orgs = [MagicMock(spec=Organization), MagicMock(spec=Organization)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orgs
        mock_session.execute.return_value = mock_result

        result = repository.search_by_name("Acme", limit=20)

        assert result == orgs
        assert len(result) == 2

    def test_get_by_city(self, repository: OrganizationRepository, mock_session: Session):
        """Test getting organizations by city."""
        orgs = [MagicMock(spec=Organization)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orgs
        mock_session.execute.return_value = mock_result

        result = repository.get_by_city("Brussels")

        assert result == orgs

    def test_get_by_nace(self, repository: OrganizationRepository, mock_session: Session):
        """Test getting organizations by NACE code."""
        orgs = [MagicMock(spec=Organization), MagicMock(spec=Organization)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orgs
        mock_session.execute.return_value = mock_result

        result = repository.get_by_nace("6201")

        assert result == orgs
        assert len(result) == 2

    def test_get_with_website(self, repository: OrganizationRepository, mock_session: Session):
        """Test getting organizations with websites."""
        orgs = [MagicMock(spec=Organization)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orgs
        mock_session.execute.return_value = mock_result

        result = repository.get_with_website()

        assert result == orgs

    def test_get_stats_by_city(self, repository: OrganizationRepository, mock_session: Session):
        """Test getting organization count by city."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("Brussels", 100),
            ("Gent", 50),
        ]
        mock_session.execute.return_value = mock_result

        result = repository.get_stats_by_city()

        assert len(result) == 2
        assert result[0]["city"] == "Brussels"
        assert result[0]["count"] == 100

    def test_get_stats_by_nace(self, repository: OrganizationRepository, mock_session: Session):
        """Test getting organization count by NACE code."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("6201", "Computer programming", 75),
            ("4711", "Retail", 25),
        ]
        mock_session.execute.return_value = mock_result

        result = repository.get_stats_by_nace()

        assert len(result) == 2
        assert result[0]["nace_code"] == "6201"
        assert result[0]["count"] == 75


class TestOrganizationModel:
    """Tests for Organization model itself."""

    def test_to_dict(self, sample_organization: Organization):
        """Test converting organization to dict."""
        data = sample_organization.to_dict()

        assert isinstance(data, dict)
        assert data["uid"] == "kbo:1234.567.890"
        assert data["legal_name"] == "Test Company NV"
        assert "organization_id" in data

    def test_repr(self, sample_organization: Organization):
        """Test string representation."""
        repr_str = repr(sample_organization)

        assert "Organization" in repr_str
        assert str(sample_organization.organization_id) in repr_str

    def test_str(self, sample_organization: Organization):
        """Test string conversion."""
        str_str = str(sample_organization)

        assert "Test Company NV" in str_str
        assert "kbo:1234.567.890" in str_str
