"""Tests for DeleteFileHandler."""

from pathlib import Path

import pytest


class TestDeleteFileHandler:
    def test_valid_apply(self, tmp_path: Path) -> None:
        """delete_file removes an existing file."""
        from forgerwrite_mcp.operations.delete_file import DeleteFileHandler

        f = tmp_path / "to_delete.rs"
        f.write_text("content")
        handler = DeleteFileHandler()
        op = {"op": "delete_file", "path": "to_delete.rs"}
        outcome = handler.apply(tmp_path, op)
        assert outcome.path == "to_delete.rs"
        assert outcome.deleted is True
        assert not f.exists()

    def test_rejects_path_escape(self, tmp_path: Path) -> None:
        """delete_file rejects path traversal."""
        from forgerwrite_mcp.operations.delete_file import DeleteFileHandler
        from forgerwrite_mcp.paths import PathSafetyError

        handler = DeleteFileHandler()
        op = {"op": "delete_file", "path": "../important.txt"}
        with pytest.raises(PathSafetyError):
            handler.apply(tmp_path, op)

    def test_rejects_missing_target(self, tmp_path: Path) -> None:
        """delete_file raises if target file doesn't exist."""
        from forgerwrite_mcp.operations.delete_file import DeleteFileHandler
        from forgerwrite_mcp.operations.registry import OperationApplyError

        handler = DeleteFileHandler()
        op = {"op": "delete_file", "path": "nonexistent.rs"}
        with pytest.raises(OperationApplyError, match="Target file missing"):
            handler.apply(tmp_path, op)
