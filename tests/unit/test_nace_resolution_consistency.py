"""Regression tests for NACE code resolution consistency.

These tests verify that industry keyword resolution produces consistent,
predictable NACE code sets to prevent planner/tool argument mismatches.
"""

import pytest

from src.ai_interface.tools.nace_resolver import _get_nace_codes_from_keyword


class TestNaceResolutionConsistency:
    """Verify NACE resolution produces consistent code sets."""

    def test_software_resolves_to_verified_current_it_codes(self):
        """Software should resolve to the verified current IT-services code set.

        Regression: Earlier iterations used 62010/62020/62030/62090/63110/63120,
        but direct Brussels dataset verification showed those codes do not exist in
        the current local KBO slice used for the demo. The authoritative current
        mapping is the 4-code IT-services set backed by live PostgreSQL checks.
        """
        codes = _get_nace_codes_from_keyword("software")
        assert set(codes) == {"62100", "62200", "62900", "63100"}
        assert len(codes) == 4

    def test_software_development_same_as_software(self):
        """Software development should resolve to same codes as software."""
        software_codes = _get_nace_codes_from_keyword("software")
        dev_codes = _get_nace_codes_from_keyword("software development")
        assert software_codes == dev_codes

    def test_it_domain_includes_all_software_codes(self):
        """All IT-related keywords should resolve to consistent code sets."""
        it_keywords = ["it", "software", "computer", "ICT", "technology"]
        all_sets = [_get_nace_codes_from_keyword(kw) for kw in it_keywords]

        # All should resolve to the same verified 4-code set
        expected = {"62100", "62200", "62900", "63100"}
        for keyword, codes in zip(it_keywords, all_sets):
            assert set(codes) == expected, f"Keyword '{keyword}' resolved to different codes"

    def test_current_it_codes_cover_programming_consultancy_and_info_services(self):
        """The current mapping spans programming, consultancy, and information services."""
        all_codes = set(_get_nace_codes_from_keyword("software"))
        expected = {"62100", "62200", "62900", "63100"}

        assert all_codes == expected


class TestNaceCodeDocumentation:
    """Document NACE code meanings for reference."""

    def test_document_verified_current_it_services_set(self):
        """Document the verified current IT-services code set.

        62100: Computer programming activities
        62200: Computer consultancy activities
        62900: Other information technology and computer service activities
        63100: Data processing, hosting and related activities; web portals

        Direct local PostgreSQL verification on 2026-03-08 showed Brussels counts
        for 62100/62200/62900/63100 and zero rows for 62010/62020/62030/62090/
        63110/63120 in the current dataset slice used for the demo.
        """
        codes = _get_nace_codes_from_keyword("software")

        codes_62xxx = [c for c in codes if c.startswith("62")]
        codes_63100 = [c for c in codes if c == "63100"]

        assert len(codes_62xxx) == 3
        assert len(codes_63100) == 1
        assert set(codes_62xxx + codes_63100) == set(codes)
