#!/usr/bin/env python3
"""Phase 1 acceptance runner — runs 3 Rust slices through the full pipeline.

Usage:
    python scripts/run_acceptance.py

Output:
    - docs/acceptance/rust.md — acceptance report
    - _acceptance_runs/<slice_id>/ — per-slice run artifacts (copied from .forgerwrite/runs/)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── Project root ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
FIXTURES_DIR = PROJECT_ROOT / "_acceptance_fixtures"
RUNS_DIR = PROJECT_ROOT / "_acceptance_runs"
ACCEPTANCE_DOC = PROJECT_ROOT / "docs" / "acceptance" / "rust.md"


# ── Slice definitions ───────────────────────────────────────────────────────


@dataclass
class SliceDefinition:
    """Definition of one acceptance-test slice."""

    slice_id: str
    goal: str
    fixture_dir: str  # relative to FIXTURES_DIR
    allowed_files: list[str]
    handoff_description: str
    expected_operation_types: list[str]
    acceptance_commands: list[str]  # shell commands to verify, run in fixture dir
    validation_profile: str = "rust_default"


SLICES: list[SliceDefinition] = [
    SliceDefinition(
        slice_id="r1-create-cli",
        goal="Create a minimal Rust CLI project that parses one flag",
        fixture_dir="r1-create-cli",
        allowed_files=["Cargo.toml", "src/main.rs"],
        handoff_description="Create a minimal Rust CLI project. Generate Cargo.toml with clap dependency "
        "and src/main.rs with a simple CLI that takes a --name flag and prints a greeting. "
        "Use clap v4 with the derive API. The CLI should accept --name <NAME> and print 'Hello, <NAME>!'.",
        expected_operation_types=["create_file", "create_file"],
        acceptance_commands=[
            "cargo build",
            "cargo test",
            "cargo clippy --all-targets --all-features -- -D warnings 2>&1 || true",  # non-fatal
            "cargo fmt -- --check 2>&1 || true",  # non-fatal
        ],
    ),
    SliceDefinition(
        slice_id="r2-fix-bug",
        goal="Add a failing test to expose the bug, then fix the function",
        fixture_dir="r2-fix-bug",
        allowed_files=["src/lib.rs", "src/main.rs", "Cargo.toml"],
        handoff_description="The function double(n) in src/lib.rs returns n * 3 instead of n * 2. "
        "First add a test that exposes this bug (expect double(2) == 4 but gets 6). "
        "Then fix the function body to return the correct value. "
        "Do NOT remove the existing test. All tests must pass after the fix.",
        expected_operation_types=["replace_line_range", "replace_line_range"],
        acceptance_commands=[
            "cargo test",
            "cargo clippy --all-targets --all-features -- -D warnings 2>&1 || true",
        ],
    ),
    SliceDefinition(
        slice_id="r3-refactor",
        goal="Refactor the math module without changing behavior",
        fixture_dir="r3-refactor",
        allowed_files=["src/lib.rs"],
        handoff_description="The math module in src/lib.rs has three area functions (rectangle_area, "
        "triangle_area, circle_area). Each computes width*height, (base*height)/2, and pi*radius^2 "
        "respectively. Extract the multiplication pattern into a private helper function that multiplies "
        "two f64 values, then use it in all three area functions. Do NOT change any public signatures "
        "or test behavior. All existing tests must still pass unchanged.",
        expected_operation_types=["replace_line_range", "replace_line_range"],
        acceptance_commands=[
            "cargo test",
            "cargo clippy --all-targets --all-features -- -D warnings 2>&1 || true",
            "cargo fmt -- --check 2>&1 || true",
        ],
    ),
]


# ── Slice runner ────────────────────────────────────────────────────────────


@dataclass
class SliceRunResult:
    """Outcome of one slice run."""

    slice_id: str
    success: bool = False
    run_id: str | None = None
    status: str = ""
    errors: list[str] = field(default_factory=list)
    timing_seconds: float = 0.0
    acceptance_results: dict[str, bool] = field(default_factory=dict)
    repair_loop_exercised: bool = False
    operation_count: int = 0


def _init_git_repo(directory: Path) -> None:
    """Initialize a git repo in directory and commit any existing files."""
    subprocess.run(["git", "init"], cwd=directory, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "acceptance@test.com"],
        cwd=directory,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Acceptance Test"],
        cwd=directory,
        capture_output=True,
        check=True,
    )
    # Add and commit if there are files
    result = subprocess.run(
        ["git", "add", "-A"], cwd=directory, capture_output=True
    )
    if result.returncode == 0:
        subprocess.run(
            ["git", "commit", "-m", "Initial fixture state", "--allow-empty"],
            cwd=directory,
            capture_output=True,
            check=True,
        )


def _write_config(directory: Path) -> None:
    """Write a forgerwrite.toml for the acceptance test project."""
    cfg_dir = directory / ".forgerwrite"
    cfg_dir.mkdir(exist_ok=True)

    config_text = """\
