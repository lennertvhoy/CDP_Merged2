"""Unit tests for typed intent system.

Tests cover:
- Intent schema validation
- Pattern-based classification
- Parameter extraction
- Execution plan generation
"""

import pytest

from src.ai_interface.intent_classifier import classify_intent
from src.ai_interface.intents import (
    Company360Intent,
    CompanyCountIntent,
    CompanySearchIntent,
    GeographicDistributionIntent,
    HelpIntent,
    IdentityLinkQualityIntent,
    IndustryAnalyticsIntent,
    IntentType,
    SegmentCreateIntent,
    SegmentListIntent,
    UnknownIntent,
)


class TestCompanyCountIntent:
    """Test company count classification."""

    def test_count_companies_in_brussels(self):
        result = classify_intent("How many companies are in Brussels?")
        assert result.intent.intent_type == IntentType.COMPANY_COUNT
        assert result.processing_path == "deterministic"
        assert result.intent.city == "brussels"
        assert "ask_for_clarification" not in result.execution_plan

    def test_count_companies_in_gent(self):
        result = classify_intent("count companies in Gent")
        assert result.intent.intent_type == IntentType.COMPANY_COUNT
        assert result.intent.city == "gent"

    def test_count_with_industry(self):
        result = classify_intent("How many software companies are in Brussels?")
        assert result.intent.intent_type == IntentType.COMPANY_COUNT
        assert result.intent.city == "brussels"
        assert result.intent.industry_keyword == "software"

    def test_total_companies(self):
        result = classify_intent("total number of companies")
        assert result.intent.intent_type == IntentType.COMPANY_COUNT


class TestCompanySearchIntent:
    """Test company search classification."""

    def test_find_companies_in_brussels(self):
        result = classify_intent("Find companies in Brussels")
        assert result.intent.intent_type == IntentType.COMPANY_SEARCH
        assert result.intent.city == "brussels"
        assert result.intent.limit == 100

    def test_list_software_companies(self):
        result = classify_intent("List software companies in Antwerp")
        assert result.intent.intent_type == IntentType.COMPANY_SEARCH
        assert result.intent.city == "antwerp"
        assert result.intent.industry_keyword == "software"

    def test_search_limit_applied(self):
        result = classify_intent("Find all companies in Brussels")
        assert result.intent.intent_type == IntentType.COMPANY_SEARCH
        assert result.intent.limit == 100


class TestCompany360Intent:
    """Test 360 view classification."""

    def test_360_by_kbo(self):
        result = classify_intent("360 view of company 0438.437.723")
        assert result.intent.intent_type == IntentType.COMPANY_360
        assert result.intent.enterprise_number == "0438437723"

    def test_info_by_kbo_dots(self):
        result = classify_intent("Tell me about KBO 0438.437.723")
        assert result.intent.intent_type == IntentType.COMPANY_360
        assert result.intent.enterprise_number == "0438437723"

    def test_details_by_name(self):
        result = classify_intent("Details for Acme Corporation")
        # This might match search or 360 depending on pattern
        assert result.intent.intent_type in [IntentType.COMPANY_360, IntentType.COMPANY_SEARCH]


class TestIndustryAnalyticsIntent:
    """Test industry analytics classification."""

    def test_pipeline_by_industry(self):
        result = classify_intent("What is the pipeline by industry?")
        assert result.intent.intent_type == IntentType.INDUSTRY_ANALYTICS
        assert result.intent.metric in ["all", "pipeline"]

    def test_software_revenue(self):
        result = classify_intent("Show me revenue for software companies")
        assert result.intent.intent_type == IntentType.INDUSTRY_ANALYTICS
        assert result.intent.industry == "software"


class TestGeographicDistributionIntent:
    """Test geographic distribution classification."""

    def test_revenue_distribution(self):
        result = classify_intent("Show me revenue distribution by city")
        assert result.intent.intent_type == IntentType.GEOGRAPHIC_DISTRIBUTION
        assert result.intent.metric in ["revenue", "both"]

    def test_companies_by_city(self):
        result = classify_intent("Where are companies located?")
        assert result.intent.intent_type == IntentType.GEOGRAPHIC_DISTRIBUTION
        assert result.intent.metric == "count"


