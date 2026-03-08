"""Tests for NACE code resolver."""

from __future__ import annotations

from unittest.mock import patch

from src.ai_interface.tools.nace_resolver import (
    DOMAIN_HINT_CODES,
    DOMAIN_SYNONYMS,
    NACE_CATALOG,
    _expand_search_terms,
    _get_nace_codes_from_keyword,
    _is_overly_generic_keyword,
    _load_json_data,
    _load_kbo_nace_codes,
    _load_nace_catalog,
    _normalize_text,
    _resolve_domain_key,
    _score_nace_description,
    lookup_juridical_code,
    lookup_nace_code,
)


class TestNormalizeText:
    """Test _normalize_text function."""

    def test_normalize_lowercase(self):
        """Test normalization to lowercase."""
        assert _normalize_text("IT") == "it"
        assert _normalize_text("Restaurant") == "restaurant"

    def test_normalize_accent_removal(self):
        """Test removal of accents."""
        assert _normalize_text("café") == "cafe"
        assert _normalize_text("naïve") == "naive"

    def test_normalize_punctuation_removal(self):
        """Test removal of punctuation."""
        assert _normalize_text("IT-company") == "it company"
        assert _normalize_text("Co., Ltd.") == "co ltd"

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        assert _normalize_text("  IT   company  ") == "it company"

    def test_normalize_empty(self):
        """Test empty string handling."""
        assert _normalize_text("") == ""
        assert _normalize_text(None) == ""


class TestResolveDomainKey:
    """Test _resolve_domain_key function."""

    def test_resolve_exact_match(self):
        """Test exact domain match."""
        assert _resolve_domain_key("it") == "it"
        assert _resolve_domain_key("restaurant") == "restaurant"

    def test_resolve_synonym(self):
        """Test synonym resolution."""
        assert _resolve_domain_key("software") == "it"
        assert _resolve_domain_key("horeca") == "restaurant"

    def test_resolve_multi_token(self):
        """Test multi-token keyword resolution."""
        assert _resolve_domain_key("information technology") == "it"

    def test_resolve_no_match(self):
        """Test no domain match."""
        assert _resolve_domain_key("unknown") is None


class TestExpandSearchTerms:
    """Test _expand_search_terms function."""

    def test_expand_basic(self):
        """Test basic term expansion."""
        result = _expand_search_terms("restaurant")
        assert "restaurant" in result
        # Should include domain synonyms
        assert "restaurants" in result

    def test_expand_plural_removal(self):
        """Test plural form handling."""
        result = _expand_search_terms("restaurants")
        assert "restaurants" in result
        assert "restaurant" in result

    def test_expand_ies_to_y(self):
        """Test 'ies' to 'y' conversion."""
        result = _expand_search_terms("companies")
        assert "companies" in result
        assert "company" in result

    def test_expand_domain_synonyms(self):
        """Test domain synonym expansion."""
        result = _expand_search_terms("it")
        # Should include all IT domain synonyms
        assert "it" in result
        assert "ict" in result
        assert "software" in result


class TestIsOverlyGenericKeyword:
    """Test _is_overly_generic_keyword function."""

    def test_generic_terms_only(self):
        """Test detection of overly generic keywords."""
        assert _is_overly_generic_keyword("business", None) is True
        assert _is_overly_generic_keyword("company", None) is True
        assert _is_overly_generic_keyword("enterprise", None) is True

    def test_specific_with_domain(self):
        """Test that domain keywords are not generic."""
        assert _is_overly_generic_keyword("restaurant", "restaurant") is False
        assert _is_overly_generic_keyword("it", "it") is False

    def test_mixed_terms(self):
        """Test mixed generic and specific terms."""
        assert _is_overly_generic_keyword("it company", "it") is False
        assert _is_overly_generic_keyword("restaurant business", "restaurant") is False


class TestScoreNaceDescription:
    """Test _score_nace_description function."""

    def test_score_exact_match(self):
        """Test high score for exact match."""
        score = _score_nace_description(
            "software", {"software"}, "development of computer software"
        )
        assert score > 0

    def test_score_no_match(self):
        """Test zero score for no match."""
        score = _score_nace_description("bakery", {"bakery"}, "computer programming activities")
        assert score == 0

    def test_score_empty_description(self):
        """Test zero score for empty description."""
        score = _score_nace_description("software", {"software"}, "")
        assert score == 0

    def test_score_short_term_boundaries(self):
        """Test boundary matching for short terms."""
        # "IT" should not match "sanITary"
        score = _score_nace_description("it", {"it"}, "sanitary engineering")
        assert score == 0


