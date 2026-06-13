"""llama.cpp HTTP client — real backend implementing LocalModelBackend.

Design reference: §5.9, ADR-002

Calls llama.cpp's OpenAI-compatible /v1/chat/completions endpoint with
JSON schema constraint. Implements retry with exponential backoff and
a circuit breaker.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from .config import LocalModelConfig
from .errors import LOCAL_MODEL_ERROR, PublicError

# ── Circuit breaker constants ───────────────────────────────────────────────

_DEFAULT_CIRCUIT_BREAKER_THRESHOLD: int = 5
_DEFAULT_CIRCUIT_BREAKER_RESET_SECONDS: float = 30.0

# ── Generation defaults ────────────────────────────────────────────────────
# Gemma 4 recommended: temperature=1.0, top_p=0.95, top_k=64

_GENERATION_TEMPERATURE: float = 1.0
_GENERATION_TOP_P: float = 0.95
_GENERATION_TOP_K: int = 64
_GENERATION_MAX_TOKENS: int = 4096


class LlamaCppClient:
    """HTTP client for llama.cpp server implementing LocalModelBackend.

    Retries invalid JSON with exponential backoff. Opens a circuit breaker
    after consecutive failures to avoid hammering a broken server.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        timeout: float,
        max_tokens: int = 4096,
        json_retries: int = 2,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 8.0,
        retry_multiplier: float = 2.0,
        circuit_breaker_threshold: int = _DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        circuit_breaker_reset_seconds: float = _DEFAULT_CIRCUIT_BREAKER_RESET_SECONDS,
    ) -> None:
        self._endpoint: str = endpoint.rstrip("/")
        self._model: str = model
        self._timeout: float = timeout
        self._max_tokens: int = max_tokens
        self._json_retries: int = json_retries
        self._retry_base_delay: float = retry_base_delay
        self._retry_max_delay: float = retry_max_delay
        self._retry_multiplier: float = retry_multiplier
        self._circuit_threshold: int = circuit_breaker_threshold
        self._circuit_reset: float = circuit_breaker_reset_seconds

        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
        )
        self._circuit_open: bool = False
        self._consecutive_failures: int = 0
        self._circuit_opened_at: float = 0.0

    @classmethod
    def from_config(cls, config: LocalModelConfig) -> LlamaCppClient:
        """Create a client from a LocalModelConfig."""
        return cls(
            endpoint=config.endpoint,
            model=config.model,
            timeout=config.request_timeout_seconds,
            max_tokens=config.max_tokens,
            json_retries=config.json_retries,
            retry_base_delay=config.retry_base_delay_seconds,
            retry_max_delay=config.retry_max_delay_seconds,
            retry_multiplier=config.retry_multiplier,
        )

    async def generate_operation_batch(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> str:
        """Call llama.cpp and return a JSON operation batch string.

        Uses ``response_format: json_object`` to constrain the model to
        produce valid JSON, while relying on structured prompting (system
        prompt + RAG-enriched user prompt) for schema adherence. The
        ``schema`` parameter is accepted for API compatibility but not
        sent to the model — structural validation happens downstream via
        :class:`ContractRegistry`.

        Retries on invalid JSON up to json_retries times.
        Raises PublicError(LOCAL_MODEL_ERROR) on failure.
        """
        if self._circuit_open:
            if time.monotonic() - self._circuit_opened_at < self._circuit_reset:
                raise PublicError(
                    code=LOCAL_MODEL_ERROR,
                    message="Circuit breaker is open. Model calls are suspended.",
                    hint=(
                        "Wait for the circuit breaker to reset, or restart the local model server."
                    ),
                )
            # Reset circuit after timeout
            self._circuit_open = False
            self._consecutive_failures = 0

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": _GENERATION_TEMPERATURE,
            "top_p": _GENERATION_TOP_P,
            "top_k": _GENERATION_TOP_K,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }

        last_error: str = ""
        delay: float = self._retry_base_delay

        for attempt in range(self._json_retries + 1):
            try:
                response = await self._client.post(
                    f"{self._endpoint}/chat/completions",
                    json=payload,
                )
                if response.status_code != 200:
                    raise PublicError(
                        code=LOCAL_MODEL_ERROR,
                        message=f"llama.cpp returned HTTP {response.status_code}",
                        hint=f"Response: {response.text[:500]}",
                    )

                body = response.json()
                content = body.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Validate it's parseable JSON
                json.loads(content)
                self._consecutive_failures = 0
                return content

            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                last_error = str(exc)
                if attempt < self._json_retries:
                    await asyncio.sleep(delay)
                    delay = min(delay * self._retry_multiplier, self._retry_max_delay)
                # Fall through to next attempt

            except PublicError:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._circuit_threshold:
                    self._circuit_open = True
                    self._circuit_opened_at = time.monotonic()
                raise

            except Exception as exc:
                last_error = str(exc)
                if attempt < self._json_retries:
                    await asyncio.sleep(delay)
                    delay = min(delay * self._retry_multiplier, self._retry_max_delay)

        # All retries exhausted
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_threshold:
            self._circuit_open = True
            self._circuit_opened_at = time.monotonic()

        raise PublicError(
            code=LOCAL_MODEL_ERROR,
            message=f"Failed to get valid JSON after {self._json_retries + 1} attempts",
            hint=f"Last error: {last_error}. Check llama.cpp server logs.",
        )
