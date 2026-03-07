from __future__ import annotations

import pytest

from scripts.demo_teamleader_integration import TeamleaderDemo, parse_args


class _FakeTeamleaderClient:
    def refresh_access_token(self) -> str:
        return "live-access-token"

    def list_records(
        self,
        endpoint: str,
        *,
        page_size: int = 10,
        page_number: int = 1,
        extra_payload: dict | None = None,
    ) -> dict:
        if endpoint == "companies.list":
            return {
                "data": [
                    {
                        "id": "company-live-1",
                        "name": "Live Company NV",
                        "address": {"city": "Gent", "country": "BE"},
                        "status": "active",
                    }
                ]
            }
        if endpoint == "contacts.list":
            return {
                "data": [
                    {
                        "id": "contact-live-1",
                        "first_name": "Alicia",
                        "last_name": "Peeters",
                        "position": "CTO",
                        "email": "alicia@example.com",
                        "decision_maker": True,
                    }
                ]
            }
        if endpoint == "deals.list":
            return {
                "data": [
                    {
                        "id": "deal-live-1",
                        "title": "Expansion Project",
                        "status": "open",
                        "value": {"amount": 12000, "currency": "EUR"},
                        "probability": 70,
                    }
                ]
            }
        if endpoint == "events.list":
            return {
                "data": [
                    {
                        "id": "event-live-1",
                        "title": "Discovery Call",
                        "description": "Scheduled follow-up call",
                        "starts_at": "2026-03-05T12:30:00+01:00",
                        "activity_type": {"type": "call", "id": "activity-type-1"},
                        "creator": {"type": "user", "id": "user-1"},
                        "links": [{"type": "company", "id": "company-live-1"}],
                    }
                ]
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")


def test_teamleader_demo_stays_mock_without_local_client(monkeypatch) -> None:
    monkeypatch.setattr(TeamleaderDemo, "_build_teamleader_client", lambda self: None)

    demo = TeamleaderDemo()

    assert demo.teamleader_client is None
    assert demo.provenance == "mock"
    assert demo.mode_description.startswith("MOCK")


@pytest.mark.asyncio
async def test_teamleader_demo_uses_live_data_when_local_client_exists(monkeypatch) -> None:
    monkeypatch.setattr(
        TeamleaderDemo,
        "_build_teamleader_client",
        lambda self: _FakeTeamleaderClient(),
    )

    demo = TeamleaderDemo()
    await demo.authenticate()
    await demo.get_company_profile()
    await demo.get_contacts()
    await demo.get_deals_pipeline()
    await demo.get_activity_history()
    enrichment = await demo.sync_to_cdp()

    assert enrichment["metadata"]["provenance"] == "real"
    assert enrichment["metadata"]["company"]["name"] == "Live Company NV"
    assert enrichment["metadata"]["source_modes"]["company"] == "real"
    assert enrichment["metadata"]["source_modes"]["deals"] == "real"
    assert enrichment["metadata"]["source_modes"]["activities"] == "real"
    assert enrichment["traits"]["deal_pipeline_value"] == 12000


class _FakeTeamleaderClientWithoutEvents(_FakeTeamleaderClient):
    def list_records(
        self,
        endpoint: str,
        *,
        page_size: int = 10,
        page_number: int = 1,
        extra_payload: dict | None = None,
    ) -> dict:
        if endpoint == "events.list":
            return {"data": []}
        return super().list_records(
            endpoint,
            page_size=page_size,
            page_number=page_number,
            extra_payload=extra_payload,
        )


@pytest.mark.asyncio
async def test_teamleader_demo_falls_back_to_mock_activities_when_no_live_events_exist(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        TeamleaderDemo,
        "_build_teamleader_client",
        lambda self: _FakeTeamleaderClientWithoutEvents(),
    )

    demo = TeamleaderDemo()
    await demo.authenticate()
    await demo.get_company_profile()
    await demo.get_contacts()
    await demo.get_deals_pipeline()
    await demo.get_activity_history()
    enrichment = await demo.sync_to_cdp()

    assert enrichment["metadata"]["provenance"] == "hybrid"
    assert enrichment["metadata"]["source_modes"]["activities"] == "mock"


class TestTeamleaderDemoPagination:
    """Test full pagination mode and rate limit monitoring."""

    def test_full_pagination_mode_can_be_enabled(self) -> None:
        """Demo should support full pagination mode."""
        demo = TeamleaderDemo(full_pagination=True, max_contacts=100, max_deals=50)

        assert demo.full_pagination is True
        assert demo.max_contacts == 100
        assert demo.max_deals == 50

    def test_default_pagination_mode_is_disabled(self) -> None:
        """Default mode should not use full pagination."""
        demo = TeamleaderDemo()

        assert demo.full_pagination is False
        assert demo.max_contacts == 50
        assert demo.max_deals == 50

    def test_rate_limit_status_with_no_client(self) -> None:
        """Rate limit status should handle missing client gracefully."""
        demo = TeamleaderDemo()
        demo.teamleader_client = None

        # Should not raise an exception
        demo._show_rate_limit_status()

    def test_pages_fetched_tracking_initialized(self) -> None:
        """Pages fetched tracking should be initialized."""
        demo = TeamleaderDemo()

        assert demo.pages_fetched["contacts"] == 0
        assert demo.pages_fetched["deals"] == 0
        assert demo.pages_fetched["activities"] == 0


class TestParseArgs:
    """Test command-line argument parsing."""

    def test_default_args(self, monkeypatch) -> None:
        """Default arguments should be set correctly."""
        monkeypatch.setattr("sys.argv", ["demo_teamleader_integration.py"])

        args = parse_args()

        assert args.full_pagination is False
        assert args.max_contacts == 50
        assert args.max_deals == 50

    def test_full_pagination_flag(self, monkeypatch) -> None:
        """Full pagination flag should be parsed."""
        monkeypatch.setattr("sys.argv", ["demo_teamleader_integration.py", "--full-pagination"])

        args = parse_args()

        assert args.full_pagination is True

    def test_custom_max_contacts(self, monkeypatch) -> None:
        """Custom max contacts should be parsed."""
        monkeypatch.setattr(
            "sys.argv", ["demo_teamleader_integration.py", "--max-contacts", "100"]
        )

        args = parse_args()

        assert args.max_contacts == 100

    def test_custom_max_deals(self, monkeypatch) -> None:
        """Custom max deals should be parsed."""
        monkeypatch.setattr("sys.argv", ["demo_teamleader_integration.py", "--max-deals", "25"])

        args = parse_args()

        assert args.max_deals == 25

    def test_full_pagination_with_custom_limits(self, monkeypatch) -> None:
        """Full pagination with all custom options."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "demo_teamleader_integration.py",
                "--full-pagination",
                "--max-contacts",
                "200",
                "--max-deals",
                "100",
            ],
        )

        args = parse_args()

        assert args.full_pagination is True
        assert args.max_contacts == 200
        assert args.max_deals == 100
