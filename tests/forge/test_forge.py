"""Tests for the Forge safety layer — preview, apply, restore."""

import subprocess
from pathlib import Path

import pytest


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)
    (path / "lib.rs").write_text("fn main() {}\n")
    subprocess.run(["git", "add", "lib.rs"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def _make_registry() -> object:
    from forgerwrite_mcp.operations.registry import default_registry

    return default_registry()


class TestForgePreview:
    def test_preview_generates_diff_against_clean_worktree(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.forge.forge import preview_operations

        _init_repo(tmp_path)
        ops = [{"op": "create_file", "path": "new_file.rs", "content": "// new\n"}]
        batch = {"operations": ops}
        result = preview_operations(
            tmp_path, "run_test", batch, {"allowed_files": ["new_file.rs"]}, _make_registry()
        )
        assert result.diff_path.exists()
        diff_content = result.diff_path.read_text()
        assert "new_file.rs" in diff_content or "new file" in diff_content.lower()

    def test_preview_restores_after_diff(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.forge.forge import preview_operations

        _init_repo(tmp_path)
        original = (tmp_path / "lib.rs").read_text()
        ops = [{"op": "create_file", "path": "extra.rs", "content": "// extra\n"}]
        batch = {"operations": ops}
        preview_operations(
            tmp_path, "run_test", batch, {"allowed_files": ["extra.rs"]}, _make_registry()
        )
        # Worktree should be unchanged
        assert (tmp_path / "lib.rs").read_text() == original
        assert not (tmp_path / "extra.rs").exists()

    def test_preview_refuses_dirty_worktree(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.forge.forge import preview_operations
        from forgerwrite_mcp.forge.git_utils import WorktreeDirtyError

        _init_repo(tmp_path)
        (tmp_path / "lib.rs").write_text("dirty\n")
        batch = {"operations": []}
        with pytest.raises(WorktreeDirtyError):
            preview_operations(tmp_path, "run_test", batch, {"allowed_files": []}, _make_registry())


class TestForgeApply:
    def test_apply_applies_all_operations(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalRecord
        from forgerwrite_mcp.forge.forge import apply_approved_operations

        _init_repo(tmp_path)
        ops = [{"op": "create_file", "path": "generated.rs", "content": "// gen\n"}]
        batch = {"operations": ops}
        slice_contract = {"allowed_files": ["generated.rs"]}
        from forgerwrite_mcp.forge.forge import preview_operations

        preview_operations(tmp_path, "run_test", batch, slice_contract, _make_registry())
        # Simulate approval
        approval = ApprovalRecord(
            run_id="run_test",
            approved=True,
            approved_at="2026-06-06T12:00:00Z",
            approval_method="terminal_cli",
            preview_diff_sha256="fake",
            worktree_clean_at_approval=True,
        )

        result = apply_approved_operations(
            tmp_path, "run_test", batch, slice_contract, approval, _make_registry()
        )
        assert len(result.changed) == 1
        assert (tmp_path / "generated.rs").exists()

    def test_apply_restores_on_failure(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalRecord
        from forgerwrite_mcp.forge.forge import apply_approved_operations
        from forgerwrite_mcp.operations.registry import OperationApplyError

        _init_repo(tmp_path)
        original = (tmp_path / "lib.rs").read_text()
        ops = [{"op": "delete_file", "path": "nonexistent.rs"}]
        batch = {"operations": ops}
        slice_contract = {"allowed_files": ["nonexistent.rs"]}
        approval = ApprovalRecord(
            run_id="run_test",
            approved=True,
            approved_at="2026-06-06T12:00:00Z",
            approval_method="terminal_cli",
            preview_diff_sha256="fake",
            worktree_clean_at_approval=True,
        )

        with pytest.raises(OperationApplyError):
            apply_approved_operations(
                tmp_path, "run_test", batch, slice_contract, approval, _make_registry()
            )
        # Worktree restored
        assert (tmp_path / "lib.rs").read_text() == original

    def test_apply_rejects_operation_outside_allowed_files(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalRecord
        from forgerwrite_mcp.forge.forge import apply_approved_operations

        _init_repo(tmp_path)
        (tmp_path / "secret.rs").write_text("secret\n")
        subprocess.run(["git", "add", "secret.rs"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add"], cwd=tmp_path, check=True, capture_output=True
        )

        ops = [{"op": "replace_file", "path": "secret.rs", "content": "leaked\n"}]
        batch = {"operations": ops}
        slice_contract = {"allowed_files": ["other.rs"]}  # secret.rs NOT allowed
        approval = ApprovalRecord(
            run_id="run_test",
            approved=True,
            approved_at="2026-06-06T12:00:00Z",
            approval_method="terminal_cli",
            preview_diff_sha256="fake",
            worktree_clean_at_approval=True,
        )

        with pytest.raises(ValueError, match="outside allowed_files"):
            apply_approved_operations(
                tmp_path, "run_test", batch, slice_contract, approval, _make_registry()
            )

    def test_apply_refuses_dirty_worktree(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalRecord
        from forgerwrite_mcp.forge.forge import apply_approved_operations
        from forgerwrite_mcp.forge.git_utils import WorktreeDirtyError

        _init_repo(tmp_path)
        (tmp_path / "lib.rs").write_text("dirty\n")
        approval = ApprovalRecord(
            run_id="run_test",
            approved=True,
            approved_at="2026-06-06T12:00:00Z",
            approval_method="terminal_cli",
            preview_diff_sha256="fake",
            worktree_clean_at_approval=True,
        )
        with pytest.raises(WorktreeDirtyError):
            apply_approved_operations(
                tmp_path,
                "run_test",
                {"operations": []},
                {"allowed_files": []},
                approval,
                _make_registry(),
            )
