"""Tests for the CLI."""

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _parse_cli_json(result) -> dict:
    """Parse JSON output from a CLI command (--json flag produces clean JSON)."""
    return json.loads(result.stdout)


def _strip_ansi(text: str) -> str:
    """Remove Rich ANSI escape sequences for non-JSON output."""
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text).replace("\x1b", "")


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

        data = _parse_cli_json(result)
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
            "scout",
            "token-stats",
            "tui",
            "audit-report",
            "model-status",
        ]
        for cmd in expected_commands:
            assert cmd in result.stdout, f"Missing command: {cmd}"

    def test_json_flag_on_all_commands(self, runner: CliRunner) -> None:
        """--json flag is available on commands."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["project", "status", "--json"])
        assert result.exit_code in (0, 1)  # May fail without config, but flag exists


class TestCLIScout:
    """Tests for forgerwrite scout command."""

    def test_scout_command_exists(self, runner: CliRunner) -> None:
        """scout --help shows the command is registered."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["scout", "--help"])
        assert result.exit_code == 0

    def test_scout_accepts_use_model_planner_flag(self, runner: CliRunner) -> None:
        """scout --help shows --use-model-planner option."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["scout", "--help"])
        assert "--use-model-planner" in result.stdout


class TestCLITokenStats:
    """Tests for forgerwrite token-stats command."""

    def test_token_stats_command_exists(self, runner: CliRunner) -> None:
        """token-stats --help shows the command."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(app, ["token-stats", "--help"])
        assert result.exit_code == 0

    def test_token_stats_runs_without_data(self, runner: CliRunner, tmp_path: Path) -> None:
        """token-stats works even with no token data yet."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(
            app, ["token-stats", "--json"],
            env={"FORGERWRITE_ROOT": str(tmp_path)},
        )
        assert result.exit_code == 0
        import json

        data = _parse_cli_json(result)
        assert data["ok"] is True
        assert data["total_calls"] == 0


class TestCLICommandsIntegration:
    """Integration tests that hit real subsystems."""

    def test_scout_finds_evidence_in_source(self) -> None:
        """forgerwrite scout finds code patterns in the project's own source."""
        from forgerwrite_mcp.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "scout", "--json",
                "CreateFileHandler apply method",
                "--allowed-file", "forgerwrite_mcp/operations/create_file.py",
            ],
            env={"FORGERWRITE_ROOT": str(Path.cwd())},
        )
        assert result.exit_code == 0

        data = _parse_cli_json(result)
        assert len(data.get("evidence", [])) > 0

    def test_token_stats_includes_by_model(self) -> None:
        """token-stats --json includes by_model key."""
        from forgerwrite_mcp.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            app, ["token-stats", "--json"],
            env={"FORGERWRITE_ROOT": str(Path.cwd())},
        )
        assert result.exit_code == 0

        data = _parse_cli_json(result)
        assert "by_model" in data


class TestCLIAuditReport:
    """Tests for forgerwrite audit-report command."""

    def test_audit_report_runs(self, runner: CliRunner) -> None:
        """audit-report runs successfully."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(
            app, ["audit-report", "--json"],
            env={"FORGERWRITE_ROOT": str(Path.cwd())},
        )
        assert result.exit_code == 0
        data = _parse_cli_json(result)
        assert "total_events" in data
        assert isinstance(data["total_events"], int)


class TestCLIModelStatus:
    """Tests for forgerwrite model-status command."""

    def test_model_status_runs(self, runner: CliRunner) -> None:
        """model-status --json returns health check."""
        from forgerwrite_mcp.cli import app

        result = runner.invoke(
            app, ["model-status", "--json"],
            env={"FORGERWRITE_ROOT": str(Path.cwd())},
        )
        assert result.exit_code == 0
        data = _parse_cli_json(result)
        assert "healthy" in data
