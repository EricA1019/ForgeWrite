"""SliceCoordinator — state machine owner for the ForgerWrite pipeline.

Owns the 14-state transition machine from design §6. The MCP server and CLI
delegate to this class — no orchestration logic lives in either.

Design: §6 state machine, SRP split from revision notes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifacts import generate_run_id, init_run_dir, write_artifact
from .config import ForgerWriteConfig
from .context import build_context_packet
from .dead_letter import write_dead_letter
from .contracts.registry import ContractRegistry
from .forge.forge import preview_operations as forge_preview
from .forge.git_utils import (
    assert_clean_worktree,
    cleanup_snapshot,
    create_snapshot,
    restore_snapshot,
)
from .local_model import LocalModelBackend
from .operations.registry import OperationRegistry
from .repair import RepairCoordinator
from .validation.runner import run_validation_profile
from .validation.semantic import default_validator


@dataclass
class RunOutcome:
    """Result of a full pipeline run."""

    run_id: str
    status: str
    run_dir: Path | None = None
    errors: list[str] = field(default_factory=list)


# State constants (design §6)
_STATUS_DRAFT = "draft"
_STATUS_CONTRACTS_VALIDATED = "contracts_validated"
_STATUS_CONTEXT_READY = "context_ready"
_STATUS_LOCAL_GENERATED = "local_generated"
_STATUS_OPS_SCHEMA_VALID = "ops_schema_valid"
_STATUS_OPS_SEMANTIC_VALID = "ops_semantic_valid"
_STATUS_PREVIEW_READY = "preview_ready"
_STATUS_APPROVED = "approved"
_STATUS_APPLIED = "applied"
_STATUS_VALIDATION_PASSED = "validation_passed"
_STATUS_VALIDATION_FAILED = "validation_failed"
_STATUS_REPAIR_GENERATED = "repair_generated"
_STATUS_RESTORED = "restored"
_STATUS_RECORDED = "recorded"


class SliceCoordinator:
    """Orchestrates the full ForgerWrite pipeline for a single slice.

    Owns state transitions. No MCP or CLI knowledge — pure library.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        config: ForgerWriteConfig,
        registry: OperationRegistry,
        backend: LocalModelBackend,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._config = config
        self._registry = registry
        self._backend = backend
        self._contract_registry = ContractRegistry(Path(__file__).parent.parent / "schemas")

        # Per-run state
        self._run_id: str = ""
        self._run_dir: Path | None = None
        self._slice_id: str = ""

    def run(self, handoff: dict[str, Any], slice_contract: dict[str, Any]) -> RunOutcome:
        """Execute the full pipeline for a handoff + slice.

        Returns a RunOutcome with the final status. The run artifacts
        are written to .forgerwrite/runs/<run_id>/ regardless of outcome.
        """
        import asyncio

        self._run_id = generate_run_id()
        self._run_dir = init_run_dir(self._run_id, base_dir=self._repo_root)
        self._slice_id = slice_contract.get("slice_id", "unknown")
        status = _STATUS_DRAFT

        try:
            status = self._validate_contracts(handoff, slice_contract)
            status = self._build_context(handoff, slice_contract)
            status = asyncio.run(self._generate_operations(handoff, slice_contract))
            status = self._validate_schema()
            status = self._validate_semantic(slice_contract)
            status = self._preview(slice_contract)
            status = self._await_approval()
            if status == _STATUS_APPROVED:
                status = self._apply(slice_contract)
                if status == _STATUS_APPLIED:
                    from .audit import write_audit_event

                    write_audit_event(self._run_dir, "apply", {"run_id": self._run_id})
                    status = self._validate_result()
                    if status == _STATUS_VALIDATION_PASSED:
                        cleanup_snapshot(self._repo_root, self._run_id)
                    elif status == _STATUS_VALIDATION_FAILED:
                        status = self._maybe_repair(slice_contract)
        except Exception as exc:
            write_dead_letter(self._run_dir, str(exc))
            return RunOutcome(
                run_id=self._run_id,
                status=status,
                run_dir=self._run_dir,
                errors=[str(exc)],
            )
        finally:
            self._record(status)

        return RunOutcome(run_id=self._run_id, status=status, run_dir=self._run_dir)

    # ── Phase methods ──────────────────────────────────────────────────────

    def _validate_contracts(self, handoff: dict, slice_contract: dict) -> str:
        self._contract_registry.validate("handoff.v1.json", handoff)
        self._contract_registry.validate("slice.v1.json", slice_contract)
        return _STATUS_CONTRACTS_VALIDATED

    def _build_context(self, handoff: dict, slice_contract: dict) -> str:
        context = build_context_packet(
            self._repo_root,
            handoff,
            slice_contract,
            self._config.limits,
            hygiene=self._config.hygiene,
        )
        write_artifact(self._run_dir, "context_packet.json", context)
        return _STATUS_CONTEXT_READY

    async def _generate_operations(self, handoff: dict, slice_contract: dict) -> str:
        # Uses LocalModelBackend Protocol (Phase 2: real backends in local_model / llama_client)
        system_prompt = "You are a coding assistant producing structured JSON operations."
        user_prompt = json.dumps({"slice": slice_contract, "handoff": handoff})
        self._operation_batch_schema = json.loads(
            (Path(__file__).parent.parent / "schemas" / "operation_batch.v1.json").read_text()
        )
        raw = await self._backend.generate_operation_batch(
            system_prompt, user_prompt, self._operation_batch_schema
        )
        write_artifact(self._run_dir, "local_model_raw_attempt_1.txt", {"raw": raw})
        self._operation_batch = json.loads(raw)
        write_artifact(self._run_dir, "operation_batch.json", self._operation_batch)
        return _STATUS_LOCAL_GENERATED

    def _validate_schema(self) -> str:
        self._contract_registry.validate("operation_batch.v1.json", self._operation_batch)
        return _STATUS_OPS_SCHEMA_VALID

    def _validate_semantic(self, slice_contract: dict) -> str:
        validator = default_validator()
        validator.validate(
            self._operation_batch,
            slice_contract,
            limits=self._config.limits,
            permissions=self._config.permissions,
        )
        return _STATUS_OPS_SEMANTIC_VALID

    def _preview(self, slice_contract: dict) -> str:
        # DRY: delegate to forge.preview_operations() which stages new files
        # and generates a cached diff against the snapshot.
        forge_preview(
            self._repo_root,
            self._run_id,
            self._operation_batch,
            slice_contract,
            self._registry,
        )
        return _STATUS_PREVIEW_READY

    def _await_approval(self) -> str:
        # Non-blocking check: approval record is written by CLI
        approval_path = self._run_dir / "approval_record.json"
        if approval_path.exists():
            record = json.loads(approval_path.read_text())
            if record.get("approved"):
                return _STATUS_APPROVED
        return _STATUS_PREVIEW_READY

    def _apply(self, slice_contract: dict) -> str:
        # TOCTOU: re-check worktree
        assert_clean_worktree(self._repo_root)
        create_snapshot(self._repo_root, self._run_id)
        try:
            allowed = set(slice_contract.get("allowed_files", []))
            for op in self._operation_batch.get("operations", []):
                if op["path"] not in allowed:
                    raise ValueError(f"Operation targets file outside allowed_files: {op['path']}")
                handler = self._registry.dispatch(op)
                handler.apply(self._repo_root, op)
        except Exception:
            restore_snapshot(self._repo_root, self._run_id)
            return _STATUS_RESTORED
        return _STATUS_APPLIED

    def _validate_result(self) -> str:
        result = run_validation_profile(
            self._repo_root,
            "rust_default",
            self._config.validation,
            limits=self._config.limits,
        )
        write_artifact(self._run_dir, "validation_result.json", result)
        if result["passed"]:
            return _STATUS_VALIDATION_PASSED
        return _STATUS_VALIDATION_FAILED

    def _maybe_repair(self, slice_contract: dict) -> str:
        """Bounded repair loop — re-invoke model with validation errors.

        Loops up to repair.max_attempts times:
        1. Build repair prompt from validation errors
        2. Re-invoke local model
        3. Schema-validate + semantic-validate
        4. Re-preview + re-apply + re-validate
        5. If validation passes → success; else → loop
        """
        import asyncio

        repair = RepairCoordinator(config=self._config.repair)

        # Read the actual validation result (not overwriting with {})
        validation_path = self._run_dir / "validation_result.json"
        if validation_path.exists():
            validation_result = json.loads(validation_path.read_text(encoding="utf-8"))
        else:
            validation_result = {
                "passed": False,
                "commands": [],
            }

        while True:
            result = repair.attempt(validation_result, slice_contract)
            if result is None:
                # Budget exhausted — restore snapshot and fail
                self._restore_apply_snapshot()
                return _STATUS_VALIDATION_FAILED

            prompt, _remaining = result
            attempt_n = repair.attempt_count

            # Write repair prompt artifact
            write_artifact(
                self._run_dir,
                f"repair_prompt_{attempt_n}.txt",
                {"prompt": prompt},
            )

            # Re-invoke model with repair prompt
            try:
                raw = asyncio.run(
                    self._backend.generate_operation_batch(
                        "You are a coding assistant fixing validation errors.",
                        prompt,
                        self._operation_batch_schema,
                    )
                )
            except Exception:
                # Model error — continue to next attempt
                continue

            # Write raw response artifact
            write_artifact(
                self._run_dir,
                f"repair_response_{attempt_n}.json",
                {"raw": raw},
            )

            # Parse and schema-validate
            try:
                self._operation_batch = json.loads(raw)
                self._validate_schema()
            except Exception:
                continue

            # Semantic-validate (with original slice scope)
            try:
                self._validate_semantic(slice_contract)
            except Exception:
                continue

            # Re-preview (applies ops, generates diff, restores)
            try:
                self._preview(slice_contract)
            except Exception:
                continue

            # Re-apply
            status = self._apply(slice_contract)
            if status != _STATUS_APPLIED:
                continue

            # Re-validate
            status = self._validate_result()
            if status == _STATUS_VALIDATION_PASSED:
                cleanup_snapshot(self._repo_root, self._run_id)
                return _STATUS_VALIDATION_PASSED

            # Validation failed again — update result for next prompt
            if self._run_dir is not None:
                vr_path = self._run_dir / "validation_result.json"
                if vr_path.exists():
                    validation_result = json.loads(vr_path.read_text(encoding="utf-8"))

        return _STATUS_VALIDATION_FAILED

    def _restore_apply_snapshot(self) -> None:
        """Restore the apply snapshot if it exists. No-op on failure."""
        if self._run_id:
            try:
                restore_snapshot(self._repo_root, self._run_id)
            except Exception:
                pass

    def _record(self, final_status: str) -> None:
        run_meta = {
            "schema_id": "forgerwrite.run.v1",
            "run_id": self._run_id,
            "slice_id": self._slice_id,
            "status": final_status,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "artifacts_dir": str(self._run_dir) if self._run_dir else "",
        }
        write_artifact(self._run_dir, "run.json", run_meta)

    def _cleanup(self) -> None:
        if self._run_id:
            cleanup_snapshot(self._repo_root, self._run_id)
