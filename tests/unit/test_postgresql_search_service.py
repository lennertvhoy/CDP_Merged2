from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.postgresql_search import (
    CompanySearchFilters,
    PostgreSQLSearchService,
    close_search_service,
)
from src.services.postgresql_search import get_search_service as get_search_service_singleton


class _AcquireContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _AcquireContext(self._conn)


@pytest.fixture
def service_setup(monkeypatch):
    conn = MagicMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchval = AsyncMock(return_value=True)

    client = MagicMock()
    client.ensure_connected = AsyncMock()
    client.disconnect = AsyncMock()
    client.pool = _Pool(conn)

    monkeypatch.setattr("src.services.postgresql_search.get_postgresql_client", lambda: client)

    service = PostgreSQLSearchService()
    return service, client, conn


def test_build_where_clause_normalizes_all_supported_filters(service_setup):
    service, _, _ = service_setup

    filters = CompanySearchFilters(
        keywords="acme",
        enterprise_number="0123.456.789",
        nace_codes=["62010", "62020"],
        juridical_codes=["014"],
        city="Gent",
        zip_code="9000",
        status="ac",
        has_phone=True,
        has_email=True,
    )

    where_clause, params = service._build_where_clause(filters)

    assert where_clause == (
        "company_name ILIKE $1 AND kbo_number = $2 AND "
        "(industry_nace_code IN ($3, $4) OR all_nace_codes && ARRAY[$5, $6]::varchar[]) "
        "AND legal_form IN ($7) AND city IN ($8, $9, $10) AND postal_code = $11 "
        "AND status = $12 "
        "AND main_phone IS NOT NULL AND main_phone != '' "
        "AND main_email IS NOT NULL AND main_email != ''"
    )
    assert params == [
        "%acme%",
        "0123456789",
        "62010",  # For IN clause
        "62020",
        "62010",  # For array overlap
        "62020",
        "014",
        "Gent",
        "Ghent",
        "Gand",
        "9000",
        "AC",
    ]


def test_build_where_clause_expands_antwerp_aliases(service_setup):
    service, _, _ = service_setup

    where_clause, params = service._build_where_clause(
        CompanySearchFilters(city="Antwerp", status=None)
    )

    assert where_clause == "city IN ($1, $2, $3)"
    assert params == ["Antwerp", "Antwerpen", "Anvers"]


def test_build_where_clause_expands_sint_niklaas_aliases(service_setup):
    service, _, _ = service_setup

    where_clause, params = service._build_where_clause(
        CompanySearchFilters(city="Sint Niklaas", status=None)
    )

    assert where_clause == "city IN ($1, $2, $3, $4)"
    assert params == ["Sint Niklaas", "Sint-Niklaas", "Saint-Nicolas", "Saint Nicolas"]


def test_build_where_clause_skips_explicit_all_status_marker(service_setup):
    service, _, _ = service_setup

    where_clause, params = service._build_where_clause(CompanySearchFilters(status="all"))

    assert where_clause == "1=1"
    assert params == []


def test_build_where_clause_maps_min_start_date_to_founded_date(service_setup):
    service, _, _ = service_setup

    where_clause, params = service._build_where_clause(
        CompanySearchFilters(min_start_date="2024-01-01", status=None)
    )

    assert where_clause == "founded_date >= $1::date"
    assert params == [date(2024, 1, 1)]


def test_build_where_clause_supports_email_domain_filter(service_setup):
    service, _, _ = service_setup

    where_clause, params = service._build_where_clause(
        CompanySearchFilters(email_domain="info@Gmail.com", status=None)
    )

    assert where_clause == "LOWER(SPLIT_PART(main_email, '@', 2)) = LOWER($1)"
    assert params == ["gmail.com"]


