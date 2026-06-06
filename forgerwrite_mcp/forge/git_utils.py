"""Git utility functions for the Forge safety layer.

Handles worktree cleanliness checks, snapshot creation, cleanup, and restore.
All subprocess calls use shell=False.

Design reference: §5.6, ADR-004
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..errors import APPROVAL_ERROR, PublicError

# Snapshot ref namespace
_SNAPSHOT_REF_PREFIX: str = "refs/forgerwrite"


def _snapshot_ref(run_id: str) -> str:
    """Construct a snapshot ref name for a run ID."""
    return f"{_SNAPSHOT_REF_PREFIX}/{run_id}"


class WorktreeDirtyError(PublicError):
    """The git worktree is not clean — mutation rejected."""

    def __init__(self, message: str = "Worktree is not clean") -> None:
        super().__init__(code=APPROVAL_ERROR, message=message)


def assert_clean_worktree(repo_root: Path) -> None:
    """Assert the git worktree is clean (no uncommitted changes).

    Runs `git status --porcelain` and raises WorktreeDirtyError
    if any output is produced.

    Design: ADR-004 — required before preview and apply.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    # Filter out .forgerwrite/ lines (artifacts dir is expected)
    dirty_lines = [
        line for line in result.stdout.strip().split("\n") if line and ".forgerwrite" not in line
    ]
    if dirty_lines:
        raise WorktreeDirtyError("Worktree is not clean:\n" + "\n".join(dirty_lines))


def create_snapshot(repo_root: Path, run_id: str) -> str:
    """Create a git snapshot of HEAD for a run.

    The snapshot is stored as a lightweight ref under refs/forgerwrite/<run_id>.
    Returns the full ref name.

    Raises subprocess.CalledProcessError on git failure.
    """
    ref = _snapshot_ref(run_id)
    subprocess.run(
        ["git", "update-ref", ref, "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return ref


def cleanup_snapshot(repo_root: Path, run_id: str) -> None:
    """Delete the snapshot ref for a run.

    Safe to call even if the ref doesn't exist.
    """
    ref = _snapshot_ref(run_id)
    subprocess.run(
        ["git", "update-ref", "-d", ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        # Don't use check=True — ref might not exist
    )


def restore_snapshot(repo_root: Path, run_id: str) -> None:
    """Restore the working tree to the snapshot state.

    Reverts tracked files to the snapshot and removes untracked files
    (except .forgerwrite/) created since the snapshot.
    """
    ref = _snapshot_ref(run_id)
    # Reset tracked files to snapshot state
    subprocess.run(
        ["git", "read-tree", ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "checkout-index", "-f", "-a"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    # Remove new untracked files (but not .forgerwrite/)
    subprocess.run(
        ["git", "clean", "-fd", "-e", ".forgerwrite"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
