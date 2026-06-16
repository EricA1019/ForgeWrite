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
from .contracts.registry import ContractRegistry
from .dead_letter import write_dead_letter
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
        auto_approve: bool = False,
        enricher: object | None = None,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._config = config
        self._registry = registry
        self._backend = backend
        self._auto_approve = auto_approve
        self._enricher = enricher
        self._contract_registry = ContractRegistry(Path(__file__).parent.parent / "schemas")

        # Per-run state
        self._run_id: str = ""
        self._run_dir: Path | None = None
        self._slice_id: str = ""
        self._context_packet: dict[str, Any] = {}

    def run(self, handoff: dict[str, Any], slice_contract: dict[str, Any]) -> RunOutcome:
        """Sync entrypoint. Delegates to :meth:`run_async`."""
        import asyncio

        return asyncio.run(self.run_async(handoff, slice_contract))

    async def run_async(
        self, handoff: dict[str, Any], slice_contract: dict[str, Any]
    ) -> RunOutcome:
        """Async-safe entrypoint. Use this when called from within an event loop.

        Identical logic to :meth:`run` but uses ``await`` instead of
        ``asyncio.run()`` for async calls.
        """
        self._run_id = generate_run_id()
        self._run_dir = init_run_dir(self._run_id, base_dir=self._repo_root)
        self._slice_id = slice_contract.get("slice_id", "unknown")
        status = _STATUS_DRAFT

        try:
            status = self._validate_contracts(handoff, slice_contract)
            status = self._enrich_with_scout(handoff, slice_contract)
            status = self._build_context(handoff, slice_contract)
            # Generate + schema-validate with retry on schema/semantic errors
            status = await self._generate_with_schema_repair(handoff, slice_contract)
            if status != _STATUS_OPS_SEMANTIC_VALID:
                # Schema/semantic repair exhausted — record and exit
                write_dead_letter(
                    self._run_dir,
                    f"Schema repair exhausted at status {status}",
                )
                return RunOutcome(
                    run_id=self._run_id,
                    status=status,
                    run_dir=self._run_dir,
                    errors=[f"Schema/semantic validation failed after repair: {status}"],
                )
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
                        status = await self._maybe_repair_async(slice_contract)
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

    def _enrich_with_scout(self, handoff: dict, slice_contract: dict) -> str:
        """Run Scout evidence pipeline before context building.

        Attaches scout packet metadata to the context packet if Scout
        is enabled (config.scout.enabled) and a question is available.
        This is an Open/Closed extension: no existing module is modified.
        """
        # Scout is optional — skip if no description in handoff
        question = handoff.get("description", "")
        if not question:
            return _STATUS_CONTRACTS_VALIDATED

        try:
            from .scout.coordinator import ScoutCoordinator

            scout = ScoutCoordinator(
                repo_root=self._repo_root,
                enricher=self._enricher,
            )
            allowed = slice_contract.get("allowed_files", [])
            packet = scout.scout(question=question, allowed_files=allowed)
            self._scout_packet = packet
            write_artifact(
                self._run_dir,
                "scout_packet.json",
                packet.__dict__,
            )
        except Exception as exc:
            # Scout failures are non-fatal — log and continue
            write_dead_letter(
                self._run_dir,
                f"Scout enrichment failed: {exc}",
            )
        return _STATUS_CONTRACTS_VALIDATED

    def _build_context(self, handoff: dict, slice_contract: dict) -> str:
        self._context_packet = build_context_packet(
            self._repo_root,
            handoff,
            slice_contract,
            self._config.limits,
            hygiene=self._config.hygiene,
        )
        write_artifact(self._run_dir, "context_packet.json", self._context_packet)
        return _STATUS_CONTEXT_READY

    async def _generate_operations(self, handoff: dict, slice_contract: dict) -> str:
        # Uses LocalModelBackend Protocol (Phase 2: real backends in local_model / llama_client)
        system_prompt = (
            "You are a coding assistant that produces structured JSON operation batches.\n\n"
            "Respond ONLY with a JSON object matching this exact structure:\n"
            '{\n'
            '  "batch_id": "unique-id",\n'
            '  "slice_id": "<from slice contract>",\n'
            '  "operations": [\n'
            '    {\n'
            '      "op": "<operation_type>",\n'
            '      "path": "<relative_file_path>",\n'
            '      "content": "<the content to write or insert>"\n'
            '    }\n'
            '  ]\n'
            '}\n\n'
            "VALID OPERATION TYPES AND THEIR REQUIRED FIELDS:\n"
            '- create_file: op, path, content\n'
            '- replace_file: op, path, content\n'
            '- replace_line_range: op, path, start_line, end_line, content\n'
            '- insert_after_line: op, path, after_line, content\n'
            '- insert_before_line: op, path, before_line, content\n'
            '- delete_file: op, path\n\n'
            "RULES:\n"
            "1. Every operation (except delete_file) MUST have a 'content' field with the text to write.\n"
            "2. Use the exact file paths from the allowed_files list.\n"
            "3. Use line numbers from the provided file contents.\n"
            "4. Line numbers are 1-indexed. Line ranges are inclusive."
        )
        user_prompt = json.dumps({
            "task": handoff.get("description", ""),
            "slice": slice_contract,
            "files": self._context_packet.get("files", {}),
        })

        # Enrich with RAG if available
        if self._enricher is not None:
            query = handoff.get("description", "") + " " + json.dumps(slice_contract)
            user_prompt = self._enricher.enrich(
                base_prompt=user_prompt,
                query=query,
                k=self._config.rag.k_documents,
            )

        # If this is a schema repair retry, prepend the error
        if hasattr(self, "_schema_repair_error") and self._schema_repair_error:
            user_prompt = (
                f"PREVIOUS ATTEMPT FAILED SCHEMA VALIDATION:\n"
                f"{self._schema_repair_error}\n\n"
                f"Please fix the validation error and produce a corrected JSON "
                f"operation batch with ALL required fields.\n\n"
                f"{user_prompt}"
            )
            self._schema_repair_error = None  # consumed

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

    async def _generate_with_schema_repair(
        self, handoff: dict, slice_contract: dict
    ) -> str:
        """Generate operations with up to N retries on schema/semantic errors.

        Feeds schema validation errors back to the model as repair prompts.
        Uses the same repair budget as code validation (repair.max_attempts).
        """
        max_attempts = max(1, self._config.repair.max_attempts)

        for attempt in range(max_attempts + 1):
            # Generate
            status = await self._generate_operations(handoff, slice_contract)
            if status != _STATUS_LOCAL_GENERATED:
                return status

            # Schema validate
            status = self._validate_schema()
            if status != _STATUS_OPS_SCHEMA_VALID:
                if attempt < max_attempts:
                    schema_error = self._last_schema_error or "Unknown schema error"
                    self._repair_prompt_from_schema_error(schema_error, attempt + 1)
                    continue
                return status

            # Semantic validate
            status = self._validate_semantic(slice_contract)
            if status != _STATUS_OPS_SEMANTIC_VALID:
                if attempt < max_attempts:
                    semantic_error = self._last_semantic_error or "Unknown semantic error"
                    self._repair_prompt_from_schema_error(semantic_error, attempt + 1)
                    continue
                return status

            return _STATUS_OPS_SEMANTIC_VALID

        return status

    def _repair_prompt_from_schema_error(self, error: str, attempt: int) -> None:
        """Store schema error for next generation attempt."""

        # Store the error so the next generate_operations call can include it
        self._schema_repair_error = error
        self._schema_repair_attempt = attempt
        write_artifact(
            self._run_dir,
            f"schema_repair_error_{attempt}.txt",
            {"error": error},
        )

    def _validate_schema(self) -> str:
        try:
            self._contract_registry.validate(
                "operation_batch.v1.json", self._operation_batch
            )
            self._last_schema_error = None
            return _STATUS_OPS_SCHEMA_VALID
        except Exception as exc:
            self._last_schema_error = str(exc)
            return _STATUS_LOCAL_GENERATED  # stay in previous state

    def _validate_semantic(self, slice_contract: dict) -> str:
        try:
            validator = default_validator()
            validator.validate(
                self._operation_batch,
                slice_contract,
                limits=self._config.limits,
                permissions=self._config.permissions,
            )
            self._last_semantic_error = None
            return _STATUS_OPS_SEMANTIC_VALID
        except Exception as exc:
            self._last_semantic_error = str(exc)
            return _STATUS_OPS_SCHEMA_VALID  # stay in previous state

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
        # Auto-approve for testing/CI; otherwise check approval record
        if self._auto_approve:
            approval_path = self._run_dir / "approval_record.json"
            approval_path.write_text(json.dumps({"approved": True, "run_id": self._run_id}))
            return _STATUS_APPROVED
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
        # Resolve validation profile from the language adapter
        profile_id = "rust_default"  # fallback
        try:
            from .languages import get_adapter

            adapter = get_adapter(self._config.project.language)
            if adapter is not None:
                profile_id = adapter.get_default_profile_name()
        except Exception:
            pass

        result = run_validation_profile(
            self._repo_root,
            profile_id,
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

            # Enrich repair prompt with RAG if available
            if self._enricher is not None and self._operation_batch is not None:
                # Build a repair-specific query from validation errors
                repair_query = json.dumps(validation_result) + " " + json.dumps(
                    self._operation_batch
                )
                prompt = self._enricher.enrich(
                    base_prompt=prompt,
                    query=repair_query,
                    k=self._config.rag.k_documents,
                )

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

    async def _maybe_repair_async(self, slice_contract: dict) -> str:
        """Async version of _maybe_repair. Uses await instead of asyncio.run."""
        repair = RepairCoordinator(config=self._config.repair)

        validation_path = self._run_dir / "validation_result.json"
        if validation_path.exists():
            validation_result = json.loads(validation_path.read_text(encoding="utf-8"))
        else:
            validation_result = {"passed": False, "commands": []}

        while True:
            result = repair.attempt(validation_result, slice_contract)
            if result is None:
                self._restore_apply_snapshot()
                return _STATUS_VALIDATION_FAILED

            prompt, _remaining = result
            attempt_n = repair.attempt_count

            if self._enricher is not None and self._operation_batch is not None:
                repair_query = json.dumps(validation_result) + " " + json.dumps(
                    self._operation_batch
                )
                prompt = self._enricher.enrich(
                    base_prompt=prompt,
                    query=repair_query,
                    k=self._config.rag.k_documents,
                )

            write_artifact(
                self._run_dir,
                f"repair_prompt_{attempt_n}.txt",
                {"prompt": prompt},
            )

            try:
                # Use await instead of asyncio.run
                system_prompt = (
                    "You are a coding assistant that produces structured JSON "
                    "operation batches.\n\n"
                    "Respond ONLY with a JSON object matching the operation_batch schema."
                )
                raw = await self._backend.generate_operation_batch(
                    system_prompt, prompt, self._operation_batch_schema
                )
                write_artifact(
                    self._run_dir,
                    f"repair_raw_{attempt_n}.txt",
                    {"raw": raw},
                )
                self._operation_batch = json.loads(raw)
                write_artifact(
                    self._run_dir,
                    f"operation_batch_repair_{attempt_n}.json",
                    self._operation_batch,
                )
            except Exception as exc:
                write_dead_letter(
                    self._run_dir,
                    f"Repair attempt {attempt_n} failed: {exc}",
                )
                continue

            try:
                self._contract_registry.validate(
                    "operation_batch.v1.json", self._operation_batch
                )
                validator = default_validator()
                validator.validate(
                    self._operation_batch,
                    slice_contract,
                    limits=self._config.limits,
                    permissions=self._config.permissions,
                )
            except Exception:
                continue

            self._preview(slice_contract)
            self._apply(slice_contract)
            status = self._validate_result()
            if status == _STATUS_VALIDATION_PASSED:
                cleanup_snapshot(self._repo_root, self._run_id)
                return _STATUS_VALIDATION_PASSED

    def _restore_apply_snapshot(self) -> None:
        """Restore the apply snapshot if it exists. No-op on failure."""
        if self._run_id:
            import contextlib

            with contextlib.suppress(Exception):
                restore_snapshot(self._repo_root, self._run_id)

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
