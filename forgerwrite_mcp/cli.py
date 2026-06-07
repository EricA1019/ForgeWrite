"""CLI — Typer commands for forgerwrite.

Design reference: §5.11

Commands: init, doctor, approve, show-diff, inspect, restore, abort, gc,
runs list, project status. All use rich for output. --json flag supported.
"""

from __future__ import annotations

import json
import os
from datetime import UTC
from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax

app = typer.Typer(
    name="forgerwrite",
    help="Local-first MCP coding service CLI.",
)
console = Console()

# ── Templates ────────────────────────────────────────────────────────────────

_GITIGNORE_TEMPLATE: str = """\
.forgerwrite/runs/
.forgerwrite/forgerwrite.db
.forgerwrite/secrets.json
"""

_CONFIG_TEMPLATE: str = """\
[project]
name = "my-project"
language = "rust"
repo_root = "."

[local_model]
provider = "llama_cpp"
endpoint = "http://127.0.0.1:8080/v1"
model = "omnicoder-9b"
temperature = 0.20
top_p = 0.90
top_k = 20
max_tokens = 2048
json_retries = 2
request_timeout_seconds = 180
retry_base_delay_seconds = 0.5
retry_max_delay_seconds = 8.0
retry_multiplier = 2.0

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
"""


def _get_root() -> Path:
    """Get the project root from env or cwd."""
    env_root = os.environ.get("FORGERWRITE_ROOT")
    if env_root:
        return Path(env_root)
    return Path.cwd()


def _json_out(data: dict, json_flag: bool) -> None:
    """Print output as JSON or rich-formatted."""
    if json_flag:
        console.print(json.dumps(data, indent=2, default=str))
    else:
        console.print(data)


# ── Commands ─────────────────────────────────────────────────────────────────


@app.command()
def init(
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
    skip_doctor: bool = typer.Option(
        False, "--skip-doctor", help="Skip environment checks."
    ),
) -> None:
    """Scaffold .forgerwrite/ directory and config."""
    root = _get_root()

    # Auto-run doctor checks before scaffolding (spec §5.11)
    if not skip_doctor:
        from .doctor import run_doctor_checks

        checks = run_doctor_checks(root)
        if not all(checks.values()):
            failed = [k for k, v in checks.items() if not v]
            console.print(f"[yellow]Warning: doctor checks failed: {', '.join(failed)}[/yellow]")

    fw_dir = root / ".forgerwrite"
    fw_dir.mkdir(exist_ok=True)
    (fw_dir / "contracts").mkdir(exist_ok=True)

    config_path = fw_dir / "forgerwrite.toml"
    if not config_path.exists():
        config_path.write_text(_CONFIG_TEMPLATE)

    gitignore = root / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    if _GITIGNORE_TEMPLATE not in existing:
        with gitignore.open("a") as f:
            f.write("\n" + _GITIGNORE_TEMPLATE)

    _json_out(
        {
            "ok": True,
            "message": "Initialized .forgerwrite/",
            "config": str(config_path),
        },
        json_flag,
    )


