"""Headroom adapter — fail-soft connection to automation orchestrator.

Detects the ``headroom`` binary. Currently expected to be unavailable
as Headroom is not part of the MVP toolchain.
"""

from __future__ import annotations

import shutil


class HeadroomAdapter:
    """Adapter for Headroom automation orchestrator.

    Headroom is an optional external orchestrator not included in MVP.
    """

    def check_available(self) -> bool:
        """Check if headroom is installed and on PATH."""
        try:
            return shutil.which("headroom") is not None
        except Exception:
            return False

    def get_info(self) -> dict:
        """Return Headroom availability info.

        Returns:
            Dict with ``available``, and if available, ``binary_path``.
        """
        try:
            binary = shutil.which("headroom")
            if binary is None:
                return {
                    "available": False,
                    "reason": "headroom binary not found on PATH (not part of MVP)",
                }
            return {
                "available": True,
                "binary_path": binary,
            }
        except Exception:
            return {
                "available": False,
                "reason": "Error checking headroom availability",
            }
