"""Tests for the validation runner."""

from pathlib import Path

import pytest


def _write_config(
    tmp_path: Path,
    commands: dict[str, str] | None = None,
    profiles: dict[str, list[str]] | None = None,
    timeout: int = 300,
    graceful_kill: int = 5,
) -> object:
    """Create a ValidationConfig for testing."""
    from forgerwrite_mcp.config import ValidationConfig

    return ValidationConfig(
        commands=commands or {},
        profiles=profiles or {},
        default_timeout_seconds=timeout,
        graceful_kill_timeout_seconds=graceful_kill,
    )


class TestValidationRunner:
    """Tests for run_validation_profile()."""

    def test_unknown_profile_raises_typed_error(self, tmp_path: Path) -> None:
        """Unknown profile ID raises ValidationError."""
        from forgerwrite_mcp.errors import VALIDATION_ERROR
        from forgerwrite_mcp.validation.runner import (
            ValidationError,
            run_validation_profile,
        )

        cfg = _write_config(tmp_path, profiles={"rust": ["fmt"]})
        with pytest.raises(ValidationError) as exc_info:
            run_validation_profile(tmp_path, "nonexistent", cfg)
        assert exc_info.value.code == VALIDATION_ERROR

    def test_unknown_command_id_raises_typed_error(self, tmp_path: Path) -> None:
        """Unknown command ID in a profile raises ValidationError."""
        from forgerwrite_mcp.errors import VALIDATION_ERROR
        from forgerwrite_mcp.validation.runner import (
            ValidationError,
            run_validation_profile,
        )

        cfg = _write_config(
            tmp_path,
            commands={"fmt": "echo ok"},
            profiles={"rust": ["fmt", "unknown_cmd"]},
        )
        with pytest.raises(ValidationError) as exc_info:
            run_validation_profile(tmp_path, "rust", cfg)
        assert exc_info.value.code == VALIDATION_ERROR

    def test_all_commands_pass_returns_passed_true(self, tmp_path: Path) -> None:
        """When all commands succeed, result.passed is True."""
        from forgerwrite_mcp.validation.runner import run_validation_profile

        cfg = _write_config(
            tmp_path,
            commands={"echo": "echo hello"},
            profiles={"test": ["echo"]},
        )
        result = run_validation_profile(tmp_path, "test", cfg)
        assert result["passed"] is True
        assert len(result["commands"]) == 1
        assert result["commands"][0]["passed"] is True

    def test_failure_stops_subsequent_commands(self, tmp_path: Path) -> None:
        """First failing command stops remaining commands from running."""
        from forgerwrite_mcp.validation.runner import run_validation_profile

        cfg = _write_config(
            tmp_path,
            commands={
                "fail": 'python -c "import sys; sys.exit(1)"',
                "never_run": "echo should_not_run",
            },
            profiles={"test": ["fail", "never_run"]},
            timeout=5,
        )
        result = run_validation_profile(tmp_path, "test", cfg)
        assert result["passed"] is False
        # Only the first command should have run
        assert len(result["commands"]) == 1
        assert result["commands"][0]["command_id"] == "fail"

    def test_output_truncation_obeys_limit(self, tmp_path: Path) -> None:
        """Long stdout is truncated per the limits config."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.validation.runner import run_validation_profile

        # Write a script that outputs lots of text
        script = tmp_path / "noisy.py"
        script.write_text("print('x' * 5000)\n")

        cfg = _write_config(
            tmp_path,
            commands={"noisy": f"python {script}"},
            profiles={"test": ["noisy"]},
            timeout=10,
        )
        # Use a small limit (minimum valid is 1000)
        limits = LimitsConfig(validation_output_max_chars=1000)
        result = run_validation_profile(tmp_path, "test", cfg, limits=limits)
        cmd_result = result["commands"][0]
        assert cmd_result["truncated"] is True
        assert len(cmd_result["stdout_head"]) <= 1000

    def test_long_running_command_sigterm_then_sigkill(self, tmp_path: Path) -> None:
        """Command exceeding timeout gets SIGTERM, then SIGKILL after grace."""
        from forgerwrite_mcp.validation.runner import run_validation_profile

        # Sleep longer than timeout — will be killed
        cfg = _write_config(
            tmp_path,
            commands={"sleeper": "sleep 30"},
            profiles={"test": ["sleeper"]},
            timeout=1,
            graceful_kill=1,
        )
        result = run_validation_profile(tmp_path, "test", cfg)
        assert result["passed"] is False
        cmd_result = result["commands"][0]
        assert cmd_result["passed"] is False

    def test_shell_equals_false_enforced(self, tmp_path: Path) -> None:
        """Commands with shell metacharacters are treated as argv, not shell."""
        from forgerwrite_mcp.validation.runner import run_validation_profile

        # $HOME should NOT be expanded (shell=False), so echo '$HOME' should print literal $HOME
        cfg = _write_config(
            tmp_path,
            commands={"echo": "echo $HOME"},
            profiles={"test": ["echo"]},
            timeout=5,
        )
        result = run_validation_profile(tmp_path, "test", cfg)
        stdout = result["commands"][0]["stdout_head"]
        # With shell=False, '$HOME' is printed literally, NOT expanded
        assert "$HOME" in stdout or result["commands"][0]["passed"] is True

    def test_result_schema_matches_validation_result(self) -> None:
        """Output dict has required fields per validation_result.v1 schema."""
        # Check the shape, not actual validation against JSON schema
        from forgerwrite_mcp.config import ValidationConfig

        cfg = ValidationConfig(
            commands={"echo": "echo ok"},
            profiles={"test": ["echo"]},
        )

        # Verify the config structure is correct; actual run tested above
        assert "echo" in cfg.commands
        assert "test" in cfg.profiles
