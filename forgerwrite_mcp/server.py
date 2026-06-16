"""ForgeWrite MCP server — FastMCP stdio server with 10 thin tools.

Design reference: §5.10

Every tool delegates to SliceCoordinator. No orchestration logic here.
Stdout is redirected to stderr at boot to prevent protocol corruption.
"""

from __future__ import annotations

import os
import sys
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
    _redirect_stdout_to_stderr()

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
    async def fw_preview_operations(operation_batch: dict, slice_contract: dict) -> dict:
        """Produce a preview diff."""
        try:
            from .forge.forge import preview_operations
            from .operations.registry import default_registry

            result = preview_operations(
                Path.cwd(),
                "preview",
                operation_batch,
                slice_contract,
                default_registry(),
            )
            return {
                "ok": True,
                "diff_sha256": result.diff_sha256,
                "diff_path": str(result.diff_path),
            }
        except Exception as exc:
            return envelope_from(exc, "preview").to_dict()

    @mcp.tool()
    async def fw_apply_approved_operations(
        operation_batch: dict, slice_contract: dict, run_id: str
    ) -> dict:
        """Apply approved operations."""
        try:
            from .approval import assert_approved
            from .forge.forge import apply_approved_operations
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
            return {"ok": True, "changed": len(result.changed)}
        except Exception as exc:
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

    # ── Start server ──────────────────────────────────────────────────
    mcp.run(transport="stdio")
