"""Tests for the audit events module."""

import json
from pathlib import Path

import pytest


class TestAudit:
    """Tests for write_audit_event()."""

    def test_write_audit_event_creates_file(self, tmp_path: Path) -> None:
        """write_audit_event writes an audit event to a run directory."""
        from forgerwrite_mcp.audit import write_audit_event

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        write_audit_event(run_dir, "approve", {"user": "test"})
        # Should create or append to an audit log
        audit_path = run_dir / "audit.jsonl"
        assert audit_path.exists()

    def test_audit_event_has_required_fields(self, tmp_path: Path) -> None:
        """Each audit event has event_type, timestamp, and details."""
        from forgerwrite_mcp.audit import write_audit_event

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        write_audit_event(run_dir, "apply", {"files": 3})
        line = (run_dir / "audit.jsonl").read_text().strip()
        event = json.loads(line)
        assert event["event_type"] == "apply"
        assert "timestamp" in event
        assert event["details"] == {"files": 3}

    def test_multiple_events_append_to_same_file(self, tmp_path: Path) -> None:
        """Multiple audit events append to the same audit.jsonl file."""
        from forgerwrite_mcp.audit import write_audit_event

        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        write_audit_event(run_dir, "approve")
        write_audit_event(run_dir, "apply")
        write_audit_event(run_dir, "restore")
        lines = (run_dir / "audit.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3
        events = [json.loads(l) for l in lines]
        assert [e["event_type"] for e in events] == ["approve", "apply", "restore"]
