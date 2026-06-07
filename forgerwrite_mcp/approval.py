"""Approval Store — hash-bound, TOCTOU-safe approval records.

Design reference: §5.7
"""

from __future__ import annotations

import fcntl
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from .errors import APPROVAL_ERROR, PublicError
from .forge.git_utils import assert_clean_worktree


class ApprovalError(PublicError):
    """Approval is missing, rejected, or stale."""

    def __init__(self, message: str) -> None:
        super().__init__(code=APPROVAL_ERROR, message=message)


class ApprovalRecord(BaseModel):
    """An approval bound to a specific preview diff hash."""

    schema_id: str = "forgerwrite.approval_record.v1"
    run_id: str
    approved: bool
    approved_at: str
    approval_method: str
    preview_diff_sha256: str
    worktree_clean_at_approval: bool = True


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_approval_record(run_dir: Path) -> Path:
    """Write an approval record bound to the current preview.diff hash.

    Uses file locking for concurrent-terminal safety.
    """
    diff_path = run_dir / "preview.diff"
    if not diff_path.exists():
        raise ApprovalError(f"preview.diff missing: {diff_path}")

    record = ApprovalRecord(
        run_id=run_dir.name,
        approved=True,
        approved_at=datetime.now(UTC).isoformat(),
        approval_method="terminal_cli",
        preview_diff_sha256=_sha256_file(diff_path),
        worktree_clean_at_approval=True,
    )
    out = run_dir / "approval_record.json"
    with out.open("w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(record.model_dump_json(indent=2) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    from .audit import write_audit_event

    write_audit_event(run_dir, "approve", {"run_id": run_dir.name})
    return out


def assert_approved(run_dir: Path, repo_root: Path) -> ApprovalRecord:
    """Verify that a run has been approved and the approval is not stale.

    TOCTOU guard: re-checks worktree cleanliness before trusting the record.
    Verifies that preview.diff hasn't changed since approval.
    """
    # TOCTOU: re-check worktree
    assert_clean_worktree(repo_root)

    p = run_dir / "approval_record.json"
    if not p.exists():
        raise ApprovalError(f"Run not approved: {run_dir.name}")

    try:
        record = ApprovalRecord.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ApprovalError(f"Invalid approval record: {p}") from exc

    if not record.approved:
        raise ApprovalError(f"Run approval is false: {run_dir.name}")

    current_hash = _sha256_file(run_dir / "preview.diff")
    if current_hash != record.preview_diff_sha256:
        raise ApprovalError("Approval is stale: preview.diff changed after approval")

    return record
