"""InsertBeforeLineHandler — inserts content before a specified line number."""

from pathlib import Path
from typing import Any

from ..config import LimitsConfig
from ..paths import safe_resolve_path
from .registry import ApplyOutcome, OperationApplyError


class InsertBeforeLineHandler:
    op_name: str = "insert_before_line"

    def validate(
        self, operation: dict[str, Any], slice_contract: dict[str, Any], limits: LimitsConfig
    ) -> None:
        content = operation.get("content") or ""
        if len(content.encode("utf-8")) > limits.operation_content_max_bytes:
            raise OperationApplyError("Operation content exceeds limit")

    def apply(self, repo_root: Path, operation: dict[str, Any]) -> ApplyOutcome:
        path = safe_resolve_path(repo_root, operation["path"])
        if not path.exists():
            raise OperationApplyError(f"Target file missing: {operation['path']}")
        before_line = int(operation["before_line"])
        content = operation.get("content") or ""
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        # before_line is 1-indexed
        idx = before_line - 1
        if idx < 0:
            idx = 0
        if idx >= len(lines):
            # Append to end
            new_lines = lines + [content + "\n"]
        else:
            new_lines = lines[:idx] + [content + "\n"] + lines[idx:]
        updated = "".join(new_lines)
        path.write_text(updated, encoding="utf-8")
        return ApplyOutcome(path=operation["path"], bytes_written=len(updated.encode("utf-8")))
