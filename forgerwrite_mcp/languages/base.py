"""Language adapter protocol — language-specific defaults for the pipeline.

Each adapter provides:
- Validation commands (e.g., cargo check, pytest)
- A default validation profile name
- Profile definitions (profile_id → list of command_ids)

Implementations are in sibling modules (``rust.py``, ``python.py``, etc.).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LanguageAdapter(Protocol):
    """Protocol for language-specific defaults and validation profiles."""

    @property
    def language(self) -> str:
        """Language identifier, e.g. ``\"rust\"`` or ``\"python\"``."""
        ...

    def get_validation_commands(self) -> dict[str, str]:
        """Return a dict mapping command_id → shell command string.

        Example: ``{"fmt": "cargo fmt -- --check", "test": "cargo test"}``
        """
        ...

    def get_default_profile_name(self) -> str:
        """Return the name of the default validation profile.

        Example: ``\"rust_default\"``
        """
        ...

    def get_profiles(self) -> dict[str, list[str]]:
        """Return a dict mapping profile_id → list of command_ids.

        Example: ``{"rust_default": ["fmt", "check", "test", "clippy"]}``
        """
        ...
