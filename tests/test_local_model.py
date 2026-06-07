"""Tests for LocalModelBackend Protocol and FakeLocalModelBackend."""

import json

import pytest


class TestFakeLocalModelBackend:
    """Tests for the FakeLocalModelBackend used in all automated tests."""

    def test_fake_backend_returns_canned_batch(self) -> None:
        """FakeLocalModelBackend returns the configured canned response."""
        import asyncio

        from forgerwrite_mcp.local_model import FakeLocalModelBackend

        canned = json.dumps({"batch_id": "test", "operations": []})
        backend = FakeLocalModelBackend(canned_response=canned)

        result = asyncio.run(
            backend.generate_operation_batch(
                system_prompt="sys",
                user_prompt="usr",
                schema={"type": "object"},
            )
        )
        assert result == canned

    def test_fake_backend_default_response_is_valid_batch(self) -> None:
        """Default canned response is a minimal valid operation batch."""
        import asyncio

        from forgerwrite_mcp.local_model import FakeLocalModelBackend

        backend = FakeLocalModelBackend()
        result = asyncio.run(
            backend.generate_operation_batch(system_prompt="sys", user_prompt="usr", schema={})
        )
        parsed = json.loads(result)
        assert "operations" in parsed
        assert len(parsed["operations"]) == 1
        assert parsed["operations"][0]["op"] == "create_file"

    def test_fake_backend_simulates_retry_with_invalid_json_on_first_attempt(
        self,
    ) -> None:
        """FakeLocalModelBackend can simulate failures before returning valid JSON."""
        import asyncio

        from forgerwrite_mcp.local_model import FakeLocalModelBackend

        backend = FakeLocalModelBackend(
            canned_response='{"valid": true}',
            failure_simulations=["invalid_json"],
        )
        # First call returns invalid JSON (simulated failure)
        result1 = asyncio.run(backend.generate_operation_batch("sys", "usr", {}))
        assert result1 == "NOT VALID JSON {{{"
        # Second call returns the canned response
        result2 = asyncio.run(backend.generate_operation_batch("sys", "usr", {}))
        assert result2 == '{"valid": true}'

    def test_fake_backend_simulates_network_failure(self) -> None:
        """FakeLocalModelBackend can simulate network errors."""
        import asyncio

        from forgerwrite_mcp.errors import LOCAL_MODEL_ERROR, PublicError
        from forgerwrite_mcp.local_model import FakeLocalModelBackend

        backend = FakeLocalModelBackend(
            failure_simulations=["network_error"],
        )
        with pytest.raises(PublicError) as exc_info:
            asyncio.run(backend.generate_operation_batch("sys", "usr", {}))
        assert exc_info.value.code == LOCAL_MODEL_ERROR

    def test_fake_backend_records_all_attempts(self) -> None:
        """Every generate_operation_batch call is recorded."""
        import asyncio

        from forgerwrite_mcp.local_model import FakeLocalModelBackend

        backend = FakeLocalModelBackend(
            canned_response='{"x": 1}',
            failure_simulations=["invalid_json", "invalid_json"],
        )
        # 2 failures + 1 success = 3 attempts
        import contextlib

        for _ in range(3):
            with contextlib.suppress(Exception):
                asyncio.run(backend.generate_operation_batch("sys", "usr", {}))
        assert len(backend.attempt_log) == 3
        assert backend.attempt_log[0]["status"] == "failure"
        assert backend.attempt_log[2]["status"] == "success"

    def test_fake_backend_is_async_iterable(self) -> None:
        """FakeLocalModelBackend implements the LocalModelBackend Protocol."""
        from forgerwrite_mcp.local_model import FakeLocalModelBackend, LocalModelBackend

        backend = FakeLocalModelBackend()
        # Verify it structurally matches the Protocol
        assert isinstance(backend, LocalModelBackend)


class TestLocalModelBackendProtocol:
    """Tests that the Protocol is correctly structured."""

    def test_protocol_requires_generate_operation_batch(self) -> None:
        """LocalModelBackend Protocol requires generate_operation_batch method."""
        from forgerwrite_mcp.local_model import LocalModelBackend

        # Protocol attributes: the method signature
        assert hasattr(LocalModelBackend, "generate_operation_batch")

    def test_fake_backend_can_be_used_where_protocol_expected(self) -> None:
        """FakeLocalModelBackend satisfies LocalModelBackend Protocol."""
        from forgerwrite_mcp.local_model import FakeLocalModelBackend, LocalModelBackend

        def accepts_backend(b: LocalModelBackend) -> None:
            pass  # Type checker verifies this

        accepts_backend(FakeLocalModelBackend())
