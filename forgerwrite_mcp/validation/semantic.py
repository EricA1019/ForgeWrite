"""Semantic validator — pluggable rule-based validation of operation batches.

Design reference: §5.4 (semantic checks)

Rules are registered via register() — Open/Closed: new rules added without
editing the validator.
"""

from __future__ import annotations

import fnmatch
from typing import Any, Protocol

from ..config import LimitsConfig, PermissionsConfig
from ..errors import PublicError

_SEMANTIC_ERROR_CODE: str = "SEMANTIC_VALIDATION_ERROR"


class SemanticValidationError(PublicError):
    """An operation batch failed semantic validation."""

    def __init__(self, message: str) -> None:
        super().__init__(code=_SEMANTIC_ERROR_CODE, message=message)


class SemanticRule(Protocol):
    """Protocol for semantic validation rules.

    Each rule checks one aspect of the operation batch.
    Returns a list of error messages (empty = pass).
    """

    def check(
        self,
        operation_batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig,
        permissions: PermissionsConfig,
    ) -> list[str]: ...


# ── Built-in rules ──────────────────────────────────────────────────────────


class ScopeRule:
    """Reject operations targeting files outside allowed_files or in forbidden_files."""

    def check(
        self,
        batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig,
        permissions: PermissionsConfig,
    ) -> list[str]:
        allowed = set(slice_contract.get("allowed_files", []))
        forbidden = set(slice_contract.get("forbidden_files", []))
        errors: list[str] = []
        for op in batch.get("operations", []):
            path = op.get("path", "")
            if path not in allowed:
                errors.append(f"Operation targets '{path}' outside allowed_files")
            if path in forbidden:
                errors.append(f"Operation targets forbidden file: '{path}'")
        return errors


class SizeRule:
    """Reject batches exceeding the max operation count."""

    def __init__(self, max_operations: int = 32) -> None:
        self._max: int = max_operations

    def check(
        self,
        batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig,
        permissions: PermissionsConfig,
    ) -> list[str]:
        ops = batch.get("operations", [])
        if len(ops) > self._max:
            return [f"Batch has {len(ops)} operations, exceeds max {self._max}"]
        return []


class ForbiddenTargetRule:
    """Reject operations targeting files matching forbidden globs."""

    def __init__(self, forbidden_globs: list[str] | None = None) -> None:
        self._globs: list[str] = forbidden_globs or []

    def check(
        self,
        batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig,
        permissions: PermissionsConfig,
    ) -> list[str]:
        errors: list[str] = []
        for op in batch.get("operations", []):
            path = op.get("path", "")
            for glob in self._globs:
                if fnmatch.fnmatch(path, glob):
                    errors.append(f"Operation targets forbidden glob '{glob}': '{path}'")
        return errors


class GeneratedPathRule:
    """Reject operations targeting generated/build paths."""

    def __init__(self, globs: list[str] | None = None) -> None:
        self._globs: list[str] = globs or ["target/**"]

    def check(
        self,
        batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig,
        permissions: PermissionsConfig,
    ) -> list[str]:
        errors: list[str] = []
        for op in batch.get("operations", []):
            path = op.get("path", "")
            for glob in self._globs:
                if fnmatch.fnmatch(path, glob):
                    errors.append(f"Operation targets generated path '{glob}': '{path}'")
        return errors


class PermissionRule:
    """Enforce permission flags from config.

    The `permissions` parameter from config is the source of truth.
    Constructor args are preserved for backward compatibility but
    the `check()` method reads from the `permissions` config, not
    from instance state.
    """

    def __init__(
        self,
        require_approval_for_delete: bool = True,
        require_approval_for_full_file_replace: bool = True,
    ) -> None:
        # Preserved for backward compatibility; check() reads from permissions config.
        self._delete: bool = require_approval_for_delete
        self._full_replace: bool = require_approval_for_full_file_replace

    def check(
        self,
        batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig,
        permissions: PermissionsConfig,
    ) -> list[str]:
        errors: list[str] = []
        for op in batch.get("operations", []):
            if op.get("op") == "delete_file" and permissions.require_approval_for_delete:
                errors.append(f"Delete operation requires approval: '{op.get('path')}'")
            if op.get("op") == "replace_file" and (
                permissions.require_approval_for_full_file_replace
            ):
                errors.append(
                    f"Full file replace requires approval: '{op.get('path')}'"
                )
        return errors


class LineOverlapRule:
    """Reject batches with multiple line-based operations on the same file.

    Sequential line operations on the same file cause shifted line numbers
    because each operation mutates the file before the next runs. Split
    line-based edits to the same file into separate batches.
    """

    _LINE_OPS = frozenset({
        "insert_before_line", "insert_after_line", "replace_line_range",
    })

    def check(
        self,
        batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig,
        permissions: PermissionsConfig,
    ) -> list[str]:
        errors: list[str] = []
        seen: dict[str, str] = {}  # path -> first line-op type

        for op in batch.get("operations", []):
            if op.get("op") not in self._LINE_OPS:
                continue
            path = op.get("path", "")
            if path in seen:
                errors.append(
                    f"Multiple line-based operations on '{path}': "
                    f"{seen[path]} and {op['op']}. Split into separate batches "
                    f"to avoid line-number shift."
                )
            else:
                seen[path] = op["op"]
        return errors


# ── Validator ───────────────────────────────────────────────────────────────


class SemanticValidator:
    """Pluggable semantic validator for operation batches.

    Rules are registered via register(). validate() runs all rules and
    aggregates errors.
    """

    def __init__(self) -> None:
        self._rules: list[SemanticRule] = []

    def register(self, rule: SemanticRule) -> None:
        """Register a semantic validation rule."""
        self._rules.append(rule)

    def validate(
        self,
        operation_batch: dict[str, Any],
        slice_contract: dict[str, Any],
        limits: LimitsConfig | None = None,
        permissions: PermissionsConfig | None = None,
    ) -> None:
        """Run all registered rules. Raises SemanticValidationError on failure."""
        if limits is None:
            limits = LimitsConfig()
        if permissions is None:
            permissions = PermissionsConfig()

        all_errors: list[str] = []
        for rule in self._rules:
            all_errors.extend(rule.check(operation_batch, slice_contract, limits, permissions))
        if all_errors:
            raise SemanticValidationError("\n".join(all_errors))


def default_validator() -> SemanticValidator:
    """Build a SemanticValidator with all built-in rules."""
    v = SemanticValidator()
    v.register(ScopeRule())
    v.register(SizeRule())
    v.register(LineOverlapRule())
    v.register(GeneratedPathRule())
    v.register(
        PermissionRule(
            require_approval_for_delete=True,
            require_approval_for_full_file_replace=True,
        )
    )
    return v