class TestSegmentIntents:
    """Test segment-related classification."""

    def test_create_segment(self):
        result = classify_intent('Create a segment "Brussels Software"')
        assert result.intent.intent_type == IntentType.SEGMENT_CREATE
        assert result.intent.name == "Brussels Software"

    def test_list_segments(self):
        result = classify_intent("Show my segments")
        assert result.intent.intent_type == IntentType.SEGMENT_LIST
        assert result.intent.limit == 50

    def test_list_segments_alt(self):
        result = classify_intent("List all audiences")
        assert result.intent.intent_type == IntentType.SEGMENT_LIST


class TestIdentityLinkQualityIntent:
    """Test identity link quality classification."""

    def test_link_quality(self):
        result = classify_intent("How well are source systems linked to KBO?")
        assert result.intent.intent_type == IntentType.IDENTITY_LINK_QUALITY
        assert result.intent.source_system == "all"

    def test_teamleader_link_quality(self):
        result = classify_intent("What is the Teamleader match rate?")
        assert result.intent.intent_type == IntentType.IDENTITY_LINK_QUALITY
        assert result.intent.source_system == "teamleader"


class TestHelpIntent:
    """Test help classification."""

    def test_simple_help(self):
        result = classify_intent("help")
        assert result.intent.intent_type == IntentType.HELP

    def test_help_with_topic(self):
        result = classify_intent("Help me with segments")
        assert result.intent.intent_type == IntentType.HELP
        assert result.intent.topic == "segments"


class TestUnknownIntent:
    """Test fallback to unknown intent."""

    def test_empty_query(self):
        result = classify_intent("")
        assert isinstance(result.intent, UnknownIntent)
        assert result.processing_path == "deterministic"

    def test_gibberish(self):
        result = classify_intent("xyz abc 123 not a valid query")
        assert isinstance(result.intent, UnknownIntent)
        assert result.processing_path == "llm_fallback"


class TestExecutionPlans:
    """Test execution plan generation."""

    def test_count_execution_plan(self):
        result = classify_intent("How many companies in Brussels?")
        assert "search_postgresql" in result.execution_plan
        assert "count_results" in result.execution_plan

    def test_360_execution_plan(self):
        result = classify_intent("360 view of 0438.437.723")
        assert "fetch_360_view" in result.execution_plan

    def test_segment_create_plan(self):
        result = classify_intent('Create segment "Test"')
        assert "create_segment" in result.execution_plan


class TestIntentValidation:
    """Test intent schema validation."""

    def test_company_count_validates_status(self):
        intent = CompanyCountIntent(
            original_query="test",
            status="AC",  # Valid status
        )
        assert intent.status == "AC"

    def test_company_360_normalizes_kbo(self):
        intent = Company360Intent(
            original_query="test",
            enterprise_number="0438.437.723",
        )
        assert intent.enterprise_number == "0438437723"

    def test_company_360_normalizes_kbo_with_spaces(self):
        intent = Company360Intent(
            original_query="test",
            enterprise_number="0 438 437 723",
        )
        assert intent.enterprise_number == "0438437723"


class TestCityExtraction:
    """Test city name extraction and normalization."""

    @pytest.mark.parametrize(
        "query,expected_city",
        [
            ("companies in Brussels", "brussels"),
            ("companies in Bruxelles", "brussels"),
            ("companies in Ghent", "gent"),
            ("companies in Antwerpen", "antwerp"),
            ("companies in Anvers", "antwerp"),
        ],
    )
    def test_city_normalization(self, query, expected_city):
        result = classify_intent(query)
        assert result.intent.city == expected_city


class TestIndustryExtraction:
    """Test industry keyword extraction."""

    @pytest.mark.parametrize(
        "query,expected_industry",
        [
            ("software companies", "software"),
            ("restaurant businesses", "restaurant"),
            ("it firms", "it"),
            ("consulting companies", "consulting"),
        ],
    )
    def test_industry_extraction(self, query, expected_industry):
        result = classify_intent(query)
        assert result.intent.industry_keyword == expected_industry