@pytest.mark.asyncio
async def test_search_companies_executes_queries_and_returns_metadata(service_setup):
    service, client, conn = service_setup
    conn.fetchrow.return_value = (2,)
    conn.fetch.return_value = [
        {"id": "1", "company_name": "Acme BV", "city": "Gent"},
        {"id": "2", "company_name": "Acme NV", "city": "Brugge"},
    ]

    result = await service.search_companies(
        CompanySearchFilters(keywords="Acme", status=None, limit=2, offset=5)
    )

    assert result == {
        "total": 2,
        "result": [
            {"id": "1", "company_name": "Acme BV", "city": "Gent"},
            {"id": "2", "company_name": "Acme NV", "city": "Brugge"},
        ],
        "limit": 2,
        "offset": 5,
        "backend": "postgresql",
        "count_is_estimated": False,
        "count_source": "exact_count",
        "companies_table_empty": False,
    }
    client.ensure_connected.assert_awaited_once()

    count_sql = conn.fetchrow.await_args.args[0]
    search_sql = conn.fetch.await_args.args[0]
    search_params = conn.fetch.await_args.args[1:]

    assert "SELECT COUNT(*)" in count_sql
    assert "ORDER BY company_name" in search_sql
    assert "LIMIT $2 OFFSET $3" in search_sql
    assert search_params == ("%Acme%", 2, 5)


@pytest.mark.asyncio
async def test_count_companies_returns_scalar_count(service_setup):
    service, client, conn = service_setup
    conn.fetchrow.return_value = (7,)

    result = await service.count_companies(CompanySearchFilters(city="Gent", status=None))

    assert result == 7
    client.ensure_connected.assert_awaited_once()
    count_sql = conn.fetchrow.await_args.args[0]
    count_params = conn.fetchrow.await_args.args[1:]
    assert "SELECT COUNT(*)" in count_sql
    assert "city IN ($1, $2, $3)" in count_sql
    assert count_params == ("Gent", "Ghent", "Gand")


@pytest.mark.asyncio
async def test_search_companies_uses_estimated_count_fast_path_for_unfiltered_queries(
    service_setup,
):
    service, client, conn = service_setup
    conn.fetchrow.side_effect = TimeoutError()
    conn.fetchval = AsyncMock(return_value=1940603)
    conn.fetch.return_value = [{"id": "1", "company_name": "Acme BV", "city": "Gent"}]

    result = await service.search_companies(CompanySearchFilters(status=None, limit=1, offset=0))

    assert result["total"] == 1940603
    assert result["count_is_estimated"] is True
    assert result["count_source"] == "estimated_reltuples"
    assert result["result"] == [{"id": "1", "company_name": "Acme BV", "city": "Gent"}]
    assert result["companies_table_empty"] is False
    client.ensure_connected.assert_awaited_once()
    conn.fetchval.assert_awaited_once()
    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_companies_raises_on_filtered_count_timeout(service_setup):
    service, _, conn = service_setup
    conn.fetchrow.side_effect = TimeoutError()

    with pytest.raises(RuntimeError, match="Count query timed out"):
        await service.search_companies(CompanySearchFilters(city="Gent"))


