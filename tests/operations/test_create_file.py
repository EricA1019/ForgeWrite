"""Tests for CreateFileHandler."""

from pathlib import Path

import pytest


class TestCreateFileHandler:
    def test_valid_apply(self, tmp_path: Path) -> None:
        """create_file creates a new file with content."""
        from forgerwrite_mcp.operations.create_file import CreateFileHandler

        handler = CreateFileHandler()
        op = {"op": "create_file", "path": "src/new_file.rs", "content": "fn hello() {}"}
        outcome = handler.apply(tmp_path, op)
        assert outcome.path == "src/new_file.rs"
        assert outcome.created is True
        assert (tmp_path / "src" / "new_file.rs").read_text() == "fn hello() {}"

    def test_rejects_path_escape(self, tmp_path: Path) -> None:
        """create_file rejects paths that escape the repo root."""
        from forgerwrite_mcp.operations.create_file import CreateFileHandler
        from forgerwrite_mcp.paths import PathSafetyError

        handler = CreateFileHandler()
        op = {"op": "create_file", "path": "../outside.rs", "content": "bad"}
        with pytest.raises(PathSafetyError):
            handler.apply(tmp_path, op)

    def test_rejects_missing_parent_directory(self, tmp_path: Path) -> None:
        """create_file creates parent directories automatically — this should not reject."""
        from forgerwrite_mcp.operations.create_file import CreateFileHandler

        handler = CreateFileHandler()
        op = {
            "op": "create_file",
            "path": "deep/nested/dir/file.txt",
            "content": "content",
        }
        outcome = handler.apply(tmp_path, op)
        assert outcome.created is True
        assert (tmp_path / "deep" / "nested" / "dir" / "file.txt").exists()

    def test_rejects_content_over_limit(self, tmp_path: Path) -> None:
        """create_file rejects content exceeding operation_content_max_bytes."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.operations.create_file import CreateFileHandler
        from forgerwrite_mcp.operations.registry import OperationApplyError

        handler = CreateFileHandler()
        limits = LimitsConfig(operation_content_max_bytes=64)
        op = {
            "op": "create_file",
            "path": "x.rs",
            "content": "x" * 65,  # 65 bytes > 64 limit
        }
        with pytest.raises(OperationApplyError, match="exceeds limit"):
            handler.validate(op, {}, limits)

    def test_validate_passes_on_valid_op(self) -> None:
        """validate does not raise for a valid operation."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.operations.create_file import CreateFileHandler

        handler = CreateFileHandler()
        op = {"op": "create_file", "path": "x.rs", "content": "hello"}
        handler.validate(op, {}, LimitsConfig())
