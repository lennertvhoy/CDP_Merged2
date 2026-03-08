from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.canonical_segments import CanonicalSegmentService
from src.services.postgresql_search import CompanySearchFilters


class _AcquireContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _TransactionContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _AcquireContext(self._conn)


def _build_service():
    conn = MagicMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=_TransactionContext())

    client = MagicMock()
    client.pool = _Pool(conn)
    client.connection_url = "postgresql://local/test"

    search_service = MagicMock()
    search_service.ensure_connected = AsyncMock()
    search_service._client = client
    search_service._build_where_clause = MagicMock(return_value=("city = $1", ["Brussels"]))

    service = CanonicalSegmentService(search_service=search_service)
    return service, search_service, conn


@pytest.mark.asyncio
async def test_upsert_segment_writes_definition_and_memberships():
    service, search_service, conn = _build_service()
    conn.fetchrow.side_effect = [
        [7],
        {
            "segment_id": "11111111-1111-1111-1111-111111111111",
            "segment_key": "brussels-software",
            "segment_name": "Brussels Software",
        },
    ]

    with patch(
        "src.services.canonical_segments.ensure_runtime_support_schema",
        new=AsyncMock(return_value=True),
    ):
        result = await service.upsert_segment(
            name="Brussels Software",
            filters=CompanySearchFilters(city="Brussels"),
            condition='traits.city="Brussels"',
            description="Created by AI",
        )

    assert result["segment_key"] == "brussels-software"
    assert result["member_count"] == 7
    search_service.ensure_connected.assert_awaited_once()
    search_service._build_where_clause.assert_called_once()

    execute_calls = conn.execute.await_args_list
    assert "DELETE FROM segment_memberships" in execute_calls[0].args[0]
    assert "INSERT INTO segment_memberships" in execute_calls[1].args[0]
    assert execute_calls[1].args[1] == "Brussels"


@pytest.mark.asyncio
async def test_upsert_segment_rejects_unfiltered_search():
    service, _, _ = _build_service()

    with patch(
        "src.services.canonical_segments.ensure_runtime_support_schema",
        new=AsyncMock(return_value=True),
    ):
        with pytest.raises(ValueError, match="Refine the search"):
            await service.upsert_segment(
                name="Everything",
                filters=CompanySearchFilters(),
            )


@pytest.mark.asyncio
async def test_get_segment_members_returns_rows_and_total():
    service, _, conn = _build_service()
    conn.fetchrow.side_effect = [
        {
            "segment_id": "11111111-1111-1111-1111-111111111111",
            "segment_key": "brussels-software",
            "segment_name": "Brussels Software",
            "description": "Created by AI",
            "definition_type": "metadata",
            "definition_json": {"filters": {"city": "Brussels", "has_email": True}},
        },
        [2],
    ]
    conn.fetch.return_value = [
        {
            "id": "uid-1",
            "company_name": "Acme BV",
            "city": "Brussels",
            "main_email": "info@acme.be",
        },
        {
            "id": "uid-2",
            "company_name": "Bravo NV",
            "city": "Brussels",
            "main_email": "",
        },
    ]

    with patch(
        "src.services.canonical_segments.ensure_runtime_support_schema",
        new=AsyncMock(return_value=True),
    ):
        result = await service.get_segment_members("Brussels Software", limit=10)

    assert result is not None
    assert result["total_count"] == 2
    assert result["segment_key"] == "brussels-software"
    assert result["definition_json"] == {"filters": {"city": "Brussels", "has_email": True}}
    assert result["rows"][0]["company_name"] == "Acme BV"


@pytest.mark.asyncio
async def test_get_segment_stats_returns_authoritative_counts():
    service, _, conn = _build_service()
    conn.fetchrow.side_effect = [
        {
            "segment_id": "11111111-1111-1111-1111-111111111111",
            "segment_key": "brussels-software",
            "segment_name": "Brussels Software",
            "description": "Created by AI",
            "definition_type": "metadata",
            "definition_json": {},
        },
        {
            "total_count": 3,
            "email_count": 2,
            "phone_count": 1,
        },
    ]
    conn.fetch.side_effect = [
        [{"label": "Brussels", "count": 3}],
        [{"label": "AC", "count": 2}, {"label": "IN", "count": 1}],
        [{"label": "BV", "count": 2}, {"label": "NV", "count": 1}],
    ]

    with patch(
        "src.services.canonical_segments.ensure_runtime_support_schema",
        new=AsyncMock(return_value=True),
    ):
        result = await service.get_segment_stats("brussels-software")

    assert result is not None
    assert result["profile_count"] == 3
    assert result["contact_coverage"]["profiles_with_email"] == 2
    assert result["top_cities"][0] == {"city": "Brussels", "count": 3}
    assert result["status_distribution"] == {"AC": 2, "IN": 1}