@pytest.mark.asyncio
async def test_search_companies_marks_empty_dataset_on_zero_results(service_setup):
    service, _, conn = service_setup
    conn.fetchrow.return_value = (0,)
    conn.fetch.return_value = []
    conn.fetchval = AsyncMock(return_value=False)

    result = await service.search_companies(
        CompanySearchFilters(city="Sint Niklaas", status=None, limit=5, offset=0)
    )

    assert result["total"] == 0
    assert result["result"] == []
    assert result["companies_table_empty"] is True
    conn.fetchval.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregate_by_field_calculates_coverage_percentages(service_setup):
    service, client, conn = service_setup
    conn.fetchrow.return_value = (10,)
    conn.fetch.return_value = [
        {"group_value": "Gent", "count": 4, "with_email": 3, "with_phone": 2},
        {"group_value": "Brugge", "count": 1, "with_email": 0, "with_phone": 0},
    ]

    result = await service.aggregate_by_field(
        "city",
        CompanySearchFilters(has_email=True, status=None),
        limit=5,
    )

    assert result["status"] == "ok"
    assert result["group_by"] == "city"
    assert result["total_matching_profiles"] == 10
    assert result["backend"] == "postgresql"
    assert result["groups"] == [
        {
            "group_value": "Gent",
            "count": 4,
            "email_coverage_percent": 75.0,
            "phone_coverage_percent": 50.0,
            "percent_of_total": 40.0,
        },
        {
            "group_value": "Brugge",
            "count": 1,
            "email_coverage_percent": 0.0,
            "phone_coverage_percent": 0.0,
            "percent_of_total": 10.0,
        },
    ]
    client.ensure_connected.assert_awaited_once()

    agg_sql = conn.fetch.await_args.args[0]
    assert "GROUP BY city" in agg_sql
    assert "LIMIT $1" in agg_sql


@pytest.mark.asyncio
async def test_aggregate_by_field_groups_business_status_not_sync_status(service_setup):
    service, _, conn = service_setup
    conn.fetchrow.return_value = (4,)
    conn.fetch.return_value = [
        {"group_value": "AC", "count": 4, "with_email": 1, "with_phone": 1},
    ]

    await service.aggregate_by_field("status", CompanySearchFilters(status=None), limit=5)

    agg_sql = conn.fetch.await_args.args[0]
    assert "COALESCE(status, 'Unknown')" in agg_sql
    assert "GROUP BY status" in agg_sql


@pytest.mark.asyncio
async def test_get_company_by_kbo_delegates_to_client(service_setup):
    service, client, _ = service_setup
    client.get_profile_by_kbo = AsyncMock(return_value={"id": "company-1"})

    company = await service.get_company_by_kbo("0123456789")

    assert company == {"id": "company-1"}
    client.ensure_connected.assert_awaited_once()
    client.get_profile_by_kbo.assert_awaited_once_with("0123456789")


@pytest.mark.asyncio
async def test_get_company_by_id_returns_dict_and_coverage_stats(service_setup):
    service, _, conn = service_setup
    conn.fetchrow.side_effect = [
        {"id": "company-1", "company_name": "Acme BV"},
        {
            "total_companies": 5,
            "with_email": 2,
            "with_phone": 1,
            "with_website": 4,
            "with_geocoding": 0,
            "with_nace": 3,
            "with_ai_description": 1,
            "with_legal_form": 5,
        },
    ]

    company = await service.get_company_by_id("company-1")
    stats = await service.get_coverage_stats()

    assert company == {"id": "company-1", "company_name": "Acme BV"}
    assert stats == {
        "status": "ok",
        "total_companies": 5,
        "coverage": {
            "email": {"count": 2, "percent": 40.0},
            "phone": {"count": 1, "percent": 20.0},
            "website": {"count": 4, "percent": 80.0},
            "geocoding": {"count": 0, "percent": 0.0},
            "nace_code": {"count": 3, "percent": 60.0},
            "ai_description": {"count": 1, "percent": 20.0},
            "legal_form": {"count": 5, "percent": 100.0},
        },
        "backend": "postgresql",
    }


@pytest.mark.asyncio
async def test_search_service_singleton_can_be_closed(monkeypatch):
    # Reset module-level singleton state to ensure test isolation
    # This fixes order-dependent failures when other tests initialize the singleton
    import src.services.postgresql_search as search_module

    monkeypatch.setattr(search_module, "_search_service", None)

    client = MagicMock()
    client.ensure_connected = AsyncMock()
    client.disconnect = AsyncMock()
    client.pool = _Pool(MagicMock())

    monkeypatch.setattr("src.services.postgresql_search.get_postgresql_client", lambda: client)

    service = get_search_service_singleton()

    assert service is get_search_service_singleton()

    await close_search_service()

    client.disconnect.assert_awaited_once()
