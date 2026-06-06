"""Operation Registry — pluggable dispatch for file operations.

New operation types are added by registering a handler — no switch statement.
This is the Open/Closed enforcement point for operations.

Design reference: §5.5, ADR-003
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..errors import OPERATION_APPLY_ERROR, PublicError


class OperationHandler(Protocol):
    """Protocol for operation handlers.

    Each handler validates and applies one operation type.
    """

    op_name: str

    def validate(
        self, operation: dict[str, Any], slice_contract: dict[str, Any], limits: Any
    ) -> None:
        """Validate the operation before apply. Raises on failure."""
        ...

    def apply(self, repo_root: Path, operation: dict[str, Any]) -> ApplyOutcome:
        """Apply the operation to the repository. Returns outcome."""
        ...


@dataclass(frozen=True)
class ApplyOutcome:
    """Result of applying a single operation."""

    path: str
    bytes_written: int
    created: bool = False
    deleted: bool = False


class OperationApplyError(PublicError):
    """An operation failed to validate or apply."""

    def __init__(self, message: str) -> None:
        super().__init__(code=OPERATION_APPLY_ERROR, message=message)


class OperationRegistry:
    """Registry of OperationHandler instances, keyed by op_name."""

    def __init__(self) -> None:
        self._handlers: dict[str, OperationHandler] = {}

    def register(self, handler: OperationHandler) -> None:
        """Register an operation handler. Overwrites existing handler for the same op_name."""
        self._handlers[handler.op_name] = handler

    def dispatch(self, operation: dict[str, Any]) -> OperationHandler:
        """Find the handler for the given operation dict.

        Args:
            operation: Must have an 'op' key with the operation name.

        Returns:
            The registered handler.

        Raises:
            OperationApplyError: If no handler is registered for this op.
        """
        op_name = operation.get("op")
        if not op_name or op_name not in self._handlers:
            raise OperationApplyError(f"Unknown operation: {op_name}")
        return self._handlers[op_name]


def default_registry() -> OperationRegistry:
    """Build the default registry with all 6 MVP operation handlers."""
    from .create_file import CreateFileHandler
    from .delete_file import DeleteFileHandler
    from .insert_after_line import InsertAfterLineHandler
    from .insert_before_line import InsertBeforeLineHandler
    from .replace_file import ReplaceFileHandler
    from .replace_line_range import ReplaceLineRangeHandler

    reg = OperationRegistry()
    reg.register(CreateFileHandler())
    reg.register(ReplaceFileHandler())
    reg.register(ReplaceLineRangeHandler())
    reg.register(InsertAfterLineHandler())
    reg.register(InsertBeforeLineHandler())
    reg.register(DeleteFileHandler())
    return reg