[project]
name = "acceptance-test"
language = "rust"
repo_root = "."

[local_model]
provider = "llama_cpp"
endpoint = "http://127.0.0.1:8080/v1"
model = "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
temperature = 0.20
top_p = 0.90
top_k = 20
max_tokens = 4096
json_retries = 2
request_timeout_seconds = 300.0

[limits]
context_file_max_bytes = 200000
context_total_max_bytes = 8000000
validation_output_max_chars = 16000
operation_batch_max_operations = 32
operation_content_max_bytes = 200000
artifact_retention_days = 90

[validation]
default_timeout_seconds = 300
graceful_kill_timeout_seconds = 5

[validation.commands]
fmt = "cargo fmt -- --check"
check = "cargo check"
test = "cargo test"
clippy = "cargo clippy --all-targets --all-features -- -D warnings"

[validation.profiles]
rust_default = ["fmt", "check", "test", "clippy"]

[permissions]
require_clean_worktree = true
allow_unknown_commands = false
require_approval_for_new_dependencies = true
require_approval_for_delete = true
require_approval_for_full_file_replace = true
allow_unified_diff_fallback = false

[hygiene]
generated_globs = ["target/**"]
vendor_globs = ["vendor/**"]

[repair]
max_attempts = 2
scope_must_match_original_slice = true