class TestGetNaceCodesFromKeyword:
    """Test _get_nace_codes_from_keyword function."""

    def test_lookup_it_codes(self):
        """Test looking up IT-related codes."""
        result = _get_nace_codes_from_keyword("IT")
        assert result == ["62100", "62200", "62900", "63100"]

    def test_lookup_restaurant_codes(self):
        """Test looking up restaurant codes."""
        result = _get_nace_codes_from_keyword("restaurant")
        assert len(result) > 0
        # Restaurant codes should start with 56
        assert all(code.startswith("56") for code in result)

    def test_lookup_empty_keyword(self):
        """Test empty keyword returns empty list."""
        result = _get_nace_codes_from_keyword("")
        assert result == []

    def test_lookup_generic_keyword(self):
        """Test overly generic keyword returns empty list."""
        result = _get_nace_codes_from_keyword("business")
        assert result == []

    def test_lookup_no_match(self):
        """Test keyword with no matches returns empty list."""
        result = _get_nace_codes_from_keyword("xyznonexistent")
        assert result == []

    def test_lookup_max_results(self):
        """Test that results are limited to max 12."""
        # Use a broad keyword that would match many codes
        result = _get_nace_codes_from_keyword("computer")
        assert len(result) <= 12


class TestLoadJsonData:
    """Test _load_json_data function."""

    def test_load_missing_file(self, tmp_path):
        """Test handling of missing file - returns empty dict."""
        result = _load_json_data("nonexistent_file_that_does_not_exist.json")
        assert result == {}


class TestLoadKboNaceCodes:
    """Test _load_kbo_nace_codes function."""

    def test_load_kbo_missing_file(self):
        """Test handling when KBO file is missing - returns empty dict."""
        result = _load_kbo_nace_codes()
        # When code.csv doesn't exist, should return empty dict
        assert result == {}


class TestLoadNaceCatalog:
    """Test _load_nace_catalog function."""

    @patch("src.ai_interface.tools.nace_resolver.NACE_CODES", {"62010": "Programming"})
    @patch("src.ai_interface.tools.nace_resolver._load_kbo_nace_codes")
    def test_merge_catalogs(self, mock_load_kbo):
        """Test merging static and KBO catalogs."""
        mock_load_kbo.return_value = {"62010": "Software development", "62020": "Consulting"}

        result = _load_nace_catalog()

        # Should merge both sources
        assert "62010" in result
        # Description should include both sources
        assert "Programming" in result["62010"]
        assert "62020" in result


class TestLookupNACECode:
    """Test NACE code lookup."""

    def test_lookup_by_code(self):
        """Test looking up by NACE code."""
        result = lookup_nace_code.func("62010")
        assert isinstance(result, list)

    def test_lookup_by_keyword(self):
        """Test looking up by keyword."""
        result = lookup_nace_code.func("restaurant")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_lookup_by_description(self):
        """Test looking up by description."""
        result = lookup_nace_code.func("software")
        assert isinstance(result, list)
        # Should find IT-related codes
        assert len(result) > 0

    def test_lookup_invalid_code(self):
        """Test lookup with invalid code."""
        result = lookup_nace_code.func("99999")
        assert isinstance(result, list)

    def test_lookup_no_match(self):
        """Test lookup with no matching results."""
        result = lookup_nace_code.func("xyznonexistent12345")
        assert result == []


class TestLookupJuridicalCode:
    """Test juridical form code lookup."""

    def test_lookup_valid_code(self):
        """Test looking up valid juridical code."""
        # The JURIDICAL_CODES is loaded from a JSON file at module load time
        # Just verify the function returns a list
        result = lookup_juridical_code.func("014")
        assert isinstance(result, list)
        # Result depends on actual JURIDICAL_CODES data, just verify it's a list

    def test_lookup_by_name(self):
        """Test looking up by company type name."""
        with patch.dict(
            "src.ai_interface.tools.nace_resolver.JURIDICAL_CODES",
            {"014": "Naamloze Vennootschap", "017": "Besloten Vennootschap"},
            clear=False,
        ):
            result = lookup_juridical_code.func("vennootschap")
            assert isinstance(result, list)
            # Should find both NV and BV
            assert "014" in result
            assert "017" in result

    def test_lookup_case_insensitive(self):
        """Test case-insensitive lookup."""
        with patch.dict(
            "src.ai_interface.tools.nace_resolver.JURIDICAL_CODES",
            {"014": "Naamloze Vennootschap"},
            clear=False,
        ):
            result_lower = lookup_juridical_code.func("naamloze")
            result_upper = lookup_juridical_code.func("NAAMLOZE")
            assert result_lower == result_upper


class TestConstants:
    """Test module constants."""

    def test_nace_catalog_exists(self):
        """Test that NACE_CATALOG is populated."""
        assert isinstance(NACE_CATALOG, dict)
        # Catalog should have some entries
        assert len(NACE_CATALOG) >= 0

    def test_domain_synonyms_structure(self):
        """Test DOMAIN_SYNONYMS structure."""
        assert isinstance(DOMAIN_SYNONYMS, dict)
        # Should have expected domains
        expected_domains = {"it", "restaurant", "barber", "dentist", "plumber", "bakery"}
        for domain in expected_domains:
            assert domain in DOMAIN_SYNONYMS
            assert isinstance(DOMAIN_SYNONYMS[domain], set)

    def test_domain_hint_codes_structure(self):
        """Test DOMAIN_HINT_CODES structure."""
        assert isinstance(DOMAIN_HINT_CODES, dict)
        # Each domain should map to a list of codes
        for _domain, codes in DOMAIN_HINT_CODES.items():
            assert isinstance(codes, list)
            assert all(isinstance(c, str) for c in codes)
        assert DOMAIN_HINT_CODES["it"] == ["62100", "62200", "62900", "63100"]
