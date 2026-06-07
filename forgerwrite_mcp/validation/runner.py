"""Validation runner — executes allowlisted command profiles.

Design reference: §5.8

Runs only configured command IDs from config. Stops on first failure.
Bounds output. Uses SIGTERM → configurable grace → SIGKILL for timeouts.
Never shell=True.
"""

from __future__ import annotations

import shlex
import signal
import subprocess
from pathlib import Path
from typing import Any

from ..config import LimitsConfig, ValidationConfig
from ..errors import VALIDATION_ERROR, PublicError


class ValidationError(PublicError):
    """A validation command failed or the profile was misconfigured."""

    def __init__(self, message: str) -> None:
        super().__init__(code=VALIDATION_ERROR, message=message)


def _bounded(value: str, max_chars: int) -> dict[str, Any]:
    """Truncate a string, keeping head and tail portions."""
    if len(value) <= max_chars:
        return {"head": value, "tail": "", "truncated": False}
    half = max_chars // 2
    return {"head": value[:half], "tail": value[-half:], "truncated": True}


def _run_one(
    repo_root: Path,
    command_id: str,
    cmd_str: str,
    timeout: int,
    graceful_kill: int,
    max_output_chars: int,
) -> dict[str, Any]:
    """Run a single command and return its result dict."""
    argv = shlex.split(cmd_str)
    try:
        with subprocess.Popen(
            argv,
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.send_signal(signal.SIGTERM)
                try:
                    stdout, stderr = proc.communicate(timeout=graceful_kill)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                out = _bounded("", 0)
                err = _bounded("", 0)
                return {
                    "command_id": command_id,
                    "command": cmd_str,
                    "returncode": -1,
                    "passed": False,
                    "stdout_head": out["head"],
                    "stdout_tail": out["tail"],
                    "stderr_head": err["head"],
                    "stderr_tail": err["tail"],
                    "truncated": False,
                }
    except Exception as exc:
        raise ValidationError(f"Cannot launch {cmd_str}: {exc}") from exc

    out = _bounded(stdout or "", max_output_chars)
    err = _bounded(stderr or "", max_output_chars)
    return {
        "command_id": command_id,
        "command": cmd_str,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_head": out["head"],
        "stdout_tail": out["tail"],
        "stderr_head": err["head"],
        "stderr_tail": err["tail"],
        "truncated": out["truncated"] or err["truncated"],
    }


def run_validation_profile(
    repo_root: Path,
    profile_id: str,
    config: ValidationConfig,
    *,
    limits: LimitsConfig | None = None,
) -> dict[str, Any]:
    """Run a named validation profile from config.

    Args:
        repo_root: Repository root for command execution.
        profile_id: Profile name from config.validation.profiles.
        config: ValidationConfig with commands and profiles.
        limits: LimitsConfig for output truncation (uses defaults if None).

    Returns:
        Dict matching validation_result.v1 schema shape.
    """
    if limits is None:
        limits = LimitsConfig()

    profiles = config.profiles
    commands = config.commands

    if profile_id not in profiles:
        raise ValidationError(f"Unknown profile: {profile_id}")

    results: list[dict[str, Any]] = []
    for cid in profiles[profile_id]:
        if cid not in commands:
            raise ValidationError(f"Unknown command ID: {cid}")
        r = _run_one(
            repo_root,
            cid,
            commands[cid],
            timeout=config.default_timeout_seconds,
            graceful_kill=config.graceful_kill_timeout_seconds,
            max_output_chars=limits.validation_output_max_chars,
        )
        results.append(r)
        if not r["passed"]:
            break

    return {
        "schema_id": "forgerwrite.validation_result.v1",
        "profile_id": profile_id,
        "passed": all(x["passed"] for x in results),
        "commands": results,
    }
