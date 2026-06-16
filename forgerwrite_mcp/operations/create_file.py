"""CreateFileHandler — creates a new file with content."""

from pathlib import Path
from typing import Any

from ..config import LimitsConfig
from ..paths import safe_resolve_path
from .registry import ApplyOutcome, OperationApplyError

# ── Hard cap (belt-and-suspenders, checked in apply() too) ──────────────────

_MAX_CONTENT_BYTES: int = 200_000


class CreateFileHandler:
    op_name: str = "create_file"

    def validate(
        self, operation: dict[str, Any], slice_contract: dict[str, Any], limits: LimitsConfig
    ) -> None:
        content = operation.get("content") or ""
        if len(content.encode("utf-8")) > limits.operation_content_max_bytes:
            raise OperationApplyError("Operation content exceeds limit")

    def apply(self, repo_root: Path, operation: dict[str, Any]) -> ApplyOutcome:
        path = safe_resolve_path(repo_root, operation["path"])
        content = operation.get("content") or ""
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > _MAX_CONTENT_BYTES:
            raise OperationApplyError(
                f"Content too large: {content_bytes} bytes exceeds "
                f"{_MAX_CONTENT_BYTES} byte limit"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ApplyOutcome(
            path=operation["path"], bytes_written=content_bytes, created=True
        )
