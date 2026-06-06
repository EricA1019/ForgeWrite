"""Tests for the artifact writer and run ID generation module."""

import json
from datetime import UTC
from pathlib import Path

import pytest

# Will import from forgerwrite_mcp.artifacts once implemented


class TestGenerateRunId:
    """Tests for generate_run_id()."""

    def test_generate_run_id_is_unique_and_sortable(self) -> None:
        """Each call returns a new, sortable ID with consistent format."""
        from forgerwrite_mcp.artifacts import generate_run_id

        ids = [generate_run_id() for _ in range(100)]
        # All unique
        assert len(set(ids)) == 100, "Run IDs must be unique"
        # Sortable (chronological order)
        assert sorted(ids) == ids, "Run IDs must be sortable (natural sort order)"
        # Consistent format: run_YYYYMMDD_NNNN
        for rid in ids:
            assert rid.startswith("run_"), f"ID must start with 'run_': {rid}"
            parts = rid.split("_")
            assert len(parts) == 3, f"ID must have 3 segments: {rid}"
            date_part = parts[1]
            assert len(date_part) == 8, f"Date part must be 8 digits: {rid}"
            seq_part = parts[2]
            assert len(seq_part) == 4, f"Seq part must be 4 digits: {rid}"
            assert date_part.isdigit(), f"Date part must be numeric: {rid}"
            assert seq_part.isdigit(), f"Seq part must be numeric: {rid}"

    def test_run_id_includes_timestamp_prefix(self) -> None:
        """Run ID uses YYYYMMDD date prefix."""
        from datetime import datetime

        from forgerwrite_mcp.artifacts import generate_run_id

        rid = generate_run_id()
        today = datetime.now(UTC).strftime("%Y%m%d")
        date_part = rid.split("_")[1]
        assert date_part == today, f"Date part must be today: {date_part} != {today}"


class TestInitRunDir:
    """Tests for init_run_dir()."""

    def test_init_run_creates_directory_structure(self, tmp_path: Path) -> None:
        """Creates the full .forgerwrite/runs/<run_id>/ layout."""
        from forgerwrite_mcp.artifacts import RUN_DIR_SECTIONS, init_run_dir

        run_id = "run_20260606_0001"
        run_dir = init_run_dir(run_id, base_dir=tmp_path)

        assert run_dir.exists()
        assert run_dir.name == run_id
        for section in RUN_DIR_SECTIONS:
            section_path = run_dir / section
            assert section_path.exists(), f"Missing section: {section}"
            assert section_path.is_dir(), f"Section must be a directory: {section}"


class TestWriteReadArtifact:
    """Tests for write_artifact() and read_artifact()."""

    def test_write_artifact_saves_json_file(self, tmp_path: Path) -> None:
        """write_artifact writes valid JSON with .json extension."""
        from forgerwrite_mcp.artifacts import init_run_dir, write_artifact

        run_dir = init_run_dir("run_20260606_0001", base_dir=tmp_path)
        data = {"key": "value", "nested": {"a": 1}}
        result = write_artifact(run_dir, "test.json", data)

        assert result.exists()
        assert result.suffix == ".json"
        loaded = json.loads(result.read_text(encoding="utf-8"))
        assert loaded == data

    def test_read_artifact_roundtrips(self, tmp_path: Path) -> None:
        """read_artifact returns the same data that was written."""
        from forgerwrite_mcp.artifacts import (
            init_run_dir,
            read_artifact,
            write_artifact,
        )

        run_dir = init_run_dir("run_20260606_0001", base_dir=tmp_path)
        data = {"numbers": [1, 2, 3], "bool": True, "null_val": None}
        write_artifact(run_dir, "data.json", data)
        loaded = read_artifact(run_dir, "data.json")
        assert loaded == data

    def test_read_artifact_raises_on_missing_file(self, tmp_path: Path) -> None:
        """read_artifact raises FileNotFoundError for missing files."""

        from forgerwrite_mcp.artifacts import init_run_dir, read_artifact

        run_dir = init_run_dir("run_20260606_0001", base_dir=tmp_path)
        with pytest.raises((FileNotFoundError, OSError)):
            read_artifact(run_dir, "nonexistent.json")

    def test_write_artifact_pretty_prints_json(self, tmp_path: Path) -> None:
        """write_artifact produces human-readable indented JSON."""
        from forgerwrite_mcp.artifacts import init_run_dir, write_artifact

        run_dir = init_run_dir("run_20260606_0001", base_dir=tmp_path)
        write_artifact(run_dir, "pretty.json", {"a": 1, "b": 2})
        content = (run_dir / "pretty.json").read_text(encoding="utf-8")
        assert "  " in content, "JSON should be indented"
        assert content.count("\n") > 2, "JSON should span multiple lines"
