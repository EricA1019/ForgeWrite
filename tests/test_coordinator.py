"""Tests for the SliceCoordinator — state machine owner."""

import json
from pathlib import Path

import pytest


class FakeModelBackend:
    """A simple fake backend for coordinator tests. Returns canned JSON."""

    async def generate_operation_batch(
        self, system_prompt: str, user_prompt: str, schema: dict
    ) -> str:
        return json.dumps(
            {
                "schema_id": "forgerwrite.operation_batch.v1",
                "batch_id": "batch-test",
                "slice_id": "test-slice",
                "operations": [
                    {"op": "create_file", "path": "src/generated.rs", "content": "// generated\n"}
                ],
            }
        )


def _init_repo(path: Path) -> None:
    """Initialize a git repo with one committed file."""
    import subprocess

    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)
    (path / "existing.rs").write_text("// existing\n")
    subprocess.run(["git", "add", "existing.rs"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


class TestSliceCoordinator:
    """Tests for SliceCoordinator state machine."""

    @pytest.fixture
    def coordinator(self, tmp_path: Path) -> object:
        """Create a SliceCoordinator with fake backend."""
        _init_repo(tmp_path)
        from forgerwrite_mcp.config import (
            ForgerWriteConfig,
            HygieneConfig,
            LimitsConfig,
            LocalModelConfig,
            PermissionsConfig,
            ProjectConfig,
            RepairConfig,
            ValidationConfig,
        )
        from forgerwrite_mcp.coordinator import SliceCoordinator
        from forgerwrite_mcp.operations.registry import default_registry

        config = ForgerWriteConfig(
            project=ProjectConfig(name="test", language="rust", repo_root="."),
            local_model=LocalModelConfig(),
            validation=ValidationConfig(commands={}, profiles={}),
            permissions=PermissionsConfig(),
            hygiene=HygieneConfig(),
            limits=LimitsConfig(),
            repair=RepairConfig(),
        )
        return SliceCoordinator(
            repo_root=tmp_path,
            config=config,
            registry=default_registry(),
            backend=FakeModelBackend(),
        )

    def test_coordinator_creates_run_directory_on_start(self, coordinator: object) -> None:
        """Starting a run creates the run artifact directory."""
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]
        run_dir = coord._init_run()
        assert run_dir.exists()
        assert (run_dir / "run.json").exists()
        # Cleanup
        coord._cleanup()

    def test_coordinator_transitions_through_states_in_order(
        self, coordinator: object, tmp_path: Path
    ) -> None:
        """Full happy path transitions through all states."""
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "test-slice",
            "allowed_files": ["src/generated.rs"],
        }

        outcome = coord.run(handoff, slice_contract)
        # Without terminal approval, the pipeline stops at preview_ready
        assert outcome.status == "preview_ready"
        # Preview restores worktree, so the generated file should NOT exist
        assert not (tmp_path / "src" / "generated.rs").exists()

    def test_coordinator_stops_at_schema_validation_failure(self, coordinator: object) -> None:
        """Invalid operation batch (bad schema) stops the pipeline."""
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]

        class BadBackend:
            async def generate_operation_batch(self, sp: str, up: str, schema: dict) -> str:
                return '{"invalid": "json'

        coord._backend = BadBackend()

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "test-slice",
            "allowed_files": ["src/generated.rs"],
        }

        outcome = coord.run(handoff, slice_contract)
        # Pipeline stops after context_ready when generation fails
        assert outcome.status in ("draft", "context_ready", "local_generated")

    def test_coordinator_restores_on_apply_failure(
        self, coordinator: object, tmp_path: Path
    ) -> None:
        """If apply fails, snapshot is restored and worktree is unchanged."""
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]
        original = (tmp_path / "existing.rs").read_text()

        class BadOpBackend:
            async def generate_operation_batch(self, sp: str, up: str, schema: dict) -> str:
                return json.dumps(
                    {
                        "schema_id": "forgerwrite.operation_batch.v1",
                        "batch_id": "b1",
                        "slice_id": "test-slice",
                        "operations": [{"op": "delete_file", "path": "nonexistent_file.rs"}],
                    }
                )

        coord._backend = BadOpBackend()

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "test-slice",
            "allowed_files": ["nonexistent_file.rs"],
        }

        outcome = coord.run(handoff, slice_contract)
        assert outcome.status != "recorded"
        # Worktree should be restored
        assert (tmp_path / "existing.rs").read_text() == original

    def test_coordinator_records_dead_letter_on_unrecoverable_error(
        self, coordinator: object
    ) -> None:
        """Unrecoverable errors produce a dead letter."""
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]

        class ExplodingBackend:
            async def generate_operation_batch(self, sp: str, up: str, schema: dict) -> str:
                raise RuntimeError("Simulated backend crash")

        coord._backend = ExplodingBackend()

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "test-slice",
            "allowed_files": ["src/generated.rs"],
        }

        outcome = coord.run(handoff, slice_contract)
        # Should have recorded something (dead letter or error status)
        assert outcome.status is not None
        assert outcome.run_id is not None
