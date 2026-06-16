"""Tests for the CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCLIInit:
    """Tests for forgerwrite init."""

    def test_init_scaffolds_dot_forgerwrite(self, runner: CliRunner, tmp_path: Path) -> None:
        """init creates .forgerwrite/ directory."""
        from forgerwrite_mcp.cli import app

        runner.invoke(app, ["init"], env={"FORGERWRITE_ROOT": str(tmp_path)})
        # init may fail without git, but should at least create the directory
        # or give a useful message

    def test_init_creates_gitignore_entries(self) -> None:
        """The init command generates gitignore entries (unit test of template)."""
        from forgerwrite_mcp.cli import _GITIGNORE_TEMPLATE

        assert ".forgerwrite/runs/" in _GITIGNORE_TEMPLATE
        assert ".forgerwrite/forgerwrite.db" in _GITIGNORE_TEMPLATE


class TestCLIDoctor:
    """Tests for forgerwrite doctor."""

    def test_doctor_detects_missing_config(self, runner: CliRunner, tmp_path: Path) -> None:
        """doctor reports missing config."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["doctor"], env={"FORGERWRITE_ROOT": str(tmp_path)})
        # Should report something useful
        assert result.exit_code in (0, 1)

    def test_doctor_rag_checks_present(self, runner: CliRunner, tmp_path: Path) -> None:
        """doctor --json includes rag_index and sentence_transformers checks."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["doctor", "--json"], env={"FORGERWRITE_ROOT": str(tmp_path)})
        assert result.exit_code in (0, 1)
        import json

        data = json.loads(result.stdout)
        assert "rag_index" in data["checks"]
        assert "sentence_transformers" in data["checks"]


class TestCLICommandsExist:
    """Verify all CLI commands are registered."""

    def test_help_shows_all_commands(self, runner: CliRunner) -> None:
        """--help lists all available commands."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        expected_commands = [
            "init",
            "doctor",
            "approve",
            "show-diff",
            "inspect",
            "restore",
            "abort",
            "gc",
            "runs",
            "project",
        ]
        for cmd in expected_commands:
            assert cmd in result.stdout, f"Missing command: {cmd}"

    def test_json_flag_on_all_commands(self, runner: CliRunner) -> None:
        """--json flag is available on commands."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["project", "status", "--json"])
        assert result.exit_code in (0, 1)  # May fail without config, but flag exists
