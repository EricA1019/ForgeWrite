"""Python language adapter — ruff/pytest/mypy based validation commands."""

from __future__ import annotations


class PythonAdapter:
    """Python language defaults — ruff check, ruff format, pytest, mypy."""

    language = "python"

    def get_validation_commands(self) -> dict[str, str]:
        return {
            "lint": "ruff check .",
            "format_check": "ruff format --check .",
            "test": "pytest -q",
            "typecheck": "mypy --strict forgerwrite_mcp/",
        }

    def get_default_profile_name(self) -> str:
        return "python_default"

    def get_profiles(self) -> dict[str, list[str]]:
        return {
            "python_default": ["lint", "format_check", "test", "typecheck"],
        }
