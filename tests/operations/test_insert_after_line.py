"""Tests for InsertAfterLineHandler."""

from pathlib import Path

import pytest


class TestInsertAfterLineHandler:
    def test_valid_apply(self, tmp_path: Path) -> None:
        """insert_after_line inserts content after a specified line."""
        from forgerwrite_mcp.operations.insert_after_line import InsertAfterLineHandler

        f = tmp_path / "lib.rs"
        f.write_text("line1\nline2\nline3\n")
        handler = InsertAfterLineHandler()
        op = {
            "op": "insert_after_line",
            "path": "lib.rs",
            "after_line": 2,
            "content": "inserted",
        }
        outcome = handler.apply(tmp_path, op)
        assert outcome.path == "lib.rs"
        assert f.read_text() == "line1\nline2\ninserted\nline3\n"

    def test_insert_at_end(self, tmp_path: Path) -> None:
        """insert_after_line at last line appends to end."""
        from forgerwrite_mcp.operations.insert_after_line import InsertAfterLineHandler

        f = tmp_path / "lib.rs"
        f.write_text("line1\nline2\n")
        handler = InsertAfterLineHandler()
        op = {
            "op": "insert_after_line",
            "path": "lib.rs",
            "after_line": 2,
            "content": "appended",
        }
        handler.apply(tmp_path, op)
        assert f.read_text() == "line1\nline2\nappended\n"

    def test_rejects_path_escape(self, tmp_path: Path) -> None:
        """insert_after_line rejects path traversal."""
        from forgerwrite_mcp.operations.insert_after_line import InsertAfterLineHandler
        from forgerwrite_mcp.paths import PathSafetyError

        handler = InsertAfterLineHandler()
        op = {
            "op": "insert_after_line",
            "path": "../secret.txt",
            "after_line": 1,
            "content": "bad",
        }
        with pytest.raises(PathSafetyError):
            handler.apply(tmp_path, op)

    def test_rejects_missing_target(self, tmp_path: Path) -> None:
        """insert_after_line raises if target file doesn't exist."""
        from forgerwrite_mcp.operations.insert_after_line import InsertAfterLineHandler
        from forgerwrite_mcp.operations.registry import OperationApplyError

        handler = InsertAfterLineHandler()
        op = {
            "op": "insert_after_line",
            "path": "nonexistent.rs",
            "after_line": 1,
            "content": "x",
        }
        with pytest.raises(OperationApplyError, match="Target file missing"):
            handler.apply(tmp_path, op)
