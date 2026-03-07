"""Regression tests for NACE code resolution consistency.

These tests verify that industry keyword resolution produces consistent,
predictable NACE code sets to prevent planner/tool argument mismatches.
"""

import pytest

from src.ai_interface.tools.nace_resolver import _get_nace_codes_from_keyword


class TestNaceResolutionConsistency:
    """Verify NACE resolution produces consistent code sets."""

    def test_software_resolves_to_all_six_codes(self):
        """Software should resolve to all 6 IT-related NACE codes.

        Regression: Earlier browser session returned 1529 results for
        'software companies in Brussels' because the planner only used
        the 4 62xxx codes (1529) instead of all 6 codes including 631xx.

        Expected: ['62010', '62020', '62030', '62090', '63110', '63120']
        """
        codes = _get_nace_codes_from_keyword("software")
        assert set(codes) == {"62010", "62020", "62030", "62090", "63110", "63120"}
        assert len(codes) == 6

    def test_software_development_same_as_software(self):
        """Software development should resolve to same codes as software."""
        software_codes = _get_nace_codes_from_keyword("software")
        dev_codes = _get_nace_codes_from_keyword("software development")
        assert software_codes == dev_codes

    def test_it_domain_includes_all_software_codes(self):
        """All IT-related keywords should resolve to consistent code sets."""
        it_keywords = ["it", "software", "computer", "ICT", "technology"]
        all_sets = [_get_nace_codes_from_keyword(kw) for kw in it_keywords]

        # All should resolve to the same 6 codes
        expected = {"62010", "62020", "62030", "62090", "63110", "63120"}
        for keyword, codes in zip(it_keywords, all_sets):
            assert set(codes) == expected, f"Keyword '{keyword}' resolved to different codes"

    def test_core_software_codes_subset(self):
        """The 4 core 62xxx codes are a proper subset of all IT codes.

        This documents the historical discrepancy where 1529 (62xxx only)
        vs 1652 (all 6 codes) results were observed for Brussels software
        companies depending on which NACE codes were used.
        """
        all_codes = set(_get_nace_codes_from_keyword("software"))
        core_62xxx = {"62010", "62020", "62030", "62090"}

        assert core_62xxx.issubset(all_codes)
        assert len(core_62xxx) == 4
        assert len(all_codes) == 6
        assert all_codes - core_62xxx == {"63110", "63120"}


class TestNaceCodeDocumentation:
    """Document NACE code meanings for reference."""

    def test_document_62xxx_vs_63xxx_distinction(self):
        """Document the distinction between 62xxx and 631xx codes.

        62xxx: Computer programming, consultancy and related activities
          - 62010: Computer programming activities
          - 62020: Computer consultancy activities
          - 62030: Computer facilities management activities
          - 62090: Other information technology and computer service activities

        631xx: Information service activities
          - 63110: Data processing, hosting and related activities
          - 63120: Web portals

        The 1529 vs 1652 discrepancy occurred because the planner only
        included the 62xxx codes, excluding web portals and data processing.
        """
        codes = _get_nace_codes_from_keyword("software")

        # Verify the structure we document is correct
        codes_62xxx = [c for c in codes if c.startswith("62")]
        codes_631xx = [c for c in codes if c.startswith("631")]

        assert len(codes_62xxx) == 4
        assert len(codes_631xx) == 2
        assert set(codes_62xxx + codes_631xx) == set(codes)