@app.command()
def doctor(
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Check environment: config, git, llama.cpp, Rust toolchain."""
    root = _get_root()
    from .doctor import run_doctor_checks

    checks = run_doctor_checks(root)
    all_ok = all(checks.values())
    _json_out({"ok": all_ok, "checks": checks}, json_flag)


@app.command()
def approve(
    run_id: str = typer.Argument(..., help="Run ID to approve."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show diff without approving."),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
    skip_doctor: bool = typer.Option(
        False, "--skip-doctor", help="Skip environment checks."
    ),
) -> None:
    """Approve a run after reviewing the preview diff."""
    root = _get_root()

    # Auto-run doctor checks before approving (spec §5.11)
    if not skip_doctor:
        from .doctor import run_doctor_checks

        checks = run_doctor_checks(root)
        if not all(checks.values()):
            failed = [k for k, v in checks.items() if not v]
            console.print(f"[yellow]Warning: doctor checks failed: {', '.join(failed)}[/yellow]")

    run_dir = root / ".forgerwrite" / "runs" / run_id
    diff_path = run_dir / "preview.diff"

    if not diff_path.exists():
        console.print(f"[red]No preview diff found for run {run_id}[/red]")
        raise typer.Exit(1)

    diff_content = diff_path.read_text()
    syntax = Syntax(diff_content, "diff", theme="monokai")
    console.print(syntax)

    if dry_run:
        console.print("[yellow]Dry run — no approval written.[/yellow]")
        return

    if not typer.confirm("\nApprove this diff?"):
        console.print("[yellow]Approval declined.[/yellow]")
        raise typer.Exit(0)

    from .approval import write_approval_record

    write_approval_record(run_dir)
    _json_out({"ok": True, "run_id": run_id, "approved": True}, json_flag)


@app.command()
def show_diff(
    run_id: str = typer.Argument(..., help="Run ID."),
) -> None:
    """Pretty-print the preview diff."""
    root = _get_root()
    diff_path = root / ".forgerwrite" / "runs" / run_id / "preview.diff"
    if not diff_path.exists():
        console.print(f"[red]No diff for run {run_id}[/red]")
        raise typer.Exit(1)
    syntax = Syntax(diff_path.read_text(), "diff", theme="monokai")
    console.print(syntax)


@app.command()
def inspect(
    run_id: str = typer.Argument(..., help="Run ID."),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Inspect a run — print full Markdown summary."""
    root = _get_root()
    run_dir = root / ".forgerwrite" / "runs" / run_id
    if not run_dir.exists():
        console.print(f"[red]Run {run_id} not found[/red]")
        raise typer.Exit(1)

    from .summary import generate_summary

    if json_flag:
        _json_out({"run_id": run_id, "summary": generate_summary(run_dir)}, True)
    else:
        console.print(generate_summary(run_dir))


@app.command()
def restore(
    run_id: str = typer.Argument(..., help="Run ID."),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Restore git snapshot for a run."""
    root = _get_root()
    from .forge.git_utils import restore_snapshot

    restore_snapshot(root, run_id)
    _json_out({"ok": True, "run_id": run_id, "restored": True}, json_flag)


@app.command()
def abort(
    run_id: str = typer.Argument(..., help="Run ID."),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Abort a run: restore snapshot and write dead letter."""
    root = _get_root()
    from .audit import write_audit_event
    from .dead_letter import write_dead_letter
    from .forge.git_utils import restore_snapshot

    restore_snapshot(root, run_id)
    run_dir = root / ".forgerwrite" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_dead_letter(run_dir, "Aborted by user")
    write_audit_event(run_dir, "abort")
    _json_out({"ok": True, "run_id": run_id, "aborted": True}, json_flag)


@app.command()
def gc(
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Clean expired run directories and orphan snapshot refs."""
    import shutil
    import subprocess
    from datetime import datetime, timedelta

    from .config import load_config

    root = _get_root()
    try:
        config = load_config(root)
        retention_days = config.limits.artifact_retention_days
    except Exception:
        retention_days = 90

    runs_dir = root / ".forgerwrite" / "runs"
    cleaned_runs = 0

    if runs_dir.exists():
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        for run_dir in list(runs_dir.iterdir()):
            if run_dir.is_dir():
                run_json = run_dir / "run.json"
                if run_json.exists():
                    try:
                        data = json.loads(run_json.read_text())
                        created = data.get("created_at", "")
                        if created:
                            created_dt = datetime.fromisoformat(created)
                            if created_dt < cutoff:
                                shutil.rmtree(run_dir)
                                cleaned_runs += 1
                    except Exception:
                        pass

    # Clean orphan snapshot refs (refs without corresponding run directories)
    cleaned_refs = 0
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "refs/forgerwrite/", "--format=%(refname:short)"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        for ref_line in result.stdout.strip().split("\n"):
            ref_line = ref_line.strip()
            if not ref_line:
                continue
            # Extract run_id from refs/forgerwrite/<run_id>
            ref_name = ref_line.removeprefix("refs/forgerwrite/")
            if ref_name == ref_line:
                continue  # unexpected format
            run_dir = runs_dir / ref_name if runs_dir else None
            if not run_dir or not run_dir.exists():
                subprocess.run(
                    ["git", "update-ref", "-d", f"refs/forgerwrite/{ref_name}"],
                    cwd=root,
                    capture_output=True,
                )
                cleaned_refs += 1
    except Exception:
        pass

    _json_out({"ok": True, "cleaned_runs": cleaned_runs, "cleaned_refs": cleaned_refs}, json_flag)


@app.command()
def runs_list(
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List all runs from JSON artifacts."""
    root = _get_root()
    runs_dir = root / ".forgerwrite" / "runs"
    if not runs_dir.exists():
        _json_out({"runs": []}, json_flag)
        return

    runs = []
    for run_dir in sorted(runs_dir.iterdir()):
        if run_dir.is_dir():
            run_json = run_dir / "run.json"
            if run_json.exists():
                try:
                    runs.append(json.loads(run_json.read_text()))
                except Exception:
                    runs.append({"run_id": run_dir.name, "status": "unknown"})
    _json_out({"runs": runs}, json_flag)


@app.command()
def project_status(
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show project config summary."""
    root = _get_root()
    try:
        from .config import load_config

        config = load_config(root)
        summary = {
            "project": config.project.model_dump(),
            "model": config.local_model.model,
            "endpoint": config.local_model.endpoint,
            "validation_profiles": list(config.validation.profiles.keys()),
            "repair_max_attempts": config.repair.max_attempts,
        }
        _json_out(summary, json_flag)
    except Exception as exc:
        _json_out({"ok": False, "error": str(exc)}, json_flag)


# ── Runs sub-command group ──────────────────────────────────────────────────

runs_app = typer.Typer(help="Manage runs.")
app.add_typer(runs_app, name="runs")


@runs_app.command("list")
def runs_list_sub(
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List all runs."""
    runs_list(json_flag=json_flag)


# ── Project sub-command group ───────────────────────────────────────────────

project_app = typer.Typer(help="Project management.")
app.add_typer(project_app, name="project")


@project_app.command("status")
def project_status_sub(
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show project status."""
    project_status(json_flag=json_flag)
