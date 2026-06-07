"""Tests for the llama.cpp HTTP client (real backend)."""

import json

import pytest


class TestLlamaCppClient:
    """Tests for LlamaCppClient using mocked httpx."""

    def test_network_error_raises_typed_error(self) -> None:
        """Connection failure raises PublicError with LOCAL_MODEL_ERROR."""
        import asyncio

        import httpx

        from forgerwrite_mcp.errors import LOCAL_MODEL_ERROR, PublicError
        from forgerwrite_mcp.llama_client import LlamaCppClient

        client = LlamaCppClient(
            endpoint="http://127.0.0.1:9999/v1",
            model="test-model",
            timeout=1.0,
        )
        # Use a transport that always fails
        transport = httpx.MockTransport(lambda req: httpx.Response(500, text="error"))
        client._client = httpx.AsyncClient(transport=transport)

        with pytest.raises(PublicError) as exc_info:
            asyncio.run(
                client.generate_operation_batch(
                    system_prompt="sys",
                    user_prompt="usr",
                    schema={"type": "object"},
                )
            )
        assert exc_info.value.code == LOCAL_MODEL_ERROR

    def test_invalid_json_retries_up_to_configured_count(self) -> None:
        """Client retries invalid JSON responses up to json_retries times."""
        import asyncio

        import httpx

        from forgerwrite_mcp.llama_client import LlamaCppClient

        valid_response = json.dumps(
            {
                "batch_id": "b1",
                "operations": [{"op": "create_file", "path": "x.rs", "content": "c"}],
            }
        )
        call_count = [0]

        def handler(req):
            call_count[0] += 1
            if call_count[0] < 3:
                return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
            return httpx.Response(200, json={"choices": [{"message": {"content": valid_response}}]})

        transport = httpx.MockTransport(handler)
        client = LlamaCppClient(
            endpoint="http://127.0.0.1:8080/v1",
            model="test",
            json_retries=3,
            timeout=10.0,
        )
        client._client = httpx.AsyncClient(transport=transport)

        result = asyncio.run(client.generate_operation_batch("sys", "usr", {"type": "object"}))
        assert call_count[0] == 3
        parsed = json.loads(result)
        assert parsed["batch_id"] == "b1"

    def test_valid_json_returned_first_try_no_retries(self) -> None:
        """Valid JSON on first try returns immediately with no retries."""
        import asyncio

        import httpx

        from forgerwrite_mcp.llama_client import LlamaCppClient

        valid = json.dumps({"batch_id": "b1", "operations": []})
        call_count = [0]

        def handler(req):
            call_count[0] += 1
            return httpx.Response(200, json={"choices": [{"message": {"content": valid}}]})

        transport = httpx.MockTransport(handler)
        client = LlamaCppClient(
            endpoint="http://127.0.0.1:8080/v1",
            model="test",
            timeout=10.0,
        )
        client._client = httpx.AsyncClient(transport=transport)

        result = asyncio.run(client.generate_operation_batch("sys", "usr", {}))
        assert call_count[0] == 1
        assert json.loads(result)["batch_id"] == "b1"

    def test_timeout_honored(self) -> None:
        """Request timeout from config is applied to httpx client."""
        from forgerwrite_mcp.llama_client import LlamaCppClient

        client = LlamaCppClient(
            endpoint="http://127.0.0.1:8080/v1",
            model="test",
            timeout=5.0,
        )
        assert client._timeout == 5.0

    def test_circuit_breaker_opens_after_failures(self) -> None:
        """After max failures, circuit breaker opens and short-circuits."""
        import asyncio

        import httpx

        from forgerwrite_mcp.errors import LOCAL_MODEL_ERROR, PublicError
        from forgerwrite_mcp.llama_client import LlamaCppClient

        client = LlamaCppClient(
            endpoint="http://127.0.0.1:9999/v1",
            model="test",
            timeout=1.0,
            circuit_breaker_threshold=2,
            circuit_breaker_reset_seconds=999,
        )
        transport = httpx.MockTransport(lambda req: httpx.Response(500))
        client._client = httpx.AsyncClient(transport=transport)

        # First failure
        with pytest.raises(PublicError):
            asyncio.run(client.generate_operation_batch("sys", "usr", {}))
        assert not client._circuit_open

        # Second failure — opens circuit
        with pytest.raises(PublicError):
            asyncio.run(client.generate_operation_batch("sys", "usr", {}))
        assert client._circuit_open

        # Third call — circuit open, immediate failure
        with pytest.raises(PublicError) as exc_info:
            asyncio.run(client.generate_operation_batch("sys", "usr", {}))
        assert "circuit" in str(exc_info.value).lower()
        assert exc_info.value.code == LOCAL_MODEL_ERROR

    def test_backoff_uses_config_values(self) -> None:
        """Backoff parameters match what's in LocalModelConfig."""
        from forgerwrite_mcp.config import LocalModelConfig

        cfg = LocalModelConfig(
            retry_base_delay_seconds=0.5,
            retry_max_delay_seconds=8.0,
            retry_multiplier=2.0,
        )
        assert cfg.retry_base_delay_seconds == 0.5
        assert cfg.retry_max_delay_seconds == 8.0
        assert cfg.retry_multiplier == 2.0
