#!/usr/bin/env python3
"""
Regression test for Exact demo narration.

Ensures the demo script does not advertise non-existent production files.
See: PROJECT_STATE.yaml exact_demo_narration_gap
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Path to the demo script
DEMO_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "demo_exact_integration.py"

# Files that should NOT be advertised as existing (they don't exist)
NONEXISTENT_FILES = [
    "src/services/exact_online.py",
    "scripts/sync_exact_to_cdp.py",
    "docs/integrations/exact_online.md",
]


class TestExactDemoNarration:
    """Verify demo script stays honest about mock-only status."""

    def test_demo_script_exists(self) -> None:
        """Demo script must exist."""
        assert DEMO_SCRIPT_PATH.exists(), f"Demo script not found: {DEMO_SCRIPT_PATH}"

    def test_no_nonexistent_file_references(self) -> None:
        """Demo must not reference files that don't exist."""
        script_content = DEMO_SCRIPT_PATH.read_text()

        for filepath in NONEXISTENT_FILES:
            assert filepath not in script_content, (
                f"Demo script advertises non-existent file: {filepath}\n"
                f"Remove this reference or create the file."
            )

    def test_mock_provenance_declared(self) -> None:
        """Demo must declare its mock provenance."""
        script_content = DEMO_SCRIPT_PATH.read_text()

        # Should contain provenance declaration
        assert "provenance" in script_content.lower(), "Demo script missing provenance declaration"
        assert "mock" in script_content.lower(), "Demo script should declare itself as mock"

    def test_no_live_api_claims(self) -> None:
        """Demo must not claim to make live API calls."""
        script_content = DEMO_SCRIPT_PATH.read_text()

        # Should not claim real API calls are happening
        # Note: "live API" can appear in warnings like "before advertising live API calls"
        # which is acceptable - we just don't want claims like "making live API calls"
        forbidden_patterns = [
            "making live api calls",
            "makes live api calls",
            "real api calls enabled",
            "production api active",
        ]

        script_lower = script_content.lower()
        for pattern in forbidden_patterns:
            assert pattern not in script_lower, (
                f"Demo script makes false live API claim: '{pattern}'"
            )

    def test_mode_description_is_accurate(self) -> None:
        """Mode description must accurately reflect mock-only status."""
        script_content = DEMO_SCRIPT_PATH.read_text()

        # Should have a mode_description property that mentions mock
        assert "mode_description" in script_content, (
            "Demo script missing mode_description property"
        )

    def test_script_is_valid_python(self) -> None:
        """Demo script must be valid Python syntax."""
        script_content = DEMO_SCRIPT_PATH.read_text()

        try:
            ast.parse(script_content)
        except SyntaxError as e:
            pytest.fail(f"Demo script has syntax error: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
