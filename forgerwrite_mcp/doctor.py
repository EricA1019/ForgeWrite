"""Shared doctor check runner — used by CLI doctor command and auto-run hooks.

Design: extracted from CLI to avoid circular imports when `init`/`approve`
need to run the same checks (SRP — one module, one responsibility).
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import httpx

# ── Check name constants (no magic strings) ──────────────────────────────────

_CHECK_CONFIG_EXISTS: str = "config_exists"
_CHECK_GIT_REPO: str = "git_repo"
_CHECK_RUST_TOOLCHAIN: str = "rust_toolchain"
_CHECK_LLAMA_REACHABLE: str = "llama_cpp_reachable"
_CHECK_RAG_INDEX: str = "rag_index"
_CHECK_SENTENCE_TRANSFORMERS: str = "sentence_transformers"

# Timeout for llama.cpp health probe (seconds)
_LLAMA_HEALTH_TIMEOUT: float = 3.0


def run_doctor_checks(root: Path) -> dict[str, bool]:
    """Run all environment checks and return a {check_name: passed} dict.

    Checks performed:
        config_exists — .forgerwrite/forgerwrite.toml exists
        git_repo — git rev-parse succeeds
        rust_toolchain — cargo --version succeeds
        llama_cpp_reachable — HTTP GET /health returns 200

    Args:
        root: Project root directory.

    Returns:
        Dict mapping check name strings to bool pass/fail.
    """
    checks: dict[str, bool] = {}

    # Config check
    config_path = root / ".forgerwrite" / "forgerwrite.toml"
    checks[_CHECK_CONFIG_EXISTS] = config_path.exists()

    # Git check
    git_ok = (
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root,
            capture_output=True,
        ).returncode
        == 0
    )
    checks[_CHECK_GIT_REPO] = git_ok

    # Rust toolchain check
    rust_ok = (
        subprocess.run(
            ["cargo", "--version"],
            capture_output=True,
        ).returncode
        == 0
    )
    checks[_CHECK_RUST_TOOLCHAIN] = rust_ok

    # llama.cpp reachability check
    llama_ok = False
    if config_path.exists():
        try:
            cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
            endpoint: str = cfg.get("local_model", {}).get("endpoint", "")
            if endpoint:
                try:
                    resp = httpx.get(
                        f"{endpoint.rstrip('/v1')}/health",
                        timeout=_LLAMA_HEALTH_TIMEOUT,
                    )
                    llama_ok = resp.status_code == 200
                except Exception:
                    pass
        except Exception:
            pass
    checks[_CHECK_LLAMA_REACHABLE] = llama_ok

    # RAG index check
    rag_ok = False
    if config_path.exists():
        try:
            cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
            rag_enabled: bool = cfg.get("rag", {}).get("enabled", False)
            if rag_enabled:
                index_path_str: str = cfg.get("rag", {}).get("index_path", "data/rag/index.tqi")
                rag_index_path = root / index_path_str
                rag_ok = rag_index_path.exists()
        except Exception:
            pass
    checks[_CHECK_RAG_INDEX] = rag_ok

    # sentence_transformers check
    st_ok = False
    try:
        import sentence_transformers  # noqa: F401
        st_ok = True
    except ImportError:
        pass
    checks[_CHECK_SENTENCE_TRANSFORMERS] = st_ok

    return checks
