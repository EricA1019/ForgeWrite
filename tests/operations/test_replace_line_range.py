"""Tests for ReplaceLineRangeHandler."""

from pathlib import Path

import pytest


class TestReplaceLineRangeHandler:
    def test_valid_apply(self, tmp_path: Path) -> None:
        """replace_line_range replaces a contiguous line range."""
        from forgerwrite_mcp.operations.replace_line_range import ReplaceLineRangeHandler

        f = tmp_path / "lib.rs"
        f.write_text("line1\nline2\nline3\nline4\n")
        handler = ReplaceLineRangeHandler()
        op = {
            "op": "replace_line_range",
            "path": "lib.rs",
            "start_line": 2,
            "end_line": 3,
            "content": "replacement",
        }
        outcome = handler.apply(tmp_path, op)
        assert outcome.path == "lib.rs"
        assert f.read_text() == "line1\nreplacement\nline4\n"

    def test_rejects_invalid_range(self, tmp_path: Path) -> None:
        """replace_line_range rejects start_line < 1 or end_line < start_line."""
        from forgerwrite_mcp.operations.registry import OperationApplyError
        from forgerwrite_mcp.operations.replace_line_range import ReplaceLineRangeHandler

        f = tmp_path / "lib.rs"
        f.write_text("a\nb\n")
        handler = ReplaceLineRangeHandler()
        op = {
            "op": "replace_line_range",
            "path": "lib.rs",
            "start_line": 0,
            "end_line": 1,
            "content": "x",
        }
        with pytest.raises(OperationApplyError, match="Invalid line range"):
            handler.apply(tmp_path, op)

    def test_rejects_range_exceeds_file_length(self, tmp_path: Path) -> None:
        """replace_line_range rejects end_line beyond file length."""
        from forgerwrite_mcp.operations.registry import OperationApplyError
        from forgerwrite_mcp.operations.replace_line_range import ReplaceLineRangeHandler

        f = tmp_path / "lib.rs"
        f.write_text("only 2 lines\nstill 2\n")
        handler = ReplaceLineRangeHandler()
        op = {
            "op": "replace_line_range",
            "path": "lib.rs",
            "start_line": 1,
            "end_line": 10,
            "content": "x",
        }
        with pytest.raises(OperationApplyError, match="exceeds file length"):
            handler.apply(tmp_path, op)

    def test_rejects_missing_target(self, tmp_path: Path) -> None:
        """replace_line_range raises if the target file doesn't exist."""
        from forgerwrite_mcp.operations.registry import OperationApplyError
        from forgerwrite_mcp.operations.replace_line_range import ReplaceLineRangeHandler

        handler = ReplaceLineRangeHandler()
        op = {
            "op": "replace_line_range",
            "path": "nonexistent.rs",
            "start_line": 1,
            "end_line": 2,
            "content": "x",
        }
        with pytest.raises(OperationApplyError, match="Target file missing"):
            handler.apply(tmp_path, op)

    def test_validate_rejects_content_over_limit(self) -> None:
        """replace_line_range rejects content over the size limit."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.operations.registry import OperationApplyError
        from forgerwrite_mcp.operations.replace_line_range import ReplaceLineRangeHandler

        handler = ReplaceLineRangeHandler()
        limits = LimitsConfig(operation_content_max_bytes=64)
        op = {
            "op": "replace_line_range",
            "path": "x.rs",
            "start_line": 1,
            "end_line": 2,
            "content": "x" * 65,
        }
        with pytest.raises(OperationApplyError, match="exceeds limit"):
            handler.validate(op, {}, limits)
