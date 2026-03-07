"""
Tests for enrichment module.
"""

from datetime import UTC, datetime

import pytest

from src.enrichment.base import EnrichmentResult, EnrichmentStats
from src.enrichment.cbe_integration import CBEIntegrationEnricher
from src.enrichment.contact_validation import ContactValidationEnricher
from src.enrichment.website_discovery import WebsiteDiscoveryEnricher


class TestEnrichmentStats:
    """Test EnrichmentStats dataclass."""

    def test_initial_state(self):
        stats = EnrichmentStats(source="test")
        assert stats.source == "test"
        assert stats.total == 0
        assert stats.success == 0
        assert stats.failed == 0
        assert stats.success_rate == 0.0

    def test_success_rate_calculation(self):
        stats = EnrichmentStats(source="test", total=100, success=80, failed=20)
        assert stats.success_rate == 80.0

    def test_to_dict(self):
        stats = EnrichmentStats(
            source="test",
            total=100,
            success=80,
            failed=20,
        )
        data = stats.to_dict()
        assert data["source"] == "test"
        assert data["total"] == 100
        assert data["success_rate"] == 80.0


class TestContactValidationEnricher:
    """Test contact validation enricher."""

    @pytest.fixture
    def enricher(self):
        return ContactValidationEnricher()

    @pytest.mark.asyncio
    async def test_validate_email_valid(self, enricher):
        result = await enricher.validate_email("test@example.com")
        assert result["valid"] is True
        assert result["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_validate_email_invalid(self, enricher):
        result = await enricher.validate_email("invalid-email")
        assert result["valid"] is False
        assert result["reason"] == "invalid_format"

    @pytest.mark.asyncio
    async def test_validate_email_disposable(self, enricher):
        result = await enricher.validate_email("test@tempmail.com")
        assert result["valid"] is True
        assert result["is_disposable"] is True

    def test_normalize_belgian_phone_mobile(self, enricher):
        result = enricher.normalize_belgian_phone("0475 12 34 56")
        assert result == "+32475123456"

    def test_normalize_belgian_phone_landline(self, enricher):
        result = enricher.normalize_belgian_phone("03 123 45 67")
        assert result == "+3231234567"

    def test_normalize_belgian_phone_already_formatted(self, enricher):
        result = enricher.normalize_belgian_phone("+32475123456")
        assert result == "+32475123456"

    def test_can_enrich_with_email(self, enricher):
        profile = {"traits": {"email": "test@example.com"}}
        assert enricher.can_enrich(profile) is True

    def test_can_enrich_with_phone(self, enricher):
        profile = {"traits": {"phone": "0475123456"}}
        assert enricher.can_enrich(profile) is True

    def test_can_enrich_empty(self, enricher):
        profile = {"traits": {}}
        assert enricher.can_enrich(profile) is False

    @pytest.mark.asyncio
    async def test_enrich_profile_email(self, enricher):
        profile = {"id": "test-1", "traits": {"email": "test@example.com"}}
        result = await enricher.enrich_profile(profile)

        assert "email_validation" in result["traits"]
        assert result["traits"]["email_validation"]["valid"] == 1
        assert result["traits"]["email_normalized"] == "test@example.com"
        assert result["traits"]["contact_quality_score"] == 0.5


class TestWebsiteDiscoveryEnricher:
    """Test website discovery enricher."""

    @pytest.fixture
    def enricher(self):
        return WebsiteDiscoveryEnricher()

    def test_clean_company_name(self, enricher):
        result = enricher._clean_company_name("ACME BVBA")
        assert result == "acme"

    def test_clean_company_name_multiple_forms(self, enricher):
        result = enricher._clean_company_name("My Company NV SA")
        assert result == "mycompany"

    def test_clean_company_name_normalizes_unicode(self, enricher):
        result = enricher._clean_company_name("Café Résumé BV")
        assert result == "caferesume"

    def test_extract_domain_from_email(self, enricher):
        result = enricher._extract_domain_from_email("contact@acme.com")
        assert result == "acme.com"

    def test_extract_domain_from_generic_email(self, enricher):
        result = enricher._extract_domain_from_email("user@gmail.com")
        assert result is None

    def test_generate_url_candidates(self, enricher):
        result = enricher._generate_url_candidates("ACME")
        assert "https://www.acme.be" in result
        assert "https://www.acme.com" in result

    def test_generate_url_candidates_adds_hyphenated_variant(self, enricher):
        result = enricher._generate_url_candidates("ACME Solutions BV")
        assert "https://www.acmesolutions.be" in result
        assert "https://www.acme-solutions.be" in result

    def test_generate_url_candidates_skips_overlong_labels(self, enricher):
        name = "Fondation " + ("Charles " * 12)
        result = enricher._generate_url_candidates(name)
        assert result == []

    def test_can_enrich_with_name(self, enricher):
        profile = {"traits": {"name": "ACME BVBA"}}
        assert enricher.can_enrich(profile) is True


class TestCBEIntegrationEnricher:
    """Test CBE integration enricher."""

    @pytest.fixture
    def enricher(self):
        return CBEIntegrationEnricher(use_api=False)

    def test_normalize_kbo(self, enricher):
        result = enricher._normalize_kbo("123.456.789")
        assert result == "0123456789"

    def test_normalize_kbo_already_valid(self, enricher):
        result = enricher._normalize_kbo("0123456789")
        assert result == "0123456789"

    def test_get_kbo_number_from_traits(self, enricher):
        profile = {"traits": {"enterprise_number": "123456789"}}
        result = enricher._get_kbo_number(profile)
        assert result == "0123456789"

    def test_get_kbo_number_from_kbo(self, enricher):
        profile = {"traits": {"kbo": {"enterprise_number": "987654321"}}}
        result = enricher._get_kbo_number(profile)
        assert result == "0987654321"

    def test_classify_industry_manufacturing(self, enricher):
        result = enricher._classify_industry(["25110"])
        assert result == "Manufacturing"

    def test_classify_industry_it(self, enricher):
        result = enricher._classify_industry(["62010"])
        assert result == "IT & Communications"

    def test_classify_industry_unknown(self, enricher):
        result = enricher._classify_industry([])
        assert result is None

    @pytest.mark.asyncio
    async def test_enrich_profile(self, enricher):
        profile = {
            "id": "test-1",
            "traits": {
                "enterprise_number": "123456789",
                "nace_codes": ["62010"],
            },
        }
        result = await enricher.enrich_profile(profile)

        assert "cbe_enrichment" in result["traits"]
        assert result["traits"]["cbe_enrichment"]["kbo_normalized"] == "0123456789"
        assert result["traits"]["cbe_enrichment"]["industry_sector"] == "IT & Communications"


class TestEnrichmentResult:
    """Test EnrichmentResult dataclass."""

    def test_to_dict(self):
        result = EnrichmentResult(
            entity_id="test-1",
            field="email",
            value="test@example.com",
            success=True,
            source="validation",
            timestamp=datetime.now(UTC).isoformat(),
        )
        data = result.to_dict()
        assert data["entity_id"] == "test-1"
        assert data["field"] == "email"
        assert data["success"] is True
