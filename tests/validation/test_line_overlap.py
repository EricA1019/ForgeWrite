"""Tests for LineOverlapRule — rejects batches with multiple line-based
operations on the same file."""

from forgerwrite_mcp.validation.semantic import LineOverlapRule


class TestLineOverlapRule:
    def test_rejects_two_line_ops_on_same_file(self) -> None:
        rule = LineOverlapRule()
        batch = {
            "operations": [
                {"op": "insert_before_line", "path": "src/main.rs",
                 "before_line": 10, "content": "use foo;\n"},
                {"op": "replace_line_range", "path": "src/main.rs",
                 "start_line": 5, "end_line": 8, "content": "// x\n"},
            ]
        }
        errors = rule.check(batch, {}, None, None)  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "src/main.rs" in errors[0]
        assert "insert_before_line" in errors[0]

    def test_allows_line_ops_on_different_files(self) -> None:
        rule = LineOverlapRule()
        batch = {
            "operations": [
                {"op": "insert_before_line", "path": "src/main.rs",
                 "before_line": 1, "content": "// header\n"},
                {"op": "replace_line_range", "path": "src/lib.rs",
                 "start_line": 1, "end_line": 3, "content": "pub mod foo;\n"},
            ]
        }
        errors = rule.check(batch, {}, None, None)  # type: ignore[arg-type]
        assert errors == []

    def test_allows_non_line_ops_on_same_file(self) -> None:
        rule = LineOverlapRule()
        batch = {
            "operations": [
                {"op": "create_file", "path": "src/new.rs",
                 "content": "pub fn hello() {}\n"},
                {"op": "replace_file", "path": "src/new.rs",
                 "content": "pub fn updated() {}\n"},
            ]
        }
        errors = rule.check(batch, {}, None, None)  # type: ignore[arg-type]
        assert errors == []

    def test_allows_single_line_op(self) -> None:
        rule = LineOverlapRule()
        batch = {
            "operations": [
                {"op": "insert_after_line", "path": "src/main.rs",
                 "after_line": 42, "content": "// footer\n"},
            ]
        }
        errors = rule.check(batch, {}, None, None)  # type: ignore[arg-type]
        assert errors == []
