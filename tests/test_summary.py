"""Tests for the run summary module."""

from pathlib import Path


class TestSummary:
    """Tests for generate_summary()."""

    def test_generate_summary_produces_markdown(self, tmp_path: Path) -> None:
        """generate_summary returns a Markdown string with a header."""
        from forgerwrite_mcp.summary import generate_summary

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        # Write minimal artifacts
        (run_dir / "resolved_contracts.json").write_text("{}")
        summary = generate_summary(run_dir)
        assert summary.startswith("# Run Summary")
        assert "## Run Artifacts" in summary

    def test_generate_summary_includes_run_id(self, tmp_path: Path) -> None:
        """Summary includes the run_id from the directory name."""
        from forgerwrite_mcp.summary import generate_summary

        run_dir = tmp_path / "run_20250101_0001"
        run_dir.mkdir()
        (run_dir / "resolved_contracts.json").write_text("{}")
        summary = generate_summary(run_dir)
        assert "run_20250101_0001" in summary

    def test_generate_summary_lists_artifacts(self, tmp_path: Path) -> None:
        """Summary lists available artifact files with sizes."""
        from forgerwrite_mcp.summary import generate_summary

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        (run_dir / "resolved_contracts.json").write_text('{"key": "value"}')
        (run_dir / "preview.diff").write_text("diff content")
        (run_dir / "audit.jsonl").write_text(
            '{"event_type":"approve","timestamp":"ts","details":{}}\n'
            '{"event_type":"apply","timestamp":"ts","details":{}}\n'
        )
        summary = generate_summary(run_dir)
        assert "resolved_contracts.json" in summary
        assert "preview.diff" in summary
        assert "audit.jsonl" in summary
        # Should mention audit event count
        assert "2" in summary  # 2 events

    def test_generate_summary_includes_errors(self, tmp_path: Path) -> None:
        """Dead letter is surfaced prominently in summary."""
        from forgerwrite_mcp.summary import generate_summary

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        (run_dir / "resolved_contracts.json").write_text("{}")
        (run_dir / "dead_letter.json").write_text(
            '{"reason": "Something failed", "timestamp": "ts"}'
        )
        summary = generate_summary(run_dir)
        assert "dead_letter.json" in summary
        assert "Something failed" in summary

    def test_generate_summary_handles_missing_artifacts(self, tmp_path: Path) -> None:
        """Summary handles empty/missing artifact gracefully."""
        from forgerwrite_mcp.summary import generate_summary

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        # No artifacts at all — should not crash
        summary = generate_summary(run_dir)
        assert "Run Summary" in summary
