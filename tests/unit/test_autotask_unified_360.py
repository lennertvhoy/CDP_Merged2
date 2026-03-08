from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.sync_autotask_to_postgres import (
    extract_belgian_kbo,
    find_kbo_match,
    normalize_vat,
)
from src.ai_interface.tools.unified_360 import query_unified_360
from src.services.unified_360_queries import (
    Company360Profile,
    FinancialSummary,
    PipelineSummary,
    Unified360Service,
)


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


def test_autotask_vat_helpers_extract_canonical_belgian_identity():
    assert normalize_vat("0438.437.723") == "BE0438437723"
    assert normalize_vat("BE0438.437.723") == "BE0438437723"
    assert extract_belgian_kbo("BE0438.437.723") == "0438437723"
    assert extract_belgian_kbo("NL123456789B01") is None


@pytest.mark.asyncio
async def test_find_kbo_match_falls_back_to_kbo_derived_from_vat():
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            None,
            {"kbo_number": "0438437723", "uid": "uid-bbs"},
        ]
    )

    kbo_number, uid = await find_kbo_match(
        conn,
        "BE0438.437.723",
        "B.B.S. Entreprise",
        "Antwerp",
    )

    assert kbo_number == "0438437723"
    assert uid == "uid-bbs"
    assert conn.fetchrow.await_count == 2


@pytest.mark.asyncio
async def test_get_company_360_profile_maps_autotask_fields():
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {
                "company_uid": "uid-bbs",
                "kbo_number": "0438437723",
                "vat_number": "BE0438437723",
                "kbo_company_name": "B.B.S. ENTREPRISE",
                "legal_form": "BV",
                "nace_code": "70220",
                "nace_description": "Business consulting",
                "kbo_status": "AC",
                "kbo_city": "Antwerp",
                "website_url": "https://bbsentreprise.be",
                "employee_count": 18,
                "tl_company_id": "tl-1",
                "tl_company_name": "B.B.S. Entreprise",
                "tl_status": "customer",
                "tl_customer_type": "customer",
                "tl_email": "info@bbsentreprise.be",
                "tl_phone": "+3235551234",
                "exact_customer_id": "ex-1",
                "exact_company_name": "Entreprise BCE sprl",
                "exact_status": "C",
                "exact_credit_line": Decimal("15000"),
                "exact_payment_terms": 30,
                "exact_account_manager": "Finance Owner",
                "autotask_company_id": "AT-002",
                "autotask_company_name": "B.B.S. Entreprise",
                "autotask_company_type": "Client",
                "autotask_phone": "+32 3 555 1234",
                "autotask_website": "https://bbsentreprise.be",
                "autotask_total_tickets": 1,
                "autotask_open_tickets": 1,
                "autotask_last_ticket_at": datetime(2026, 3, 8, 10, 0, 0),
                "autotask_total_contracts": 1,
                "autotask_active_contracts": 1,
                "autotask_total_contract_value": Decimal("15000"),
                "autotask_last_contract_start": datetime(2026, 1, 1, 0, 0, 0),
                "has_teamleader": True,
                "has_exact": True,
                "has_autotask": True,
                "total_source_count": 4,
                "identity_link_status": "linked_all",
                "last_updated_at": datetime(2026, 3, 8, 11, 0, 0),
            },
            {
                "tl_open_deals": 2,
                "tl_pipeline_value": Decimal("24500"),
                "tl_won_deals_ytd": 1,
                "tl_won_value_ytd": Decimal("8000"),
                "exact_revenue_ytd": Decimal("120000"),
                "exact_revenue_total": Decimal("250000"),
                "exact_outstanding": Decimal("3000"),
                "exact_overdue": Decimal("500"),
            },
        ]
    )
    service = Unified360Service(pool=_Pool(conn))

    profile = await service.get_company_360_profile(kbo_number="0438437723")

    assert profile is not None
    assert profile.identity_link_status == "linked_all"
    assert profile.has_autotask is True
    assert profile.autotask_company_id == "AT-002"
    assert profile.autotask_open_tickets == 1
    assert profile.autotask_total_contract_value == Decimal("15000")
    assert profile.total_source_count == 4
    assert profile.pipeline == PipelineSummary(
        open_deals_count=2,
        open_deals_value=Decimal("24500"),
        won_deals_ytd=1,
        won_value_ytd=Decimal("8000"),
    )
    assert profile.financials == FinancialSummary(
        revenue_ytd=Decimal("120000"),
        revenue_total=Decimal("250000"),
        outstanding_amount=Decimal("3000"),
        overdue_amount=Decimal("500"),
        total_invoices=0,
        paid_invoices=0,
        open_invoices=0,
        overdue_invoices=0,
        avg_days_overdue=None,
        last_invoice_date=None,
    )


