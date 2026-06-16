"""Tests for token usage tracking and cost savings reporting."""

from __future__ import annotations

from pathlib import Path

import pytest

# ── Constants ────────────────────────────────────────────────────────────────

_CLAUDE_COST_PER_M_INPUT = 3.0  # Claude 3.5 Sonnet: $3/M input tokens
_CLAUDE_COST_PER_M_OUTPUT = 15.0  # Claude 3.5 Sonnet: $15/M output tokens


# ── TokenTracker tests ───────────────────────────────────────────────────────


class TestTokenTracker:
    """TokenTracker appends usage records to a JSONL file."""

    def test_record_writes_jsonl_line(self, tmp_path: Path) -> None:
        """Recording a token usage writes a JSONL line."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        tracker.record(
            prompt_tokens=150,
            completion_tokens=300,
            model_name="gemma4-12b",
            purpose="generate_operations",
        )

        lines = (tmp_path / "token_usage.jsonl").read_text().strip().split("\n")
        assert len(lines) == 1

        import json

        record = json.loads(lines[0])
        assert record["prompt_tokens"] == 150
        assert record["completion_tokens"] == 300
        assert record["total_tokens"] == 450
        assert record["model_name"] == "gemma4-12b"
        assert record["purpose"] == "generate_operations"
        assert "timestamp" in record

    def test_multiple_records_append(self, tmp_path: Path) -> None:
        """Multiple records append to the same file."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        tracker.record(100, 50, "gemma4", "purpose-a")
        tracker.record(200, 100, "gemma4", "purpose-b")

        lines = (tmp_path / "token_usage.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2

    def test_get_stats_empty(self, tmp_path: Path) -> None:
        """Stats from an empty tracker returns zeros."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        stats = tracker.get_stats()
        assert stats["total_calls"] == 0
        assert stats["total_input_tokens"] == 0
        assert stats["total_output_tokens"] == 0

    def test_get_stats_with_records(self, tmp_path: Path) -> None:
        """Stats aggregate multiple records correctly."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        tracker.record(100, 50, "gemma4", "purpose-a")
        tracker.record(200, 100, "gemma4", "purpose-b")
        tracker.record(300, 150, "gemma4", "purpose-a")

        stats = tracker.get_stats()
        assert stats["total_calls"] == 3
        assert stats["total_input_tokens"] == 600
        assert stats["total_output_tokens"] == 300
        assert stats["total_tokens"] == 900

    def test_get_stats_by_purpose(self, tmp_path: Path) -> None:
        """Stats break down by purpose."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        tracker.record(100, 50, "gemma4", "purpose-a")
        tracker.record(200, 100, "gemma4", "purpose-b")
        tracker.record(50, 25, "gemma4", "purpose-a")

        stats = tracker.get_stats()
        by_purpose = stats["by_purpose"]
        assert by_purpose["purpose-a"]["calls"] == 2
        assert by_purpose["purpose-a"]["total_tokens"] == 225
        assert by_purpose["purpose-b"]["calls"] == 1

    def test_estimated_savings(self, tmp_path: Path) -> None:
        """Stats include estimated cost savings vs cloud APIs."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        # 1M input + 500K output tokens
        tracker.record(1_000_000, 500_000, "gemma4", "test")

        stats = tracker.get_stats()
        assert "estimated_savings" in stats
        savings = stats["estimated_savings"]
        # Claude: $3/M input + $15/M output = $3 + $7.50 = $10.50
        assert savings["claude"]["input_cost"] == pytest.approx(3.0, rel=0.1)
        assert savings["claude"]["output_cost"] == pytest.approx(7.50, rel=0.1)
        assert savings["claude"]["total"] == pytest.approx(10.50, rel=0.1)
        # GPT-4o: $2.50/M input + $10/M output = $2.50 + $5 = $7.50
        assert savings["gpt4o"]["total"] == pytest.approx(7.50, rel=0.1)

    def test_tracker_file_does_not_exist_initially(self, tmp_path: Path) -> None:
        """Tracker doesn't create the file until a record is written."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        assert not (tmp_path / "token_usage.jsonl").exists()
        # Stats should still work
        stats = tracker.get_stats()
        assert stats["total_calls"] == 0


class TestTokenTrackerByModel:
    """Per-model breakdown in stats."""

    def test_by_model_breakdown(self, tmp_path: Path) -> None:
        """Stats include per-model breakdown."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        tracker.record(500, 200, "gemma4-12b", "generate")
        tracker.record(300, 100, "gemma4-12b", "generate")
        tracker.record(150, 50, "omnicoder-9b", "scout")

        stats = tracker.get_stats()
        by_model = stats["by_model"]
        assert by_model["gemma4-12b"]["calls"] == 2
        assert by_model["gemma4-12b"]["total_tokens"] == 1100
        assert by_model["omnicoder-9b"]["calls"] == 1
        assert by_model["omnicoder-9b"]["total_tokens"] == 200

    def test_by_model_empty(self, tmp_path: Path) -> None:
        """Empty tracker has by_model with no entries."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        stats = tracker.get_stats()
        assert "by_model" in stats
        assert stats["by_model"] == {}

    def test_empty_stats_has_all_required_keys(self, tmp_path: Path) -> None:
        """Zero-record stats must include every key that populated stats have."""
        from forgerwrite_mcp.token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=tmp_path)
        empty = tracker.get_stats()

        # Add one record to get populated
        tracker.record(100, 50, "test-model", "test-purpose")
        populated = tracker.get_stats()

        for key in populated:
            assert key in empty, f"Key '{key}' missing from empty stats"
