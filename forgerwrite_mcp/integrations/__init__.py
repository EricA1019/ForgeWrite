"""Integration adapters — fail-soft connections to external tools.

Each adapter detects if its target tool is available and returns info
without raising. Missing tools return ``{"available": False, "reason": "..."}``.
"""

from __future__ import annotations

from pathlib import Path

from .graphify_adapter import GraphifyAdapter
from .headroom_adapter import HeadroomAdapter
from .mex_adapter import MexAdapter

__all__ = [
    "GraphifyAdapter",
    "HeadroomAdapter",
    "MexAdapter",
    "get_all_info",
    "list_integrations",
]

# ── Registry ─────────────────────────────────────────────────────────────────

_ADAPTERS: dict[str, object] = {
    "mex": MexAdapter(),
    "graphify": GraphifyAdapter(),
    "headroom": HeadroomAdapter(),
}


def list_integrations() -> list[str]:
    """Return the names of all registered integration adapters."""
    return list(_ADAPTERS.keys())


def get_all_info(repo_root: Path) -> dict[str, dict]:
    """Return availability info for every integration without raising.

    Each adapter's ``get_info()`` is called; failures are caught and
    reported as unavailable.
    """
    result: dict[str, dict] = {}
    for name, adapter in _ADAPTERS.items():
        try:
            if name == "mex":
                result[name] = adapter.get_info(repo_root)  # type: ignore[union-attr]
            else:
                result[name] = adapter.get_info()  # type: ignore[union-attr]
        except Exception:
            result[name] = {
                "available": False,
                "reason": "Adapter raised an unexpected error",
            }
    return result
