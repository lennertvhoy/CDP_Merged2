"""
API Test Suite for CDP KBO Agent

Tests for new features:
- Revenue/employee/founding date endpoints
- Phone discovery endpoints
- CSV export endpoints
- Error handling
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_interface.tools import email_segment_export, export_segment_to_csv
from src.enrichment.phone_discovery import PhoneDiscoveryEnricher

# Import services under test
from src.services.cbe_extended import CBEExtendedClient

pytestmark = pytest.mark.integration


class TestCBEExtendedClient:
    """Tests for CBE Extended Client (revenue, employees, founding date)."""

    @pytest.fixture
    def cbe_client(self, tmp_path):
        return CBEExtendedClient(
            data_dir=str(tmp_path / "cbe_test"),
            use_api=True,
        )

    @pytest.mark.asyncio
    async def test_fetch_company_financials_success(self, cbe_client):
        """Test fetching financial data for a valid KBO."""
        with (
            patch.object(cbe_client, "fetch_enterprise_details", return_value=None),
            patch.object(cbe_client, "fetch_annual_accounts", return_value=None),
            patch.object(cbe_client, "get_revenue", return_value={"revenue_eur": 1250000}),
            patch.object(cbe_client, "get_employee_count", return_value={"total": 42}),
            patch.object(cbe_client, "get_founding_date", return_value="1995-03-15"),
        ):
            result = await cbe_client.get_company_financials("0200225413")

        assert result["kbo_number"] == "0200225413"
        assert result["revenue"]["revenue_eur"] == 1250000
        assert result["employees"]["total"] == 42
        assert result["founding"] == "1995-03-15"

    @pytest.mark.asyncio
    async def test_fetch_company_financials_not_found(self, cbe_client):
        """Test handling of non-existent KBO."""
        with (
            patch.object(cbe_client, "fetch_enterprise_details", return_value=None),
            patch.object(cbe_client, "fetch_annual_accounts", return_value=None),
        ):
            result = await cbe_client.get_company_financials("0999999999")

        assert result["kbo_number"] == "0999999999"
        assert result["revenue"] is None

    @pytest.mark.asyncio
    async def test_fetch_company_financials_api_error(self, cbe_client):
        """Test handling of API errors."""
        with (
            patch.object(
                cbe_client, "fetch_enterprise_details", side_effect=Exception("Connection failed")
            ),
            patch.object(
                cbe_client, "fetch_annual_accounts", side_effect=Exception("Connection failed")
            ),
        ):
            with pytest.raises(ConnectionError):
                await cbe_client.get_company_financials("0200225413")

    def test_normalize_kbo_10_digits(self, cbe_client):
        """Test KBO normalization for 10-digit input."""
        assert cbe_client._normalize_kbo("0200225413") == "0200225413"

    def test_normalize_kbo_9_digits(self, cbe_client):
        """Test KBO normalization for 9-digit input (adds leading zero)."""
        assert cbe_client._normalize_kbo("200225413") == "0200225413"

    def test_calculate_company_size_micro(self, cbe_client):
        """Test company size categorization - micro."""
        assert cbe_client._categorize_company_size(5) == "micro"

    def test_calculate_company_size_small(self, cbe_client):
        """Test company size categorization - small."""
        assert cbe_client._categorize_company_size(25) == "small"

    def test_calculate_company_size_medium(self, cbe_client):
        """Test company size categorization - medium."""
        assert cbe_client._categorize_company_size(100) == "medium"

    def test_calculate_company_size_large(self, cbe_client):
        """Test company size categorization - large."""
        assert cbe_client._categorize_company_size(300) == "large"


class TestPhoneDiscoveryEnricher:
    """Tests for Phone Discovery enrichment."""

    @pytest.fixture
    def phone_enricher(self, tmp_path):
        return PhoneDiscoveryEnricher(
            cache_dir=str(tmp_path),
            cache_file="phone_test_cache.json",
        )

    def test_normalize_phone_belgian_landline(self, phone_enricher):
        """Test normalization of Belgian landline number."""
        assert phone_enricher.discovery._normalize_phone("02 123 45 67") == "+3221234567"

    def test_normalize_phone_belgian_mobile(self, phone_enricher):
        """Test normalization of Belgian mobile number."""
        assert phone_enricher.discovery._normalize_phone("0471 23 45 67") == "+32471234567"

    def test_normalize_phone_international(self, phone_enricher):
        """Test preservation of already international number."""
        assert phone_enricher.discovery._normalize_phone("+32 2 123 45 67") == "+3221234567"

    def test_normalize_phone_invalid(self, phone_enricher):
        """Test handling of invalid phone number."""
        assert phone_enricher.discovery._normalize_phone("123") is None

    @pytest.mark.asyncio
    async def test_enrich_profile_with_website(self, phone_enricher):
        """Test enriching profile with website for phone discovery."""
        profile = {
            "id": "test-1",
            "traits": {"website": "https://example.com"},
        }

        mock_discover = AsyncMock(return_value="+3221234567")
        with patch.object(phone_enricher.discovery, "discover_from_website", new=mock_discover):
            result = await phone_enricher.enrich_profile(profile)

        assert result["traits"]["phone"] == "+3221234567"
        assert result["traits"]["phone_discovered"] is True

    @pytest.mark.asyncio
    async def test_enrich_profile_from_cbe_data(self, phone_enricher):
        """Test enriching profile from CBE contact data."""
        profile = {
            "id": "test-1",
            "traits": {
                "kbo": "0200225413",
                # No website
            },
        }

        # Mock CBE phone lookup
        mock_discover = AsyncMock(return_value="+3221234567")
        with patch.object(phone_enricher.discovery, "discover_from_cbe", new=mock_discover):
            result = await phone_enricher.enrich_profile(profile)

        assert result["traits"]["phone"] == "+3221234567"
        assert result["traits"]["phone_discovered"] is True

    @pytest.mark.asyncio
    async def test_enrich_profile_no_data(self, phone_enricher):
        """Test enriching profile with no phone data available."""
        profile = {
            "id": "test-1",
            "traits": {},  # No website, no KBO
        }

        result = await phone_enricher.enrich_profile(profile)

        # Should return profile unchanged
        assert result == profile


class TestExportTools:
    """Tests for CSV export and email functionality."""

    @pytest.fixture
    def sample_profiles(self):
        return [
            {
                "id": "prof-1",
                "traits": {
                    "name": "Acme BV",
                    "company": "Acme BV",
                    "kbo": "0200225413",
                    "email": "info@acme.be",
                },
                "data": {
                    "job": {"company": {"name": "Acme BV"}},
                    "contact": {
                        "email": {"main": "info@acme.be"},
                        "address": {"town": "Brussels"},
                    },
                },
            },
            {
                "id": "prof-2",
                "traits": {
                    "name": "Tech SA",
                    "company": "Tech SA",
                    "kbo": "0200225414",
                    "email": "contact@tech.be",
                },
                "data": {
                    "job": {"company": {"name": "Tech SA"}},
                    "contact": {
                        "email": {"main": "contact@tech.be"},
                        "address": {"town": "Antwerp"},
                    },
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_export_segment_to_csv_default_fields(self, tmp_path, sample_profiles):
        """Test CSV export with default fields."""
        import json

        with (
            patch("src.ai_interface.tools.export.TracardiClient") as mock_cls,
            patch("tempfile.gettempdir", return_value=str(tmp_path)),
        ):
            mock_client = AsyncMock()
            mock_client.search_profiles.return_value = {"result": sample_profiles, "total": 2}
            mock_cls.return_value = mock_client

            result_str = await export_segment_to_csv.ainvoke(
                {
                    "segment_id": "test_segment",
                }
            )
            result = json.loads(result_str)

            assert result["status"] == "ok"
            assert result["exported_count"] == 2

            output_dir = tmp_path / "cdp_exports"
            files = list(output_dir.glob("test_segment_*.csv"))
            assert len(files) == 1
            content = files[0].read_text()
            assert "name,email,phone,city" in content
            assert "Acme BV" in content
            assert "Tech SA" in content

    @pytest.mark.asyncio
    async def test_export_segment_to_csv_custom_fields(self, tmp_path, sample_profiles):
        """Test CSV export with custom field configuration."""
        import json

        with (
            patch("src.ai_interface.tools.export.TracardiClient") as mock_cls,
            patch("tempfile.gettempdir", return_value=str(tmp_path)),
        ):
            mock_client = AsyncMock()
            mock_client.search_profiles.return_value = {"result": sample_profiles, "total": 2}
            mock_cls.return_value = mock_client

            fields = ["name", "email"]
            result_str = await export_segment_to_csv.ainvoke(
                {
                    "segment_id": "test_custom_segment",
                    "include_fields": fields,
                }
            )
            result = json.loads(result_str)

            assert result["status"] == "ok"
            output_dir = tmp_path / "cdp_exports"
            files = list(output_dir.glob("test_custom_segment_*.csv"))
            content = files[0].read_text()
            assert "name,email" in content
            assert "city" not in content  # Not requested

    @pytest.mark.asyncio
    async def test_export_segment_to_csv_empty_profiles(self, tmp_path):
        """Test CSV export with empty profile list."""
        import json

        with patch("src.ai_interface.tools.export.TracardiClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.search_profiles.return_value = {"result": [], "total": 0}
            mock_cls.return_value = mock_client

            result_str = await export_segment_to_csv.ainvoke(
                {
                    "segment_id": "empty_segment",
                }
            )
            result = json.loads(result_str)

            assert result["status"] == "ok"
            assert result["exported_count"] == 0
            assert "no profiles" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_email_segment_export_success(self, tmp_path, sample_profiles):
        """Test email export with Resend integration."""
        with (
            patch("src.ai_interface.tools.export.TracardiClient") as mock_cls,
            patch("tempfile.gettempdir", return_value=str(tmp_path)),
        ):
            mock_client = AsyncMock()
            mock_client.search_profiles.return_value = {"result": sample_profiles, "total": 2}
            mock_cls.return_value = mock_client

            # Mock Resend client
            mock_resend_instance = AsyncMock()
            mock_resend_instance.send_email.return_value = {"id": "email-123"}
            mock_resend_cls = Mock(return_value=mock_resend_instance)

            with patch("src.ai_interface.tools.export.ResendClient", mock_resend_cls):
                result = await email_segment_export.ainvoke(
                    {
                        "segment_id": "test_segment",
                        "email_address": "user@example.com",
                        "message": "Test Export",
                    }
                )

            assert "Message ID: email-123" in result
            mock_resend_instance.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_segment_export_file_not_found(self):
        """Test email export with failing CSV export."""
        with patch("src.ai_interface.tools.export.TracardiClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.search_profiles.return_value = {"result": [], "total": 0}
            mock_cls.return_value = mock_client

            # Mock Resend client so it doesn't crash on invalid real call
            mock_resend_instance = AsyncMock()
            mock_resend_instance.send_email.return_value = {"id": "email-empty-123"}
            mock_resend_cls = Mock(return_value=mock_resend_instance)

            with patch("src.ai_interface.tools.export.ResendClient", mock_resend_cls):
                # Export returns OK but count 0
                result = await email_segment_export.ainvoke(
                    {
                        "segment_id": "empty_segment",
                        "email_address": "user@example.com",
                    }
                )

            assert "Message ID" in result  # It should proceed to send an empty export email


class TestPipelineIntegration:
    """Integration tests for the enrichment pipeline."""

    @pytest.fixture
    def sample_profile_full(self):
        """Sample profile with various data fields."""
        return {
            "id": "test-prof-123",
            "traits": {
                "company": "Test Company BV",
                "kbo": "0200225413",
                "email": "info@testcompany.be",
                "website": "https://testcompany.be",
                "address": {
                    "street": "Test Street 123",
                    "postcode": "1000",
                    "city": "Brussels",
                },
            },
        }


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_cbe_client_rate_limit_handling(self):
        """Test handling of rate limit errors from CBE API."""
        client = CBEExtendedClient(use_api=True)

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            # Should handle gracefully without throwing
            result = await client.get_company_financials("0200225413")

        # Should return a safe default dict on rate limit
        assert result["revenue"] is None
        assert result["employees"] is None

    @pytest.mark.asyncio
    async def test_phone_discovery_website_timeout(self):
        """Test handling of website timeout during phone discovery."""
        enricher = PhoneDiscoveryEnricher()

        profile = {
            "id": "test-1",
            "traits": {"website": "https://slow-website.be"},
        }

        import httpx

        with patch(
            "httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timeout")
        ):
            result = await enricher.enrich_profile(profile)

        # Should return profile unchanged on timeout
        assert result == profile

    @pytest.mark.asyncio
    async def test_export_invalid_csv_path(self):
        """Test export with error from search_profiles."""
        import json

        with patch("src.ai_interface.tools.export.TracardiClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.search_profiles.return_value = None
            mock_cls.return_value = mock_client

            result_str = await export_segment_to_csv.ainvoke(
                {
                    "segment_id": "invalid_segment",
                }
            )
            result = json.loads(result_str)

            assert result["status"] == "error"
            assert "Failed to retrieve" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
