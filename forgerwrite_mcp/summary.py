"""Run summary generator — produces Markdown for human-readable run results.

Design reference: §12.2

Reads all artifacts from a run directory and produces a Markdown summary
suitable for both terminal display and export.
"""

from __future__ import annotations

import json
from pathlib import Path


def generate_summary(run_dir: Path) -> str:
    """Generate a Markdown summary of a run from its artifact directory.

    Args:
        run_dir: The run artifact directory (.forgerwrite/runs/<run_id>/).

    Returns:
        A Markdown string summarizing the run.
    """
    run_id = run_dir.name
    lines: list[str] = [
        f"# Run Summary: `{run_id}`",
        "",
    ]

    # Dead letter (critical — surface first)
    dl_path = run_dir / "dead_letter.json"
    if dl_path.exists():
        dl = _read_json(dl_path)
        lines.append("## ⚠️ Dead Letter")
        lines.append("")
        lines.append(f"> **Reason:** {dl.get('reason', 'Unknown')}")
        ts = dl.get("timestamp", "")
        if ts:
            lines.append(f"> **Timestamp:** {ts}")
        payload = dl.get("payload", {})
        if payload:
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(payload, indent=2))
            lines.append("```")
        lines.append("")

    # Artifacts table
    lines.append("## Run Artifacts")
    lines.append("")
    lines.append("| File | Size |")
    lines.append("|------|------|")

    artifact_dir = run_dir
    artifacts = sorted(
        [f for f in artifact_dir.iterdir() if f.is_file()],
        key=lambda f: f.name,
    )
    for art in artifacts:
        size = art.stat().st_size
        lines.append(f"| `{art.name}` | {_format_size(size)} |")

    lines.append("")

    # Audit summary
    audit_path = run_dir / "audit.jsonl"
    if audit_path.exists():
        events = []
        for raw in audit_path.read_text(encoding="utf-8").strip().split("\n"):
            if raw.strip():
                events.append(json.loads(raw))
        lines.append("## Audit Trail")
        lines.append("")
        lines.append(f"{len(events)} event(s):")
        lines.append("")
        for evt in events:
            ts = evt.get("timestamp", "")[:19]
            etype = evt.get("event_type", "?")
            lines.append(f"- `[{ts}]` **{etype}**")
        lines.append("")

    # Contracts
    contracts_path = run_dir / "resolved_contracts.json"
    if contracts_path.exists():
        contracts = _read_json(contracts_path)
        lines.append("## Contracts")
        lines.append("")
        # Show a summary, not the full blob
        if isinstance(contracts, dict):
            for key in sorted(contracts.keys()):
                val = contracts[key]
                if isinstance(val, str):
                    lines.append(f"- **{key}:** {val[:200]}")
        lines.append("")

    # Preview diff
    diff_path = run_dir / "preview.diff"
    if diff_path.exists():
        diff_size = diff_path.stat().st_size
        lines.append("## Preview Diff")
        lines.append("")
        lines.append(f"`preview.diff` ({_format_size(diff_size)})")
        lines.append("")

    return "\n".join(lines)


def _read_json(path: Path) -> dict:
    """Read a JSON file, returning empty dict on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _format_size(size: int) -> str:
    """Format a byte count into a human-readable string."""
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MiB"
    if size >= 1_024:
        return f"{size / 1_024:.1f} KiB"
    return f"{size} B"
