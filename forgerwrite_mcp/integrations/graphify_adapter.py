"""Graphify adapter — fail-soft connection to codebase graph analysis.

Detects the ``graphify`` binary and reports its version/capabilities.
"""

from __future__ import annotations

import shutil


class GraphifyAdapter:
    """Adapter for Graphify codebase graph analysis.

    Graphify produces knowledge graphs from code and documentation.
    """

    def check_available(self) -> bool:
        """Check if graphify is installed and on PATH."""
        try:
            return shutil.which("graphify") is not None
        except Exception:
            return False

    def get_info(self) -> dict:
        """Return Graphify availability info.

        Returns:
            Dict with ``available``, and if available, ``binary_path``.
        """
        try:
            binary = shutil.which("graphify")
            if binary is None:
                return {
                    "available": False,
                    "reason": "graphify binary not found on PATH",
                }
            return {
                "available": True,
                "binary_path": binary,
            }
        except Exception:
            return {
                "available": False,
                "reason": "Error checking graphify availability",
            }
