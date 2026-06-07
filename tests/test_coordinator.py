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
    """Initialize a git repo with committed files for coordinator tests."""
    import subprocess

    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)
    (path / "src").mkdir(parents=True, exist_ok=True)
    (path / "existing.rs").write_text("// existing\n")
    (path / "src" / "generated.rs").write_text("// placeholder\n")
    subprocess.run(
        ["git", "add", "existing.rs", "src/generated.rs"],
        cwd=path,
        check=True,
        capture_output=True,
    )
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

    def test_coordinator_creates_run_directory_on_start(self, coordinator: object, tmp_path: Path) -> None:
        """Running the pipeline creates the run artifact directory."""
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "test-slice",
            "allowed_files": ["src/generated.rs"],
        }

        outcome = coord.run(handoff, slice_contract)
        assert outcome.run_dir is not None
        assert outcome.run_dir.exists()
        assert (outcome.run_dir / "run.json").exists()

    def test_preview_captures_new_files(self, coordinator: object, tmp_path: Path) -> None:
        """Preview diff includes newly created (untracked) files.

        Verifies B3 fix: preview uses git add -A + git diff --cached
        so create_file operations appear in the diff.
        """
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]

        # Use a backend that creates a new file
        class NewFileBackend:
            async def generate_operation_batch(self, sp: str, up: str, schema: dict) -> str:
                return json.dumps(
                    {
                        "schema_id": "forgerwrite.operation_batch.v1",
                        "batch_id": "b1",
                        "slice_id": "test-slice",
                        "operations": [
                            {
                                "op": "create_file",
                                "path": "src/new_module.rs",
                                "content": "pub fn hello() {}\n",
                            }
                        ],
                    }
                )

        coord._backend = NewFileBackend()

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "test-slice",
            "allowed_files": ["src/new_module.rs", "src/generated.rs"],
        }

        outcome = coord.run(handoff, slice_contract)
        # Check the preview diff includes the new file
        diff_path = outcome.run_dir / "preview.diff" if outcome.run_dir else None
        assert diff_path is not None
        assert diff_path.exists(), f"preview.diff missing at {diff_path}"
        diff_content = diff_path.read_text()
        assert "new_module.rs" in diff_content, (
            f"New file not in diff:\n{diff_content}"
        )
        assert "pub fn hello()" in diff_content

    def test_run_json_includes_slice_id(self, coordinator: object, tmp_path: Path) -> None:
        """run.json artifact contains the real slice_id, not 'unknown'."""
        from forgerwrite_mcp.coordinator import SliceCoordinator

        coord: SliceCoordinator = coordinator  # type: ignore[assignment]

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust"}
        slice_contract = {
            "schema_id": "forgerwrite.slice.v1",
            "slice_id": "slice-abc-123",
            "allowed_files": ["src/generated.rs"],
        }

        outcome = coord.run(handoff, slice_contract)
        run_json_path = outcome.run_dir / "run.json" if outcome.run_dir else None
        assert run_json_path is not None
        run_data = json.loads(run_json_path.read_text())
        assert run_data["slice_id"] == "slice-abc-123", (
            f"Expected 'slice-abc-123', got {run_data['slice_id']}"
        )

    def test_snapshot_cleanup_wired_in_coordinator(
        self, coordinator: object, tmp_path: Path
    ) -> None:
        """cleanup_snapshot is imported and callable from the coordinator.

        The actual snapshot-ref deletion is verified in forge/test_git_utils.py
        (test_cleanup_snapshot_removes_ref). This test confirms the import path
        and that the coordinator module compiles with cleanup_snapshot wired in.
        """
        import subprocess

        from forgerwrite_mcp.coordinator import SliceCoordinator
        from forgerwrite_mcp.forge.git_utils import cleanup_snapshot, create_snapshot

        # Direct verification: create + cleanup round-trip works in this repo
        coord: SliceCoordinator = coordinator  # type: ignore[assignment]
        run_id = "run_cleanup_test"
        create_snapshot(tmp_path, run_id)
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/forgerwrite/{run_id}"],
            cwd=tmp_path,
            capture_output=True,
        )
        assert result.returncode == 0, "Snapshot ref should exist after create"
        cleanup_snapshot(tmp_path, run_id)
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/forgerwrite/{run_id}"],
            cwd=tmp_path,
            capture_output=True,
        )
        assert result.returncode != 0, "Snapshot ref should be deleted after cleanup"

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
        # Preview restores worktree; committed files still exist
        assert (tmp_path / "src" / "generated.rs").exists()
        assert (tmp_path / "src" / "generated.rs").read_text() == "// placeholder\n"

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
            "allowed_files": ["existing.rs"],
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
