"""ReplaceLineRangeHandler — replaces a contiguous range of lines in a file.

1-indexed, inclusive. Design reference: §5.5
"""

from pathlib import Path
from typing import Any

from ..config import LimitsConfig
from ..paths import safe_resolve_path
from .registry import ApplyOutcome, OperationApplyError


def _replace_line_range(original: str, start_line: int, end_line: int, content: str) -> str:
    """Replace lines start_line through end_line (1-indexed, inclusive) with content.

    Design §5.5 implementation.
    """
    if start_line < 1 or end_line < start_line:
        raise OperationApplyError(f"Invalid line range {start_line}-{end_line}")
    lines = original.splitlines(keepends=True)
    if end_line > len(lines):
        raise OperationApplyError(f"Range exceeds file length {len(lines)}")
    replacement = content if content.endswith("\n") or not content else content + "\n"
    new = lines[: start_line - 1] + [replacement] + lines[end_line:]
    return "".join(new)


class ReplaceLineRangeHandler:
    op_name: str = "replace_line_range"

    def validate(
        self, operation: dict[str, Any], slice_contract: dict[str, Any], limits: LimitsConfig
    ) -> None:
        if "start_line" not in operation or "end_line" not in operation:
            raise OperationApplyError("Missing start_line/end_line")
        content = operation.get("content") or ""
        if len(content.encode("utf-8")) > limits.operation_content_max_bytes:
            raise OperationApplyError("Operation content exceeds limit")

    def apply(self, repo_root: Path, operation: dict[str, Any]) -> ApplyOutcome:
        path = safe_resolve_path(repo_root, operation["path"])
        if not path.exists():
            raise OperationApplyError(f"Target file missing: {operation['path']}")
        original = path.read_text(encoding="utf-8")
        updated = _replace_line_range(
            original,
            int(operation["start_line"]),
            int(operation["end_line"]),
            operation.get("content") or "",
        )
        path.write_text(updated, encoding="utf-8")
        return ApplyOutcome(path=operation["path"], bytes_written=len(updated.encode("utf-8")))
