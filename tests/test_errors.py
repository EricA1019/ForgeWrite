"""Tests for the error envelope and PublicError shared module."""


class TestPublicError:
    """Tests for PublicError exception class."""

    def test_public_error_has_code_message_hint(self) -> None:
        """PublicError stores code, message, and optional hint."""
        from forgerwrite_mcp.errors import PublicError

        err = PublicError(code="TEST_CODE", message="Something went wrong")
        assert err.code == "TEST_CODE"
        assert err.message == "Something went wrong"
        assert err.hint is None

    def test_public_error_with_hint(self) -> None:
        """PublicError accepts an optional hint string."""
        from forgerwrite_mcp.errors import PublicError

        err = PublicError(
            code="TEST_CODE",
            message="Error message",
            hint="Try checking the config file.",
        )
        assert err.hint == "Try checking the config file."

    def test_public_error_is_exception(self) -> None:
        """PublicError is a proper Exception subclass."""
        from forgerwrite_mcp.errors import PublicError

        err = PublicError(code="E", message="m")
        assert isinstance(err, Exception)

    def test_public_error_str_returns_message(self) -> None:
        """str(PublicError) returns the message for logging compatibility."""
        from forgerwrite_mcp.errors import PublicError

        err = PublicError(code="E", message="my message")
        assert str(err) == "my message"


class TestErrorEnvelope:
    """Tests for ErrorEnvelope dataclass."""

    def test_error_envelope_to_dict_has_ok_false(self) -> None:
        """to_dict() produces the standard error envelope format."""
        from forgerwrite_mcp.errors import ErrorEnvelope

        env = ErrorEnvelope(
            code="CONFIG_ERROR",
            message="Invalid config",
            correlation_id="abc-123",
            hint="Check forgerwrite.toml",
        )
        d = env.to_dict()
        assert d["ok"] is False
        assert d["error"]["code"] == "CONFIG_ERROR"
        assert d["error"]["message"] == "Invalid config"
        assert d["error"]["correlation_id"] == "abc-123"
        assert d["error"]["hint"] == "Check forgerwrite.toml"

    def test_error_envelope_hint_is_optional(self) -> None:
        """hint field is omitted from dict when None."""
        from forgerwrite_mcp.errors import ErrorEnvelope

        env = ErrorEnvelope(code="TEST", message="msg", correlation_id="cid", hint=None)
        d = env.to_dict()
        assert d["error"]["hint"] is None

    def test_error_envelope_correlation_id_is_always_set(self) -> None:
        """Every envelope gets a correlation_id."""
        from forgerwrite_mcp.errors import ErrorEnvelope

        env = ErrorEnvelope(code="X", message="y")
        assert env.correlation_id
        assert len(env.correlation_id) > 0


class TestEnvelopeFrom:
    """Tests for envelope_from() factory function."""

    def test_envelope_from_public_error_preserves_code(self) -> None:
        """PublicError code is forwarded to the envelope."""
        from forgerwrite_mcp.errors import PublicError, envelope_from

        exc = PublicError(code="PATH_SAFETY_ERROR", message="Traversal detected")
        env = envelope_from(exc, correlation_id="run_001")
        assert env.code == "PATH_SAFETY_ERROR"
        assert env.message == "Traversal detected"

    def test_envelope_from_public_error_preserves_hint(self) -> None:
        """PublicError hint is forwarded."""
        from forgerwrite_mcp.errors import PublicError, envelope_from

        exc = PublicError(code="E", message="m", hint="h")
        env = envelope_from(exc, correlation_id="cid")
        assert env.hint == "h"

    def test_envelope_from_unknown_exception_returns_internal_error(self) -> None:
        """Non-PublicError exceptions become INTERNAL_ERROR with sanitized message."""
        from forgerwrite_mcp.errors import (
            INTERNAL_ERROR,
            envelope_from,
        )

        exc = ValueError("raw internal detail with /path/to/file.py:42")
        env = envelope_from(exc, correlation_id="run_002")
        assert env.code == INTERNAL_ERROR
        # Must NOT leak raw exception message
        assert "raw internal detail" not in env.message
        assert "/path/to/file.py" not in env.message
        # Must NOT leak exception class name
        assert "ValueError" not in env.message

    def test_envelope_from_no_class_names_leak(self) -> None:
        """Envelope from any exception must never contain __class__.__name__."""
        from forgerwrite_mcp.errors import envelope_from

        class MyCustomInternalError(RuntimeError):
            pass

        exc = MyCustomInternalError("secret details")
        env = envelope_from(exc, correlation_id="cid")
        assert "MyCustomInternalError" not in env.message
        assert "RuntimeError" not in env.message
        assert "secret details" not in env.message


class TestErrorCodeConstants:
    """Tests that all standard error codes are defined as module constants."""

    def test_all_standard_error_codes_defined(self) -> None:
        """Verify the 9 standard error codes exist."""
        from forgerwrite_mcp import errors

        expected = [
            "PATH_SAFETY_ERROR",
            "CONTRACT_VALIDATION_ERROR",
            "CONFIG_ERROR",
            "APPROVAL_ERROR",
            "OPERATION_APPLY_ERROR",
            "VALIDATION_ERROR",
            "LOCAL_MODEL_ERROR",
            "REPAIR_ERROR",
            "INTERNAL_ERROR",
        ]
        for code in expected:
            assert hasattr(errors, code), f"Missing error code constant: {code}"
            assert isinstance(getattr(errors, code), str)
