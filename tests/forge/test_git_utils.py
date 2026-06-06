"""Tests for git utility functions."""

import subprocess
from pathlib import Path

import pytest


def _git_init(path: Path) -> None:
    """Initialize a git repo at the given path."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True
    )


def _make_commit(path: Path, filename: str) -> None:
    """Create a file and commit it."""
    f = path / filename
    f.write_text("initial content\n", encoding="utf-8")
    subprocess.run(["git", "add", filename], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"add {filename}"], cwd=path, check=True, capture_output=True
    )


class TestAssertCleanWorktree:
    """Tests for assert_clean_worktree()."""

    def test_assert_clean_worktree_passes_on_clean_repo(self, tmp_path: Path) -> None:
        """A freshly committed repo is clean."""
        from forgerwrite_mcp.forge.git_utils import assert_clean_worktree

        _git_init(tmp_path)
        _make_commit(tmp_path, "README.md")
        # Should not raise
        assert_clean_worktree(tmp_path)

    def test_assert_clean_worktree_fails_on_dirty_repo(self, tmp_path: Path) -> None:
        """A repo with uncommitted changes raises WorktreeDirtyError."""
        from forgerwrite_mcp.forge.git_utils import (
            WorktreeDirtyError,
            assert_clean_worktree,
        )

        _git_init(tmp_path)
        _make_commit(tmp_path, "README.md")
        (tmp_path / "README.md").write_text("modified content\n", encoding="utf-8")
        with pytest.raises(WorktreeDirtyError):
            assert_clean_worktree(tmp_path)


class TestSnapshot:
    """Tests for create_snapshot, cleanup_snapshot, restore_snapshot."""

    def test_create_snapshot_creates_ref(self, tmp_path: Path) -> None:
        """create_snapshot creates a git ref in refs/forgerwrite/."""
        from forgerwrite_mcp.forge.git_utils import create_snapshot

        _git_init(tmp_path)
        _make_commit(tmp_path, "lib.rs")
        ref = create_snapshot(tmp_path, "run_20260606_0001")
        assert ref.startswith("refs/forgerwrite/run_20260606_0001")
        # Verify the ref exists
        result = subprocess.run(
            ["git", "show-ref", "--verify", ref], cwd=tmp_path, capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_cleanup_snapshot_removes_ref(self, tmp_path: Path) -> None:
        """cleanup_snapshot deletes the snapshot ref."""
        from forgerwrite_mcp.forge.git_utils import cleanup_snapshot, create_snapshot

        _git_init(tmp_path)
        _make_commit(tmp_path, "lib.rs")
        create_snapshot(tmp_path, "run_test")
        cleanup_snapshot(tmp_path, "run_test")
        # Verify the ref is gone
        result = subprocess.run(
            ["git", "show-ref", "--verify", "refs/forgerwrite/run_test"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_restore_snapshot_reverts_changes(self, tmp_path: Path) -> None:
        """restore_snapshot restores files to the snapshot state."""
        from forgerwrite_mcp.forge.git_utils import (
            create_snapshot,
            restore_snapshot,
        )

        _git_init(tmp_path)
        _make_commit(tmp_path, "lib.rs")
        original = (tmp_path / "lib.rs").read_text()
        create_snapshot(tmp_path, "run_test")
        # Modify the file
        (tmp_path / "lib.rs").write_text("corrupted content\n", encoding="utf-8")
        # Restore
        restore_snapshot(tmp_path, "run_test")
        assert (tmp_path / "lib.rs").read_text() == original

    def test_snapshot_create_cleanup_round_trip_no_stray_refs(self, tmp_path: Path) -> None:
        """Creating and cleaning up a snapshot leaves no side effects on git state."""
        from forgerwrite_mcp.forge.git_utils import cleanup_snapshot, create_snapshot

        _git_init(tmp_path)
        _make_commit(tmp_path, "lib.rs")

        # Get refs before
        before = subprocess.run(
            ["git", "show-ref"], cwd=tmp_path, capture_output=True, text=True
        ).stdout

        create_snapshot(tmp_path, "run_test")
        cleanup_snapshot(tmp_path, "run_test")

        # Get refs after
        after = subprocess.run(
            ["git", "show-ref"], cwd=tmp_path, capture_output=True, text=True
        ).stdout

        assert before == after
