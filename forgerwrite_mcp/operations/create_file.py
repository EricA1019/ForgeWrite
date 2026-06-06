"""CreateFileHandler — creates a new file with content."""

from pathlib import Path
from typing import Any

from ..config import LimitsConfig
from ..paths import safe_resolve_path
from .registry import ApplyOutcome, OperationApplyError


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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ApplyOutcome(
            path=operation["path"], bytes_written=len(content.encode("utf-8")), created=True
        )
