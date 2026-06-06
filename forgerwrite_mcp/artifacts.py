"""Artifact writer and run ID generation.

Centralized module for creating and managing the .forgerwrite/runs/<run_id>/
directory structure. Every module that produces persistent output uses this
module — no ad-hoc file writing to .forgerwrite/ anywhere else.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

# Public constant for the run directory sub-sections.
# Every run directory contains these subdirectories.
RUN_DIR_SECTIONS: tuple[str, ...] = ("repair_attempts",)


# -- Run ID generation --

# Private counter for unique run IDs within the same second.
# Resets on process restart (acceptable: run IDs are not required to be
# globally unique across process lifetimes).
_seq_counter: int = 0


def generate_run_id() -> str:
    """Produce a sortable, unique run ID.

    Format: run_YYYYMMDD_NNNN

    The date prefix ensures chronological sort order. The 4-digit
    sequence number handles up to 9999 runs per day per process.
    """
    global _seq_counter
    date_prefix = datetime.now(UTC).strftime("%Y%m%d")
    _seq_counter += 1
    seq = f"{_seq_counter:04d}"
    if _seq_counter >= 9999:
        _seq_counter = 0  # wrap; collision risk is negligible for a local tool
    return f"run_{date_prefix}_{seq}"


# -- Run directory management --

_RUN_DIR_BASE = ".forgerwrite/runs"


def init_run_dir(run_id: str, *, base_dir: Path | None = None) -> Path:
    """Create the full .forgerwrite/runs/<run_id>/ directory structure.

    Args:
        run_id: The run identifier (from generate_run_id()).
        base_dir: Override the root directory (for testing). Defaults to cwd.

    Returns:
        Path to the created run directory.
    """
    root = (base_dir or Path.cwd()).resolve()
    run_dir = root / _RUN_DIR_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    for section in RUN_DIR_SECTIONS:
        (run_dir / section).mkdir(exist_ok=True)
    return run_dir


# -- Artifact I/O --


def write_artifact(run_dir: Path, filename: str, data: object) -> Path:
    """Write a JSON artifact into the run directory.

    Args:
        run_dir: The run directory path (from init_run_dir).
        filename: File name, e.g. 'context_packet.json'.
        data: JSON-serializable data to write.

    Returns:
        Path to the written file.
    """
    # Safety: reject filenames with path separators (defense-in-depth;
    # proper path safety is in paths.py and will be retrofitted).
    if "/" in filename or "\\" in filename or "\x00" in filename:
        raise ValueError(f"Invalid artifact filename: {filename!r}")
    dest = run_dir / filename
    dest.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return dest


def read_artifact(run_dir: Path, filename: str) -> object:
    """Read a JSON artifact from the run directory.

    Args:
        run_dir: The run directory path.
        filename: File name to read.

    Returns:
        Parsed JSON data.

    Raises:
        FileNotFoundError: If the artifact does not exist.
    """
    dest = run_dir / filename
    return json.loads(dest.read_text(encoding="utf-8"))
