"""ForgeWrite TUI — terminal dashboard for tokens, runs, and system status.

Built with Textual. Single-screen dashboard with side-by-side panels.
Auto-refreshes every 30 seconds.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

# ── Data providers (imported lazily at call time) ────────────────────────────


def _get_token_stats() -> dict:
    from .token_tracker import TokenTracker

    tracker = TokenTracker(tracker_dir=Path.cwd() / ".forgerwrite")
    return tracker.get_stats()


def _get_run_summary() -> list[dict]:
    runs_dir = Path.cwd() / ".forgerwrite" / "runs"
    if not runs_dir.is_dir():
        return []
    results: list[dict] = []
    import json as _json

    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        if run_dir.is_dir():
            run_json = run_dir / "run.json"
            if run_json.exists():
                try:
                    data = _json.loads(run_json.read_text())
                    # Load dead letter for error detail
                    error = ""
                    dead_letter = run_dir / "dead_letter.json"
                    if dead_letter.exists():
                        try:
                            dl = _json.loads(dead_letter.read_text())
                            error = dl.get("reason", "")[:60]
                        except Exception:
                            pass
                    results.append({
                        "run_id": data.get("run_id", run_dir.name),
                        "status": data.get("status", "unknown"),
                        "slice_id": data.get("slice_id", ""),
                        "created_at": data.get("created_at", ""),
                        "error": error,
                    })
                except Exception:
                    pass
    return results[:20]


def _get_kb_summary() -> dict:
    from .knowledge.store import KnowledgeStore

    store = KnowledgeStore(repo_root=Path.cwd())
    entries = store.list()
    active = sum(1 for e in entries if e.get("status") == "active")
    deprecated = sum(1 for e in entries if e.get("status") == "deprecated")
    return {"total": len(entries), "active": active, "deprecated": deprecated}


def _get_system_status() -> list[tuple[str, bool, str]]:
    from .integrations import get_all_info

    info = get_all_info(Path.cwd())
    result: list[tuple[str, bool, str]] = []
    for name, i in info.items():
        avail = i["available"]
        reason = "" if avail else i.get("reason", "")
        result.append((name, avail, reason))
    return result


def _get_model_health() -> dict:
    try:
        from .config import load_config
        from .llama_client import LlamaCppClient

        config = load_config(Path.cwd())
        client = LlamaCppClient.from_config(config.local_model)
        return client.check_health()
    except Exception:
        return {"healthy": False, "model_name": "unknown", "error": "config failure"}


_STATUS_EMOJI: dict[str, str] = {
    "validation_passed": "✅",
    "applied": "✅",
    "passed": "✅",
    "draft": "📝",
    "context_ready": "📦",
    "validation_failed": "❌",
    "failed": "❌",
    "repairing": "🔧",
    "approved": "👍",
    "preview_ready": "👁️",
    "aborted": "🚫",
}


# ── App ─────────────────────────────────────────────────────────────────────


class ForgerwriteTUI(App):
    """Terminal dashboard for ForgeWrite.

    Displays token usage, recent runs, knowledge base status, and
    system integration health. Auto-refreshes every 30 seconds.
    """

    CSS = """
    Horizontal > Vertical { margin: 1; }
    Static { padding: 1; }
    #token-panel  { width: 35%; border: solid $primary; }
    #run-panel    { width: 35%; border: solid $accent; }
    #info-panel   { width: 30%; border: solid $success; }
    #token-title  { text-style: bold; color: $primary; }
    #run-title    { text-style: bold; color: $accent; }
    #info-title   { text-style: bold; color: $success; }
    """

    TITLE = "ForgeWrite Dashboard"
    SUB_TITLE = "Tokens \u00b7 Runs \u00b7 Knowledge \u00b7 System"
    BINDINGS = [("r", "refresh", "Refresh"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="token-panel"):
                yield Static("\U0001f4ca  Tokens", id="token-title")
                yield Static("Loading...", id="token-content")
            with Vertical(id="run-panel"):
                yield Static("\U0001f504  Recent Runs", id="run-title")
                yield Static("Loading...", id="run-content")
            with Vertical(id="info-panel"):
                yield Static("\U0001f4da  Knowledge + System", id="info-title")
                yield Static("Loading...", id="info-content")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(30, self.refresh_data)

    def action_refresh(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            stats = _get_token_stats()
            self.query_one("#token-content").update(self._render_tokens(stats))
        except Exception:
            self.query_one("#token-content").update("Error loading tokens")

        try:
            runs = _get_run_summary()
            self.query_one("#run-content").update(self._render_runs(runs))
        except Exception:
            self.query_one("#run-content").update("Error loading runs")

        try:
            kb = _get_kb_summary()
            sys_status = _get_system_status()
            model_health = _get_model_health()
            self.query_one("#info-content").update(
                self._render_info(kb, sys_status, model_health)
            )
        except Exception:
            self.query_one("#info-content").update("Error loading info")

    @staticmethod
    def _render_tokens(stats: dict) -> str:
        if stats["total_calls"] == 0:
            return (
                "No token data yet.\n"
                "Run fw_generate_operations_local to start tracking."
            )
        lines = [
            f"Total calls:  {stats['total_calls']}",
            f"Input tokens: {stats['total_input_tokens']:,}",
            f"Output tokens: {stats['total_output_tokens']:,}",
            f"Total tokens: {stats['total_tokens']:,}",
            "",
            "\U0001f4b0 Saved vs cloud:",
        ]
        for key in ("claude", "gpt4o"):
            s = stats["estimated_savings"][key]
            lines.append(f"  {s['label']}: ${s['total']:.4f}")

        if stats.get("by_model"):
            lines.append("")
            lines.append("By model:")
            for model, m in sorted(stats["by_model"].items()):
                name = model[:35]
                lines.append(f"  {name}: {m['calls']} calls, {m['total_tokens']:,} tokens")

        return "\n".join(lines)

    @staticmethod
    def _render_runs(runs: list[dict]) -> str:
        if not runs:
            return "No runs yet.\nRun a ForgeWrite pipeline to see results here."
        lines: list[str] = []
        for r in runs[:15]:
            emoji = _STATUS_EMOJI.get(r["status"], "\u2753")
            rid = r["run_id"][:25]
            sid = r.get("slice_id", "")[:20]
            lines.append(f"{emoji} {rid}")
            if sid:
                lines.append(f"   [{r['status']}] {sid}")
            else:
                lines.append(f"   [{r['status']}]")
        return "\n".join(lines)

    @staticmethod
    def _render_info(
        kb: dict,
        sys_status: list[tuple[str, bool, str]],
        model_health: dict,
    ) -> str:
        # Model health vars used multiple times below
        model_ok = model_health.get("healthy", False)
        model_emoji = "\u2705" if model_ok else "\u274c"
        model_name = model_health.get("model_name", "unknown")[:30]
        model_err = model_health.get("error", "")

        lines = [
            f"Model: {model_emoji} {model_name}",
            "",
            f"\U0001f4da KB: {kb['active']} active, {kb['deprecated']} deprecated "
            f"({kb['total']} total)",
            "",
            "\U0001f50c System:",
        ]
        for name, avail, reason in sys_status:
            emoji = "\u2705" if avail else "\u26a0\ufe0f"
            detail = "" if avail else f" \u2014 {reason[:40]}"
            lines.append(f"  {emoji} {name}{detail}")

        if not model_ok and model_err:
            lines.append(f"     \u26a0\ufe0f {model_err[:50]}")

        # Loaded models
        loaded = model_health.get("loaded_models", [])
        if loaded:
            lines.append(f"     Loaded: {len(loaded)} model(s)")
            for m in loaded[:3]:
                lines.append(f"       \u2022 {m[:40]}")

        lines.append("")
        lines.append("Keys: r=refresh q=quit")
        return "\n".join(lines)


def run_tui() -> None:
    """Entry point for `forgerwrite tui`."""
    app = ForgerwriteTUI()
    app.run()
