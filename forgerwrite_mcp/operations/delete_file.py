"""DeleteFileHandler — deletes an existing file."""

from pathlib import Path
from typing import Any

from ..config import LimitsConfig
from ..paths import safe_resolve_path
from .registry import ApplyOutcome, OperationApplyError


class DeleteFileHandler:
    op_name: str = "delete_file"

    def validate(
        self, operation: dict[str, Any], slice_contract: dict[str, Any], limits: LimitsConfig
    ) -> None:
        # No content to validate for delete
        pass

    def apply(self, repo_root: Path, operation: dict[str, Any]) -> ApplyOutcome:
        path = safe_resolve_path(repo_root, operation["path"])
        if not path.exists():
            raise OperationApplyError(f"Target file missing: {operation['path']}")
        path.unlink()
        return ApplyOutcome(path=operation["path"], bytes_written=0, deleted=True)
