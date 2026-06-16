"""MEX adapter — fail-soft connection to project memory (.mex/).

Detects the ``.mex/`` directory and reports its contents.
"""

from __future__ import annotations

from pathlib import Path


class MexAdapter:
    """Adapter for MEX project memory system.

    MEX stores project context in ``.mex/`` with markdown files,
    ``ROUTER.md``, and ``config.json``.
    """

    def check_available(self, repo_root: Path) -> bool:
        """Check if MEX is available in the given repo."""
        try:
            mex_dir = repo_root.resolve() / ".mex"
            return mex_dir.is_dir()
        except Exception:
            return False

    def get_info(self, repo_root: Path) -> dict:
        """Return MEX availability and metadata.

        Returns:
            Dict with ``available``, and if available, ``files`` and ``router``.
        """
        try:
            mex_dir = repo_root.resolve() / ".mex"
            if not mex_dir.is_dir():
                return {
                    "available": False,
                    "reason": ".mex/ directory not found",
                }

            router = mex_dir / "ROUTER.md"
            files = sorted(
                [p.name for p in mex_dir.rglob("*") if p.is_file()],
            )

            return {
                "available": True,
                "mex_dir": str(mex_dir),
                "has_router": router.exists(),
                "file_count": len(files),
                "files": files[:20],  # Cap at 20 to avoid huge payloads
            }
        except Exception:
            return {
                "available": False,
                "reason": "Error accessing .mex/ directory",
            }
