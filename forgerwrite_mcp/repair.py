"""Repair coordinator — bounded repair loop for failed validation.

Design reference: §5.12

When validation fails, the repair coordinator:
1. Builds a targeted feedback prompt including the validation errors
2. Re-invokes the local model to generate a fix
3. Re-validates the new operations
4. Re-previews the diff
5. Loops up to repair.max_attempts times
"""

from __future__ import annotations

from typing import Any

from .config import RepairConfig
from .errors import REPAIR_ERROR, PublicError


class RepairError(PublicError):
    """Repair loop exhausted or failed."""

    def __init__(self, message: str) -> None:
        super().__init__(code=REPAIR_ERROR, message=message)


class RepairCoordinator:
    """Manages the bounded repair loop.

    Instantiated by SliceCoordinator when validation fails. Tracks
    attempts and enforces config limits.

    Usage:
        repair = RepairCoordinator(config=...)
        while True:
            result = repair.attempt(validation_result, slice_contract)
            if result is None:
                break  # budget exhausted
            prompt, remaining = result
            # Call model with prompt, validate, apply...
    """

    def __init__(self, *, config: RepairConfig | None = None) -> None:
        self._cfg: RepairConfig = config or RepairConfig()
        self._max_attempts: int = self._cfg.max_attempts
        self._attempt_count: int = 0
        self._scope_must_match: bool = self._cfg.scope_must_match_original_slice

    @property
    def attempt_count(self) -> int:
        """Number of attempts used so far."""
        return self._attempt_count

    @property
    def budget_remaining(self) -> int:
        """Remaining repair attempts."""
        return max(0, self._max_attempts - self._attempt_count)

    def attempt(
        self,
        validation_result: dict[str, Any],
        slice_contract: dict[str, Any],
    ) -> tuple[str, int] | None:
        """Run one repair attempt. Returns (prompt, budget_remaining) or None.

        Args:
            validation_result: The failed validation result dict.
            slice_contract: The original slice contract for scope enforcement.

        Returns:
            Tuple of (repair_prompt, budget_remaining) if budget remains,
            or None if the repair budget is exhausted.
        """
        if self._attempt_count >= self._max_attempts:
            return None

        self._attempt_count += 1
        repair_prompt = self._build_repair_prompt(validation_result)
        return (repair_prompt, self.budget_remaining)

    def _build_repair_prompt(self, validation_result: dict[str, Any]) -> str:
        """Build a repair prompt that includes the validation failure details."""
        errors: list[str] = []
        for cmd in validation_result.get("commands", []):
            if not cmd.get("passed", False):
                err_text = cmd.get("stderr_head", "") or cmd.get("stdout_head", "")
                errors.append(
                    f"Command '{cmd.get('command_id', 'unknown')}' failed "
                    f"(returncode {cmd.get('returncode', '?')}):\n{err_text[:2000]}"
                )
        return (
            "The following validation errors were detected. Please fix the code "
            "and produce a corrected operation batch.\n\n" + "\n".join(errors)
        )
