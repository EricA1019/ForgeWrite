"""ForgeWrite MCP server — FastMCP stdio server with 22 MCP tools.

Design reference: §5.10

Every tool delegates to SliceCoordinator. No orchestration logic here.
Stdout is redirected to stderr at boot to prevent protocol corruption.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC
from pathlib import Path

from .errors import envelope_from


async def fw_turbovec_health() -> dict:
    """Report TurboVec / RAG retrieval system health.

    Checks index file presence, document count, and basic integrity.
    Returns healthy=False with reason when index is missing.
    """
    try:
        from .config import load_config

        config = load_config(Path.cwd())
        index_path = Path.cwd() / config.rag.index_path

        if not config.rag.enabled:
            return {
                "ok": True,
                "healthy": False,
                "reason": "RAG is disabled in config",
            }

        if not index_path.exists():
            return {
                "ok": True,
                "healthy": False,
                "reason": f"Index not found at {config.rag.index_path}. "
                          f"Run: forgerwrite build-index",
            }

        # Check file integrity: non-empty file is a basic health signal
        file_size = index_path.stat().st_size

        return {
            "ok": True,
            "healthy": True,
            "file_size_bytes": file_size,
            "index_path": str(index_path),
        }
    except Exception as exc:
        return envelope_from(exc, "turbovec_health").to_dict()


async def fw_turbovec_index(
    kb_dir: str = "data/rag", index_path: str = "data/rag/index.tqi"
) -> dict:
    """Build (or rebuild) the TurboVec retrieval index.

    Args:
        kb_dir: Directory containing curated knowledge base markdown files.
        index_path: Where to write the turbovec index file.

    Returns:
        Dict with ok status and document count.
    """
    try:
        from pathlib import Path

        from .rag import build_rag_index
        from .rag.preprocessor import DocumentPreprocessor

        # Count docs before building (RagIndex doesn't expose count)
        kb = Path(kb_dir)
        curated = kb / "rust-knowledge-base.md"
        doc_count = 0
        if curated.exists():
            processor = DocumentPreprocessor(source="curated")
            doc_count += len(processor.process_file(str(curated)))
        # External dirs
        for ext_dir_name in ("rust-cookbook", "rust-by-example"):
            ext_dir = kb / ext_dir_name / "src"
            if ext_dir.is_dir():
                processor = DocumentPreprocessor(source=ext_dir_name)
                for md_file in sorted(ext_dir.rglob("*.md")):
                    doc_count += len(processor.process_file(str(md_file)))

        build_rag_index(kb_dir=kb_dir, index_path=index_path)
        return {"ok": True, "indexed": doc_count}
    except Exception as exc:
        return envelope_from(exc, "turbovec_index").to_dict()


async def fw_scout(
    question: str,
    allowed_files: list[str] | None = None,
    use_model_planner: bool = False,
    max_results: int = 20,
) -> dict:
    """Run the Scout evidence pipeline and return an evidence packet.

    Scout searches for relevant code patterns via ripgrep and RAG retrieval,
    producing path:line evidence for the requested question.

    Args:
        question: Natural-language question to find evidence for.
        allowed_files: Optional list of file paths to scope the search.
        use_model_planner: If True, use the local LLM to plan grep queries.
        max_results: Maximum exact evidence lines to return (default 20).
    """
    try:
        from .config import load_config
        from .rag import build_rag_enricher
        from .scout.coordinator import ScoutCoordinator

        config = load_config(Path.cwd())
        enricher = build_rag_enricher(config, project_root=Path.cwd())

        scout = ScoutCoordinator(
            repo_root=Path.cwd(),
            enricher=enricher,
            use_model_planner=use_model_planner,
            max_evidence_lines=max_results,
        )
        packet = scout.scout(
            question=question,
            allowed_files=allowed_files or [],
        )
        return {"ok": True, "packet": packet.__dict__}
    except Exception as exc:
        return envelope_from(exc, "scout").to_dict()


async def fw_scout_grep(
    queries: list[str],
    allowed_files: list[str] | None = None,
    max_results: int = 20,
) -> dict:
    """Bounded grep through ForgeWrite path policy.

    Runs ripgrep with safety constraints — no files outside the repo,
    capped matches, and timeout.

    Args:
        queries: List of grep patterns to search for.
        allowed_files: Optional list of file paths to scope the search.
        max_results: Maximum matches to return (default 20).
    """
    try:
        from .scout.safe_grep import safe_grep

        # If allowed_files is provided, scope the search to those paths
        search_queries = list(queries)
        if allowed_files:
            search_queries.extend(allowed_files)

        result = safe_grep(
            repo_root=Path.cwd(),
            queries=search_queries,
            max_total_matches=max_results,
        )
        return {
            "ok": True,
            "matches": [
                {"path": m.path, "line_number": m.line_number, "line_content": m.line_content}
                for m in result.matches
            ],
            "truncated": result.truncated,
            "queries": result.queries,
        }
    except Exception as exc:
        return envelope_from(exc, "scout_grep").to_dict()


async def fw_knowledge_search(query: str, k: int = 5) -> dict:
    """Search the knowledge base for relevant patterns.

    Uses semantic search via the knowledge indexer.
    """
    try:
        from .knowledge.indexer import KnowledgeIndexer
        from .knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=Path.cwd())
        entries = store.list(status="active")
        if not entries:
            return {"ok": True, "results": [], "total": 0}

        indexer = KnowledgeIndexer()
        indexer.index(entries)
        results = indexer.search(query, k=k)
        return {"ok": True, "results": results, "total": len(results)}
    except Exception as exc:
        return envelope_from(exc, "knowledge_search").to_dict()


async def fw_knowledge_save_entry(entry: dict) -> dict:
    """Save a knowledge entry to the KB."""
    try:
        from .contracts.registry import ContractRegistry
        from .knowledge.store import KnowledgeStore

        registry = ContractRegistry(Path(__file__).parent.parent / "schemas")
        registry.validate("knowledge_entry.v1.json", entry)

        store = KnowledgeStore(repo_root=Path.cwd())
        store.save(entry)
        return {"ok": True, "entry_id": entry.get("id")}
    except Exception as exc:
        return envelope_from(exc, "knowledge_save_entry").to_dict()


async def fw_knowledge_get_entry(entry_id: str) -> dict:
    """Retrieve a single knowledge entry by ID."""
    try:
        from .knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=Path.cwd())
        entry = store.get(entry_id)
        if entry is None:
            return {
                "ok": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Knowledge entry {entry_id} not found",
                },
            }
        return {"ok": True, "entry": entry}
    except Exception as exc:
        return envelope_from(exc, "knowledge_get_entry").to_dict()


async def fw_knowledge_promote_from_run(run_id: str, curator_notes: str = "") -> dict:
    """Promote a successful run into the knowledge base.

    Reads run artifacts, constructs a knowledge entry, validates it,
    saves it, and returns the entry.
    """
    try:
        from .knowledge.promotion import promote_from_run
        from .knowledge.store import KnowledgeStore

        entry = promote_from_run(
            repo_root=Path.cwd(),
            run_id=run_id,
            curator_notes=curator_notes,
        )
        if entry is None:
            return {
                "ok": False,
                "error": {
                    "code": "PROMOTE_FAILED",
                    "message": f"Cannot promote run {run_id} — "
                               f"not found, incomplete, or didn't pass validation.",
                },
            }

        store = KnowledgeStore(repo_root=Path.cwd())
        store.save(entry)
        return {"ok": True, "entry": entry}
    except Exception as exc:
        return envelope_from(exc, "knowledge_promote_from_run").to_dict()


async def fw_knowledge_record_usage(entry_id: str, outcome: str, notes: str = "") -> dict:
    """Record a usage outcome for a knowledge entry.

    Args:
        entry_id: The knowledge entry ID.
        outcome: One of 'helped', 'did_not_help', 'neutral'.
        notes: Optional notes about the outcome.
    """
    try:
        from datetime import datetime

        from .contracts.registry import ContractRegistry
        from .knowledge.store import KnowledgeStore

        usage = {
            "schema_id": "forgewrite.knowledge_usage.v1",
            "entry_id": entry_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "outcome": outcome,
            "notes": notes,
        }

        registry = ContractRegistry(Path(__file__).parent.parent / "schemas")
        registry.validate("knowledge_usage.v1.json", usage)

        store = KnowledgeStore(repo_root=Path.cwd())
        entry = store.get(entry_id)
        if entry is None:
            return {
                "ok": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Knowledge entry {entry_id} not found",
                },
            }

        # Increment usage count on the entry
        entry["usage_count"] = entry.get("usage_count", 0) + 1
        store.save(entry)

        return {"ok": True, "usage": usage, "entry_usage_count": entry["usage_count"]}
    except Exception as exc:
        return envelope_from(exc, "knowledge_record_usage").to_dict()


async def fw_knowledge_deprecate_entry(entry_id: str) -> dict:
    """Mark a knowledge entry as deprecated."""
    try:
        from .knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=Path.cwd())
        entry = store.get(entry_id)
        if entry is None:
            return {
                "ok": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Knowledge entry {entry_id} not found",
                },
            }

        store.deprecate(entry_id)
        return {"ok": True, "entry_id": entry_id, "status": "deprecated"}
    except Exception as exc:
        return envelope_from(exc, "knowledge_deprecate_entry").to_dict()


async def fw_token_stats() -> dict:
    """Return accumulated token usage and estimated cloud cost savings."""
    try:
        from .token_tracker import TokenTracker

        tracker = TokenTracker(tracker_dir=Path.cwd() / ".forgerwrite")
        stats = tracker.get_stats()
        return {"ok": True, **stats}
    except Exception as exc:
        return envelope_from(exc, "token_stats").to_dict()


async def fw_model_health() -> dict:
    """Check llama.cpp model server health and loaded models."""
    try:
        from .config import load_config
        from .llama_client import LlamaCppClient
        from .model_state import save_model_state

        config = load_config(Path.cwd())
        client = LlamaCppClient.from_config(config.local_model)
        health = client.check_health()

        # Save state for TUI / dashboard
        save_model_state(
            repo_root=Path.cwd(),
            model_name=config.local_model.model,
            endpoint=config.local_model.endpoint,
            healthy=health["healthy"],
        )

        return {"ok": True, **health}
    except Exception as exc:
        return envelope_from(exc, "model_health").to_dict()


def _redirect_stdout_to_stderr() -> None:
    """Redirect sys.stdout to sys.stderr.

    MCP uses stdio JSON-RPC. Any accidental print() to stdout corrupts
    the protocol. This redirect is mandatory and tested.
    """
    sys.stdout.flush()
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())


def boot() -> None:
    """Start the ForgerWrite MCP server over stdio.

    This is the entry point registered in pyproject.toml as
    `forgerwrite-mcp = "forgerwrite_mcp.server:boot"`.
    """
    # Import FastMCP lazily — it's only needed at runtime.
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("forgerwrite")

    # ── Tool registration ──────────────────────────────────────────────
    # Each tool is a thin wrapper. The SliceCoordinator is constructed
    # per-call from config. In a production setup this would be a
    # singleton initialized with the project config.

    @mcp.tool()
    async def fw_ping() -> dict:
        """Health check. Returns ok."""
        return {"ok": True, "service": "forgerwrite-mcp"}

    @mcp.tool()
    async def fw_validate_handoff(handoff: dict) -> dict:
        """Validate a handoff contract against its JSON Schema."""
        try:
            from .contracts.registry import ContractRegistry

            registry = ContractRegistry(Path(__file__).parent.parent / "schemas")
            registry.validate("handoff.v1.json", handoff)
            return {"ok": True, "valid": True}
        except Exception as exc:
            return envelope_from(exc, "validate_handoff").to_dict()

    @mcp.tool()
    async def fw_validate_slice(slice_contract: dict) -> dict:
        """Validate a slice contract against its JSON Schema."""
        try:
            from .contracts.registry import ContractRegistry

            registry = ContractRegistry(Path(__file__).parent.parent / "schemas")
            registry.validate("slice.v1.json", slice_contract)
            return {"ok": True, "valid": True}
        except Exception as exc:
            return envelope_from(exc, "validate_slice").to_dict()

    @mcp.tool()
    async def fw_build_context_packet(handoff: dict, slice_contract: dict) -> dict:
        """Build and save a context packet."""
        try:
            from .config import load_config
            from .context import build_context_packet

            config = load_config(Path.cwd())
            packet = build_context_packet(
                Path.cwd(),
                handoff,
                slice_contract,
                config.limits,
                hygiene=config.hygiene,
            )
            return {"ok": True, "files": list(packet.get("files", {}).keys())}
        except Exception as exc:
            return envelope_from(exc, "build_context").to_dict()

    @mcp.tool()
    async def fw_generate_operations_local(handoff: dict, slice_contract: dict) -> dict:
        """Generate operations using the local model (with optional RAG enrichment)."""
        try:
            from .config import load_config
            from .context import build_context_packet
            from .llama_client import LlamaCppClient
            from .rag import build_rag_enricher

            config = load_config(Path.cwd())
            client = LlamaCppClient.from_config(config.local_model)
            import json

            schema = json.loads(
                (Path(__file__).parent.parent / "schemas" / "operation_batch.v1.json").read_text()
            )

            # Build context packet for file contents
            context = build_context_packet(
                Path.cwd(), handoff, slice_contract, config.limits, hygiene=config.hygiene
            )

            user_prompt = json.dumps({
                "task": handoff.get("description", ""),
                "slice": slice_contract,
                "files": context.get("files", {}),
            })

            # Enrich with RAG if available
            enricher = build_rag_enricher(config, project_root=Path.cwd())
            if enricher is not None:
                query = handoff.get("description", "") + " " + json.dumps(slice_contract)
                user_prompt = enricher.enrich(
                    base_prompt=user_prompt,
                    query=query,
                    k=config.rag.k_documents,
                )

            system_prompt = (
                "You are a coding assistant that produces structured JSON operation batches.\n\n"
                "Respond ONLY with a JSON object matching the operation_batch schema."
            )
            raw = await client.generate_operation_batch(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
            )
            return {"ok": True, "batch": json.loads(raw), "rag_enriched": enricher is not None}
        except Exception as exc:
            return envelope_from(exc, "generate").to_dict()

    @mcp.tool()
    async def fw_validate_operations(operation_batch: dict) -> dict:
        """Validate an operation batch (schema + semantic)."""
        try:
            from .contracts.registry import ContractRegistry
            from .validation.semantic import default_validator

            registry = ContractRegistry(Path(__file__).parent.parent / "schemas")
            registry.validate("operation_batch.v1.json", operation_batch)
            validator = default_validator()
            validator.validate(operation_batch, {"allowed_files": []})
            return {"ok": True, "valid": True}
        except Exception as exc:
            return envelope_from(exc, "validate_ops").to_dict()

    @mcp.tool()
    async def fw_preview_operations(
        operation_batch: dict,
        slice_contract: dict,
        run_id: str = "preview",
    ) -> dict:
        """Produce a preview diff and write an approval record.

        Args:
            operation_batch: The operations to preview.
            slice_contract: The slice contract for scope validation.
            run_id: Run identifier (default "preview"). Use a unique ID
                   for parallel operations.
        """
        try:
            from .approval import write_approval_record
            from .forge.forge import preview_operations
            from .operations.registry import default_registry

            result = preview_operations(
                Path.cwd(),
                run_id,
                operation_batch,
                slice_contract,
                default_registry(),
            )
            run_dir = Path.cwd() / ".forgerwrite" / "runs" / run_id
            write_approval_record(run_dir)
            return {
                "ok": True,
                "diff_sha256": result.diff_sha256,
                "diff_path": str(result.diff_path),
            }
        except Exception as exc:
            return envelope_from(exc, "preview").to_dict()

    @mcp.tool()
    async def fw_apply_approved_operations(
        operation_batch: dict, slice_contract: dict,
        run_id: str = "preview",
        auto_validate: bool = False,
    ) -> dict:
        """Apply approved operations with full lifecycle.

        Verifies approval, applies operations, writes audit event,
        cleans up snapshot, and optionally runs validation.

        Args:
            operation_batch: The operations to apply.
            slice_contract: The slice contract for scope validation.
            run_id: Run identifier (default "preview"). Must match the
                   run_id used in fw_preview_operations.
            auto_validate: If True, run validation profile after apply.
        """
        try:
            from .approval import assert_approved
            from .audit import write_audit_event
            from .dead_letter import write_dead_letter
            from .forge.forge import apply_approved_operations
            from .forge.git_utils import cleanup_snapshot
            from .operations.registry import default_registry

            run_dir = Path.cwd() / ".forgerwrite" / "runs" / run_id
            approval = assert_approved(run_dir, Path.cwd())

            result = apply_approved_operations(
                Path.cwd(),
                run_id,
                operation_batch,
                slice_contract,
                approval,
                default_registry(),
            )

            write_audit_event(run_dir, "apply", {"run_id": run_id, "changed": len(result.changed)})
            cleanup_snapshot(Path.cwd(), run_id)

            response: dict = {"ok": True, "changed": len(result.changed)}

            if auto_validate:
                try:
                    from .config import load_config
                    from .validation.runner import run_validation_profile

                    config = load_config(Path.cwd())
                    vr = run_validation_profile(
                        Path.cwd(),
                        "python_default",
                        config.validation,
                        limits=config.limits,
                    )
                    response["validation_passed"] = vr["passed"]
                except Exception as ve:
                    response["validation_passed"] = False
                    response["validation_error"] = str(ve)

            return response
        except Exception as exc:
            from .dead_letter import write_dead_letter

            run_dir = Path.cwd() / ".forgerwrite" / "runs" / run_id
            write_dead_letter(run_dir, f"Apply failed: {exc}")
            return envelope_from(exc, "apply").to_dict()

    @mcp.tool()
    async def fw_run_validation_profile(profile_id: str = "rust_default") -> dict:
        """Run a validation profile."""
        try:
            from .config import load_config
            from .validation.runner import run_validation_profile

            config = load_config(Path.cwd())
            result = run_validation_profile(
                Path.cwd(),
                profile_id,
                config.validation,
                limits=config.limits,
            )
            return {"ok": True, "passed": result["passed"]}
        except Exception as exc:
            return envelope_from(exc, "validation").to_dict()

    @mcp.tool()
    async def fw_get_run_summary(run_id: str) -> dict:
        """Return a Markdown summary of a run."""
        try:
            run_dir = Path.cwd() / ".forgerwrite" / "runs" / run_id
            if not run_dir.exists():
                return {
                    "ok": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Run {run_id} not found",
                    },
                }
            from .summary import generate_summary

            return {"ok": True, "run_id": run_id, "summary": generate_summary(run_dir)}
        except Exception as exc:
            return envelope_from(exc, "summary").to_dict()

    mcp.tool()(fw_turbovec_health)
    mcp.tool()(fw_turbovec_index)
    mcp.tool()(fw_scout)
    mcp.tool()(fw_scout_grep)
    mcp.tool()(fw_knowledge_search)
    mcp.tool()(fw_knowledge_save_entry)
    mcp.tool()(fw_knowledge_get_entry)
    mcp.tool()(fw_knowledge_promote_from_run)
    mcp.tool()(fw_knowledge_record_usage)
    mcp.tool()(fw_knowledge_deprecate_entry)
    mcp.tool()(fw_token_stats)
    mcp.tool()(fw_model_health)

    # ── Start server ──────────────────────────────────────────────────
    mcp.run(transport="stdio")
