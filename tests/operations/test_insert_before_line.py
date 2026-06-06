"""Tests for InsertBeforeLineHandler."""

from pathlib import Path

import pytest


class TestInsertBeforeLineHandler:
    def test_valid_apply(self, tmp_path: Path) -> None:
        """insert_before_line inserts content before a specified line."""
        from forgerwrite_mcp.operations.insert_before_line import InsertBeforeLineHandler

        f = tmp_path / "lib.rs"
        f.write_text("line1\nline2\nline3\n")
        handler = InsertBeforeLineHandler()
        op = {
            "op": "insert_before_line",
            "path": "lib.rs",
            "before_line": 2,
            "content": "inserted",
        }
        outcome = handler.apply(tmp_path, op)
        assert outcome.path == "lib.rs"
        assert f.read_text() == "line1\ninserted\nline2\nline3\n"

    def test_insert_at_start(self, tmp_path: Path) -> None:
        """insert_before_line at line 1 prepends."""
        from forgerwrite_mcp.operations.insert_before_line import InsertBeforeLineHandler

        f = tmp_path / "lib.rs"
        f.write_text("line1\nline2\n")
        handler = InsertBeforeLineHandler()
        op = {
            "op": "insert_before_line",
            "path": "lib.rs",
            "before_line": 1,
            "content": "prepended",
        }
        handler.apply(tmp_path, op)
        assert f.read_text() == "prepended\nline1\nline2\n"

    def test_rejects_path_escape(self, tmp_path: Path) -> None:
        """insert_before_line rejects path traversal."""
        from forgerwrite_mcp.operations.insert_before_line import InsertBeforeLineHandler
        from forgerwrite_mcp.paths import PathSafetyError

        handler = InsertBeforeLineHandler()
        op = {
            "op": "insert_before_line",
            "path": "../secret.txt",
            "before_line": 1,
            "content": "bad",
        }
        with pytest.raises(PathSafetyError):
            handler.apply(tmp_path, op)

    def test_rejects_missing_target(self, tmp_path: Path) -> None:
        """insert_before_line raises if target file doesn't exist."""
        from forgerwrite_mcp.operations.insert_before_line import InsertBeforeLineHandler
        from forgerwrite_mcp.operations.registry import OperationApplyError

        handler = InsertBeforeLineHandler()
        op = {
            "op": "insert_before_line",
            "path": "nonexistent.rs",
            "before_line": 1,
            "content": "x",
        }
        with pytest.raises(OperationApplyError, match="Target file missing"):
            handler.apply(tmp_path, op)
