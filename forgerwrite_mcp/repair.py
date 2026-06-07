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


class RepairOutcome:
    """Result of a repair attempt."""

    def __init__(
        self,
        success: bool = False,
        attempts_used: int = 0,
        new_operations: dict[str, Any] | None = None,
        message: str = "",
    ) -> None:
        self.success = success
        self.attempts_used = attempts_used
        self.new_operations = new_operations or {}
        self.message = message


class RepairCoordinator:
    """Manages the bounded repair loop.

    Instantiated by SliceCoordinator when validation fails. Tracks
    attempts and enforces config limits.
    """

    def __init__(self, *, config: RepairConfig | None = None) -> None:
        self._config: RepairConfig = config or RepairConfig()
        self._max_attempts: int = self._config.max_attempts
        self._attempt_count: int = 0
        self._scope_must_match: bool = self._config.scope_must_match_original_slice

    def _increment_attempt(self) -> None:
        self._attempt_count += 1

    def _budget_exhausted(self) -> bool:
        return self._attempt_count >= self._max_attempts

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

    def attempt(
        self,
        validation_result: dict[str, Any],
        slice_contract: dict[str, Any],
    ) -> RepairOutcome:
        """Run one repair attempt.

        Args:
            validation_result: The failed validation result.
            slice_contract: The original slice contract for scope enforcement.

        Returns:
            RepairOutcome with success status.
        """
        if self._budget_exhausted():
            return RepairOutcome(
                success=False,
                attempts_used=self._attempt_count,
                message=f"Repair budget exhausted ({self._max_attempts} attempts)",
            )

        self._increment_attempt()

        # Build feedback prompt (used by SliceCoordinator to re-generate)
        repair_prompt = self._build_repair_prompt(validation_result)

        # The SliceCoordinator will:
        #   1. Call the model with this repair prompt
        #   2. Validate the new operations
        #   3. Preview and apply
        # We return an outcome that signals "try again with this prompt"
        return RepairOutcome(
            success=False,
            attempts_used=self._attempt_count,
            message=(
                f"Repair attempt {self._attempt_count}/{self._max_attempts}: "
                f"{repair_prompt[:200]}..."
            ),
        )
