"""Audit Analyzer — reads ForgeWrite audit logs and produces reports.

Scans ``.forgerwrite/runs/*/audit.jsonl`` files, aggregates statistics,
and outputs JSON or Markdown reports.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

_AUDIT_DIR: str = ".forgerwrite/runs"
_AUDIT_FILE: str = "audit.jsonl"


# ── Public API ───────────────────────────────────────────────────────────────


def analyze(repo_root: Path) -> dict[str, Any]:
    """Analyze all audit logs in the project.

    Returns a dict with total counts, per-run breakdown, event timeline,
    and per-type statistics.
    """
    runs_dir = repo_root / _AUDIT_DIR
    if not runs_dir.is_dir():
        return _empty_result()

    all_events: list[dict[str, Any]] = []
    runs_analyzed: list[str] = []

    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        audit_path = run_dir / _AUDIT_FILE
        if not audit_path.exists():
            continue
        events = _read_jsonl(audit_path)
        if events:
            all_events.extend(events)
            runs_analyzed.append(run_dir.name)

    if not all_events:
        return _empty_result()

    by_type: dict[str, int] = defaultdict(int)
    for e in all_events:
        by_type[e.get("event_type", e.get("action", "unknown"))] += 1

    by_run: dict[str, int] = defaultdict(int)
    for e in all_events:
        details = e.get("details", {}) if isinstance(e.get("details"), dict) else {}
        by_run[details.get("run_id", e.get("run_id", "unknown"))] += 1

    timeline = sorted(all_events, key=lambda e: e.get("timestamp", ""))

    first_ts = timeline[0].get("timestamp", "unknown") if timeline else "unknown"
    last_ts = timeline[-1].get("timestamp", "unknown") if timeline else "unknown"

    return {
        "total_runs": len(runs_analyzed),
        "total_events": len(all_events),
        "events_by_type": dict(by_type),
        "events_by_run": dict(by_run),
        "first_event": first_ts,
        "last_event": last_ts,
        "runs_analyzed": runs_analyzed,
        "events": timeline,
    }


def report_markdown(analysis: dict[str, Any]) -> str:
    """Render analysis as a Markdown report."""
    lines = [
        "# Audit Report",
        "",
        f"**Runs analyzed:** {analysis['total_runs']}",
        f"**Total events:** {analysis['total_events']}",
        f"**Date range:** {analysis['first_event']} → {analysis['last_event']}",
        "",
        "## Events by Type",
        "",
    ]
    for action, count in sorted(analysis["events_by_type"].items()):
        lines.append(f"- **{action}**: {count}")

    lines.extend(["", "## Events by Run", ""])
    for run_id, count in sorted(analysis["events_by_run"].items()):
        lines.append(f"- `{run_id}`: {count} events")

    lines.extend(["", "## Recent Events", ""])
    for event in analysis["events"][-20:]:
        ts = event.get("timestamp", "?")
        action = event.get("event_type", event.get("action", "?"))
        details = event.get("details", {}) if isinstance(event.get("details"), dict) else {}
        run_id = details.get("run_id", event.get("run_id", "?"))
        lines.append(f"- `{ts}` | **{action}** | `{run_id}`")

    return "\n".join(lines)


# ── Internal ─────────────────────────────────────────────────────────────────


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file, returning valid JSON lines."""
    events: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except (OSError, UnicodeDecodeError):
        pass
    return events


def _empty_result() -> dict[str, Any]:
    return {
        "total_runs": 0,
        "total_events": 0,
        "events_by_type": {},
        "events_by_run": {},
        "first_event": "N/A",
        "last_event": "N/A",
        "runs_analyzed": [],
        "events": [],
    }
