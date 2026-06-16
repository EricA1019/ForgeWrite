"""Language adapter protocol and discovery.

Each language provides validation commands and default profiles.
Extend by adding a new module in this package and registering
the adapter class in :func:`_init_adapters`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import LanguageAdapter

_ADAPTERS: dict[str, LanguageAdapter] = {}


def _init_adapters() -> None:
    """Lazy-init the adapter registry from known implementations."""
    # Local imports to avoid circular dependencies at module level
    from .python import PythonAdapter
    from .rust import RustAdapter

    for cls in (RustAdapter, PythonAdapter):
        adapter = cls()
        _ADAPTERS[adapter.language] = adapter


def get_adapter(language: str) -> LanguageAdapter | None:
    """Return the adapter for *language*, or ``None`` if unsupported."""
    if not _ADAPTERS:
        _init_adapters()
    return _ADAPTERS.get(language)


def list_adapters() -> list[str]:
    """Return the list of supported language identifiers."""
    if not _ADAPTERS:
        _init_adapters()
    return list(_ADAPTERS.keys())