[rag]
enabled = true
index_path = "../../data/rag/index.tqi"
k_documents = 3
embedding_model_name = "Alibaba-NLP/gte-modernbert-base"
max_rag_tokens = 2048
"""
    (cfg_dir / "forgerwrite.toml").write_text(config_text)


def run_slice(slice_def: SliceDefinition) -> SliceRunResult:
    """Execute one slice through the full coordinator pipeline."""
    from forgerwrite_mcp.config import load_config, ForgerWriteConfig
    from forgerwrite_mcp.coordinator import SliceCoordinator
    from forgerwrite_mcp.llama_client import LlamaCppClient
    from forgerwrite_mcp.operations.registry import default_registry
    from forgerwrite_mcp.rag import build_rag_enricher

    result = SliceRunResult(slice_id=slice_def.slice_id)
    start_time = time.time()

    # Create working directory
    fixture_path = FIXTURES_DIR / slice_def.fixture_dir
    work_dir = RUNS_DIR / slice_def.slice_id
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(fixture_path, work_dir)

    print(f"\n{'='*70}")
    print(f"  Running slice: {slice_def.slice_id}")
    print(f"  Goal: {slice_def.goal}")
    print(f"{'='*70}")

    # Initialize git repo
    _init_git_repo(work_dir)
    _write_config(work_dir)

    # Load config and build dependencies
    config: ForgerWriteConfig = load_config(work_dir)
    registry = default_registry()
    client = LlamaCppClient.from_config(config.local_model)

    # Build RAG enricher (uses relative index_path from config)
    enricher = build_rag_enricher(config, project_root=work_dir)

    if enricher:
        print(f"  RAG enricher: built (k={config.rag.k_documents})")
    else:
        print("  RAG enricher: not available (index missing or disabled)")

    # Build coordinator
    coord = SliceCoordinator(
        repo_root=work_dir,
        config=config,
        registry=registry,
        backend=client,
        auto_approve=True,
        enricher=enricher,
    )

    # Build handoff and slice contracts
    handoff = {
        "schema_id": "forgerwrite.handoff.v1",
        "project": "acceptance-test",
        "language": "rust",
        "description": slice_def.handoff_description,
    }
    slice_contract = {
        "schema_id": "forgerwrite.slice.v1",
        "slice_id": slice_def.slice_id,
        "description": slice_def.goal,
        "allowed_files": slice_def.allowed_files,
        "validation_profile": slice_def.validation_profile,
    }

    # Run the pipeline
    print(f"  Running coordinator pipeline...")
    try:
        outcome = coord.run(handoff, slice_contract)
        result.run_id = outcome.run_id
        result.status = outcome.status
        result.errors = outcome.errors or []

        # Count operations
        if hasattr(coord, "_operation_batch") and coord._operation_batch:
            ops = coord._operation_batch.get("operations", [])
            result.operation_count = len(ops)

        print(f"  Run ID: {outcome.run_id}")
        print(f"  Status: {outcome.status}")
        print(f"  Operations: {result.operation_count}")
        if outcome.errors:
            for err in outcome.errors:
                print(f"  Error: {err}")

        # Check if repair loop was exercised
        result.repair_loop_exercised = (
            coord._run_dir is not None
            and (coord._run_dir / "repair_prompt_1.txt").exists()
        )
        if result.repair_loop_exercised:
            print(f"  Repair loop: EXERCISED")

    except Exception as exc:
        result.status = "exception"
        result.errors = [str(exc)]
        print(f"  Exception: {exc}")

    # Run acceptance verification commands
    print(f"\n  ── Acceptance verification ──")
    for cmd in slice_def.acceptance_commands:
        try:
            proc = subprocess.run(
                cmd,
                cwd=work_dir,
                shell=True,
                capture_output=True,
                timeout=120,
            )
            passed = proc.returncode == 0
            result.acceptance_results[cmd] = passed
            status_str = "PASS" if passed else "FAIL"
            print(f"  [{status_str}] $ {cmd}")
            if not passed:
                stderr = proc.stderr.decode()[:200]
                if stderr:
                    print(f"           {stderr.strip()}")
        except subprocess.TimeoutExpired:
            result.acceptance_results[cmd] = False
            print(f"  [TIMEOUT] $ {cmd}")

    # Overall success
    all_acceptance_pass = all(result.acceptance_results.values())
    pipeline_ok = result.status == "validation_passed"
    result.success = pipeline_ok and all_acceptance_pass

    result.timing_seconds = time.time() - start_time

    # Note: run artifacts are already in work_dir/.forgerwrite/runs/<run_id>/
    if coord._run_dir and coord._run_dir.exists():
        print(f"  Artifacts at: {coord._run_dir}")

    print(f"  Time: {result.timing_seconds:.1f}s")
    print(f"  Outcome: {'✅ PASS' if result.success else '❌ FAIL'}")

    return result


# ── Report generation ───────────────────────────────────────────────────────


def generate_report(results: list[SliceRunResult]) -> str:
    """Generate the acceptance report Markdown."""
    total = len(results)
    passed = sum(1 for r in results if r.success)

    lines: list[str] = []
    lines.append("# Rust MVP Acceptance Report")
    lines.append("")
    lines.append(f"**Date:** 2026-06-13")
    lines.append(f"**Model:** Gemma 4 12B (Q4_K_XL) via llama.cpp")
    lines.append(f"**Pipeline:** `SliceCoordinator` with auto-approve + RAG enrichment")
    lines.append(f"**Result:** {passed}/{total} slices passed")
    lines.append("")

    for r in results:
        lines.append(f"## {r.slice_id}: {dict(g for g in [(s.slice_id, s.goal) for s in SLICES] if g[0] == r.slice_id)[0][1]}")
        lines.append("")
        lines.append(f"- **Status:** `{r.status}`")
        lines.append(f"- **Run ID:** `{r.run_id}`")
        lines.append(f"- **Duration:** {r.timing_seconds:.1f}s")
        lines.append(f"- **Operations generated:** {r.operation_count}")
        lines.append(f"- **Repair loop exercised:** {'Yes' if r.repair_loop_exercised else 'No'}")
        lines.append(f"- **Overall:** {'✅ PASS' if r.success else '❌ FAIL'}")
        if r.errors:
            lines.append("- **Errors:**")
            for err in r.errors:
                lines.append(f"  - {err}")
        lines.append("")
        lines.append("### Acceptance Criteria")
        lines.append("")
        for cmd, passed in r.acceptance_results.items():
            lines.append(f"- {'✅' if passed else '❌'} `{cmd}`")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"**{passed}/{total} slices passed acceptance criteria.**")
    lines.append("")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 70)
    print("  ForgeWrite MCP — Phase 1 Acceptance Tests")
    print("  Model: Gemma 4 12B (Q4_K_XL) via llama.cpp")
    print("=" * 70)

    # Ensure the acceptance runs directory exists
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    results: list[SliceRunResult] = []
    for i, slice_def in enumerate(SLICES):
        print(f"\n{'='*70}")
        print(f"  Slice {i+1}/{len(SLICES)}: {slice_def.slice_id}")
        print(f"{'='*70}")
        try:
            result = run_slice(slice_def)
        except Exception as exc:
            print(f"  UNEXPECTED ERROR: {exc}")
            import traceback
            traceback.print_exc()
            result = SliceRunResult(
                slice_id=slice_def.slice_id,
                success=False,
                status="exception",
                errors=[str(exc)],
            )
        results.append(result)

    # Generate report
    report = generate_report(results)
    ACCEPTANCE_DOC.parent.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_DOC.write_text(report)
    print(f"\nAcceptance report written to: {ACCEPTANCE_DOC}")

    # Summary
    passed = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    total_time = sum(r.timing_seconds for r in results)
    print(f"\n{'='*70}")
    print(f"  Phase 1 Complete: {passed} passed, {failed} failed, {total_time:.0f}s total")
    print(f"{'='*70}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
