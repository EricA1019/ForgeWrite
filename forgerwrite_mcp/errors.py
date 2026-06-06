"""Shared error types for ForgerWrite MCP.

Every module raises errors through PublicError subclasses. The MCP server
and CLI both use ErrorEnvelope to produce safe, sanitized error responses.

Design rule (§9.1, §5.10): no exception class names or raw exception
messages ever leak to external consumers.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

# ── Standard error code constants ───────────────────────────────────────────
# Every module uses these named constants — no raw strings in raise statements.

PATH_SAFETY_ERROR: str = "PATH_SAFETY_ERROR"
CONTRACT_VALIDATION_ERROR: str = "CONTRACT_VALIDATION_ERROR"
CONFIG_ERROR: str = "CONFIG_ERROR"
APPROVAL_ERROR: str = "APPROVAL_ERROR"
OPERATION_APPLY_ERROR: str = "OPERATION_APPLY_ERROR"
VALIDATION_ERROR: str = "VALIDATION_ERROR"
LOCAL_MODEL_ERROR: str = "LOCAL_MODEL_ERROR"
REPAIR_ERROR: str = "REPAIR_ERROR"
INTERNAL_ERROR: str = "INTERNAL_ERROR"

# ── Public error base class ─────────────────────────────────────────────────


class PublicError(Exception):
    """Exception with a machine-readable code and optional user hint.

    Raised by library modules. Never subclasses anything except Exception.
    The code maps to the error envelope's public error code.
    """

    def __init__(self, *, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code: str = code
        self.message: str = message
        self.hint: str | None = hint


# ── Error envelope for external consumers ───────────────────────────────────

# Sanitized message used when wrapping unknown internal exceptions.
_SANITIZED_INTERNAL_MESSAGE: str = "An internal error occurred. See run artifacts for details."
_SANITIZED_INTERNAL_HINT: str = "Inspect .forgerwrite/runs/<run_id>/run.json and logs."


@dataclass(frozen=True)
class ErrorEnvelope:
    """Safe, structured error response for MCP tools and CLI output.

    Never contains raw exception messages or class names. The correlation_id
    links the error to a specific run for debugging.
    """

    code: str
    message: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Produce the standard error envelope dict.

        Format: {"ok": false, "error": {"code": ..., "message": ...,
        "correlation_id": ..., "hint": ...}}
        """
        d = asdict(self)
        return {"ok": False, "error": d}


def envelope_from(exc: Exception, correlation_id: str) -> ErrorEnvelope:
    """Map any exception to a safe ErrorEnvelope.

    - PublicError: code, message, and hint are forwarded directly.
    - Any other exception: wrapped as INTERNAL_ERROR with a sanitized
      message. Class names and raw exception text are never leaked.
    """
    if isinstance(exc, PublicError):
        return ErrorEnvelope(
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            hint=exc.hint,
        )
    # Unknown internal exception — sanitize
    return ErrorEnvelope(
        code=INTERNAL_ERROR,
        message=_SANITIZED_INTERNAL_MESSAGE,
        correlation_id=correlation_id,
        hint=_SANITIZED_INTERNAL_HINT,
    )
