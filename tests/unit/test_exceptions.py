"""Unit tests for the custom exception hierarchy."""

from __future__ import annotations

import pytest

from src.core.exceptions import (
    CDPError,
    ConfigurationError,
    FlexmailError,
    LLMError,
    QueryTimeoutError,
    TracardiError,
    ValidationError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_cdp_error(self):
        for exc_cls in [
            ConfigurationError,
            ValidationError,
            TracardiError,
            FlexmailError,
            LLMError,
            QueryTimeoutError,
        ]:
            assert issubclass(exc_cls, CDPError)

    def test_cdp_error_inherits_from_exception(self):
        assert issubclass(CDPError, Exception)

    def test_cdp_error_message_stored(self):
        err = CDPError("test message")
        assert err.message == "test message"
        assert str(err) == "test message"

    def test_cdp_error_context(self):
        err = CDPError("msg", context={"key": "value"})
        assert err.context == {"key": "value"}

    def test_cdp_error_default_context(self):
        err = CDPError("msg")
        assert err.context == {}

    def test_tracardi_error_status_code(self):
        err = TracardiError("Not found", status_code=404)
        assert err.status_code == 404
        assert isinstance(err, CDPError)

    def test_flexmail_error_status_code(self):
        err = FlexmailError("Server error", status_code=500)
        assert err.status_code == 500

    def test_validation_error_flags(self):
        err = ValidationError("Bad query", flags=["sql_injection"])
        assert "sql_injection" in err.flags

    def test_llm_error_provider(self):
        err = LLMError("Timeout", provider="openai")
        assert err.provider == "openai"

    def test_can_raise_and_catch_specific(self):
        with pytest.raises(TracardiError):
            raise TracardiError("Tracardi down")

    def test_can_catch_as_cdp_error(self):
        with pytest.raises(CDPError):
            raise FlexmailError("Flexmail down")
