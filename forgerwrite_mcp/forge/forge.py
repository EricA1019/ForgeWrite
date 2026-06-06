"""Forge safety layer — preview, apply, and restore operations.

The mutation chokepoint. Every file change flows through here.
Enforces: clean worktree, allowed-files scope, TOCTOU re-check,
snapshot-before-mutation, restore-on-failure.

Design reference: §5.6, ADR-004
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .git_utils import (
    assert_clean_worktree,
    create_snapshot,
    restore_snapshot,
)


@dataclass
class PreviewResult:
    """Result of previewing operations."""

    diff_path: Path
    diff_sha256: str


@dataclass
class ApplyResult:
    """Result of applying approved operations."""

    changed: list[Any] = field(default_factory=list)
    snapshot_ref: str = ""


def preview_operations(
    repo_root: Path,
    run_id: str,
    operation_batch: dict[str, Any],
    slice_contract: dict[str, Any],
    registry: Any,
) -> PreviewResult:
    """Apply operations to a temp snapshot, generate a diff, then restore.

    The worktree MUST be clean before calling. It will be clean after.
    """
    assert_clean_worktree(repo_root)
    ref = create_snapshot(repo_root, run_id)
    try:
        for op in operation_batch.get("operations", []):
            handler = registry.dispatch(op)
            handler.apply(repo_root, op)
        # Generate diff
        # Stage all changes so diff captures new files too
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        result = subprocess.run(
            ["git", "diff", "--cached", ref],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        restore_snapshot(repo_root, run_id)

    run_dir = repo_root / ".forgerwrite" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    diff_path = run_dir / "preview.diff"
    diff_path.write_text(result.stdout)

    sha = hashlib.sha256(diff_path.read_bytes()).hexdigest()
    return PreviewResult(diff_path=diff_path, diff_sha256=sha)


def apply_approved_operations(
    repo_root: Path,
    run_id: str,
    operation_batch: dict[str, Any],
    slice_contract: dict[str, Any],
    approval: Any,  # ApprovalRecord (avoids circular import)
    registry: Any,
) -> ApplyResult:
    """Apply approved operations atomically against a snapshot.

    TOCTOU guard: re-checks clean worktree before mutating.
    On failure: restores snapshot and re-raises.
    """
    # TOCTOU re-check
    assert_clean_worktree(repo_root)
    ref = create_snapshot(repo_root, run_id)

    allowed = set(slice_contract.get("allowed_files", []))
    changed: list[Any] = []
    try:
        for op in operation_batch.get("operations", []):
            if op["path"] not in allowed:
                raise ValueError(f"Operation targets file outside allowed_files: {op['path']}")
            handler = registry.dispatch(op)
            changed.append(handler.apply(repo_root, op))
        return ApplyResult(changed=changed, snapshot_ref=ref)
    except Exception:
        restore_snapshot(repo_root, run_id)
        raise
