"""Tests for ReplaceFileHandler."""

from pathlib import Path

import pytest


class TestReplaceFileHandler:
    def test_valid_apply(self, tmp_path: Path) -> None:
        """replace_file replaces an existing file's content."""
        from forgerwrite_mcp.operations.replace_file import ReplaceFileHandler

        f = tmp_path / "lib.rs"
        f.write_text("old content")
        handler = ReplaceFileHandler()
        op = {"op": "replace_file", "path": "lib.rs", "content": "new content"}
        outcome = handler.apply(tmp_path, op)
        assert outcome.path == "lib.rs"
        assert f.read_text() == "new content"

    def test_rejects_missing_target(self, tmp_path: Path) -> None:
        """replace_file raises if the target file doesn't exist."""
        from forgerwrite_mcp.operations.registry import OperationApplyError
        from forgerwrite_mcp.operations.replace_file import ReplaceFileHandler

        handler = ReplaceFileHandler()
        op = {"op": "replace_file", "path": "nonexistent.rs", "content": "x"}
        with pytest.raises(OperationApplyError, match="Target file missing"):
            handler.apply(tmp_path, op)

    def test_rejects_path_escape(self, tmp_path: Path) -> None:
        """replace_file rejects paths that escape the repo."""
        from forgerwrite_mcp.operations.replace_file import ReplaceFileHandler
        from forgerwrite_mcp.paths import PathSafetyError

        handler = ReplaceFileHandler()
        op = {"op": "replace_file", "path": "../secret.txt", "content": "bad"}
        with pytest.raises(PathSafetyError):
            handler.apply(tmp_path, op)

    def test_rejects_content_over_limit(self) -> None:
        """replace_file rejects content over the size limit."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.operations.registry import OperationApplyError
        from forgerwrite_mcp.operations.replace_file import ReplaceFileHandler

        handler = ReplaceFileHandler()
        limits = LimitsConfig(operation_content_max_bytes=64)
        op = {"op": "replace_file", "path": "x.rs", "content": "x" * 65}
        with pytest.raises(OperationApplyError, match="exceeds limit"):
            handler.validate(op, {}, limits)
