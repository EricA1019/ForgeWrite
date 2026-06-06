"""Tests for the Approval Store."""

import json
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


class TestApproval:
    def test_write_approval_creates_record(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import write_approval_record

        _init_repo(tmp_path)
        run_dir = tmp_path / ".forgerwrite" / "runs" / "run_test"
        run_dir.mkdir(parents=True)
        (run_dir / "preview.diff").write_text("diff content here")

        result = write_approval_record(run_dir)
        assert result.exists()
        record = json.loads(result.read_text())
        assert record["approved"] is True
        assert record["preview_diff_sha256"]

    def test_assert_approved_rejects_missing_file(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalError, assert_approved

        _init_repo(tmp_path)
        run_dir = tmp_path / ".forgerwrite" / "runs" / "run_test"
        run_dir.mkdir(parents=True)

        with pytest.raises(ApprovalError, match="not approved"):
            assert_approved(run_dir, tmp_path)

    def test_assert_approved_rejects_false_approval(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalError, assert_approved

        _init_repo(tmp_path)
        run_dir = tmp_path / ".forgerwrite" / "runs" / "run_test"
        run_dir.mkdir(parents=True)
        (run_dir / "approval_record.json").write_text(
            json.dumps(
                {
                    "schema_id": "forgerwrite.approval_record.v1",
                    "run_id": "run_test",
                    "approved": False,
                    "approved_at": "2026-06-06T12:00:00Z",
                    "approval_method": "terminal_cli",
                    "preview_diff_sha256": "a" * 64,
                    "worktree_clean_at_approval": True,
                }
            )
        )

        with pytest.raises(ApprovalError, match="false"):
            assert_approved(run_dir, tmp_path)

    def test_assert_approved_rejects_stale_diff(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalError, assert_approved, write_approval_record

        _init_repo(tmp_path)
        run_dir = tmp_path / ".forgerwrite" / "runs" / "run_test"
        run_dir.mkdir(parents=True)
        (run_dir / "preview.diff").write_text("original diff")
        write_approval_record(run_dir)
        # Modify the diff after approval
        (run_dir / "preview.diff").write_text("modified diff")

        with pytest.raises(ApprovalError, match="stale"):
            assert_approved(run_dir, tmp_path)

    def test_assert_approved_rejects_dirty_worktree(self, tmp_path: Path) -> None:
        from forgerwrite_mcp.approval import ApprovalError, assert_approved, write_approval_record
        from forgerwrite_mcp.forge.git_utils import WorktreeDirtyError

        _init_repo(tmp_path)
        run_dir = tmp_path / ".forgerwrite" / "runs" / "run_test"
        run_dir.mkdir(parents=True)
        (run_dir / "preview.diff").write_text("diff")
        write_approval_record(run_dir)
        # Dirty the worktree
        (tmp_path / "lib.rs").write_text("dirty worktree\n")

        with pytest.raises((ApprovalError, WorktreeDirtyError)):
            assert_approved(run_dir, tmp_path)