@pytest.mark.asyncio
async def test_query_unified_360_company_profile_serializes_autotask(monkeypatch):
    profile = Company360Profile(
        company_uid="uid-bbs",
        kbo_number="0438437723",
        vat_number="BE0438437723",
        kbo_company_name="B.B.S. ENTREPRISE",
        legal_form="BV",
        nace_code="70220",
        nace_description="Business consulting",
        kbo_status="AC",
        kbo_city="Antwerp",
        website_url="https://bbsentreprise.be",
        employee_count=18,
        tl_company_id="tl-1",
        tl_company_name="B.B.S. Entreprise",
        tl_status="customer",
        tl_customer_type="customer",
        tl_email="info@bbsentreprise.be",
        tl_phone="+3235551234",
        exact_customer_id="ex-1",
        exact_company_name="Entreprise BCE sprl",
        exact_status="C",
        exact_credit_line=Decimal("15000"),
        exact_payment_terms=30,
        exact_account_manager="Finance Owner",
        autotask_company_id="AT-002",
        autotask_company_name="B.B.S. Entreprise",
        autotask_company_type="Client",
        autotask_phone="+32 3 555 1234",
        autotask_website="https://bbsentreprise.be",
        autotask_total_tickets=1,
        autotask_open_tickets=1,
        autotask_last_ticket_at=datetime(2026, 3, 8, 10, 0, 0),
        autotask_total_contracts=1,
        autotask_active_contracts=1,
        autotask_total_contract_value=Decimal("15000"),
        autotask_last_contract_start=datetime(2026, 1, 1, 0, 0, 0),
        has_teamleader=True,
        has_exact=True,
        has_autotask=True,
        total_source_count=4,
        identity_link_status="linked_all",
        last_updated_at=datetime(2026, 3, 8, 11, 0, 0),
        pipeline=PipelineSummary(
            open_deals_count=2,
            open_deals_value=Decimal("24500"),
            won_deals_ytd=1,
            won_value_ytd=Decimal("8000"),
        ),
        financials=FinancialSummary(
            revenue_ytd=Decimal("120000"),
            revenue_total=Decimal("250000"),
            outstanding_amount=Decimal("3000"),
            overdue_amount=Decimal("500"),
        ),
    )

    class _FakeUnified360Service:
        def __init__(self, *args, **kwargs):
            pass

        async def get_company_360_profile(self, **kwargs):
            return profile

        async def close(self):
            return None

    monkeypatch.setattr(
        "src.ai_interface.tools.unified_360.Unified360Service",
        _FakeUnified360Service,
    )

    raw = await query_unified_360.coroutine(
        query_type="company_profile",
        kbo_number="0438437723",
    )
    result = json.loads(raw)

    assert result["identity_link_status"] == "linked_all"
    assert result["total_source_count"] == 4
    assert result["data_sources"] == {
        "kbo": True,
        "teamleader": True,
        "exact": True,
        "autotask": True,
    }
    assert result["autotask"] == {
        "company_id": "AT-002",
        "company_name": "B.B.S. Entreprise",
        "company_type": "Client",
        "phone": "+32 3 555 1234",
        "website": "https://bbsentreprise.be",
        "total_tickets": 1,
        "open_tickets": 1,
        "last_ticket_at": "2026-03-08T10:00:00",
        "total_contracts": 1,
        "active_contracts": 1,
        "total_contract_value": 15000.0,
        "last_contract_start": "2026-01-01T00:00:00",
    }
