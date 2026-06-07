"""Tests for the dead letter module."""

import json
from pathlib import Path


class TestDeadLetter:
    """Tests for write_dead_letter()."""

    def test_write_dead_letter_creates_file(self, tmp_path: Path) -> None:
        """write_dead_letter writes a dead_letter.json file."""
        from forgerwrite_mcp.dead_letter import write_dead_letter

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        write_dead_letter(run_dir, "Test failure", {"detail": "extra"})
        dl_path = run_dir / "dead_letter.json"
        assert dl_path.exists()
        data = json.loads(dl_path.read_text())
        assert data["reason"] == "Test failure"
        assert "timestamp" in data

    def test_write_dead_letter_stores_timestamp(self, tmp_path: Path) -> None:
        """Dead letter includes an ISO timestamp."""
        from forgerwrite_mcp.dead_letter import write_dead_letter

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        write_dead_letter(run_dir, "reason")
        data = json.loads((run_dir / "dead_letter.json").read_text())
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format

    def test_write_dead_letter_payload_is_optional(self, tmp_path: Path) -> None:
        """payload is optional; defaults to empty dict."""
        from forgerwrite_mcp.dead_letter import write_dead_letter

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        write_dead_letter(run_dir, "reason only")
        data = json.loads((run_dir / "dead_letter.json").read_text())
        assert "payload" in data
