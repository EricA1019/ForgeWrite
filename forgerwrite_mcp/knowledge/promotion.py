"""Knowledge promotion — extract patterns from successful ForgeWrite runs.

Reads run artifacts and constructs a ``knowledge_entry.v1``-compatible dict.
Non-destructive: never modifies the original run artifacts.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

_RUN_DIR = ".forgerwrite/runs"

_SUCCESS_STATUSES: frozenset[str] = frozenset({
    "validation_passed",
    "applied",
})

# ── Public API ───────────────────────────────────────────────────────────────


def promote_from_run(
    repo_root: Path,
    run_id: str,
    curator_notes: str = "",
) -> dict[str, Any] | None:
    """Promote a successful run into a knowledge entry.

    Reads ``run.json``, ``operation_batch.json``, and ``context_packet.json``
    from ``.forgerwrite/runs/<run_id>/``. Only promotes runs whose status
    indicates success (validation_passed, applied).

    Args:
        repo_root: The repository root directory.
        run_id: The run identifier to promote.
        curator_notes: Optional notes from the promoting agent.

    Returns:
        A knowledge-entry dict ready for ``KnowledgeStore.save()``, or
        ``None`` if the run doesn't exist, is incomplete, or didn't pass.
    """
    run_dir = repo_root.resolve() / _RUN_DIR / run_id
    if not run_dir.is_dir():
        return None

    # Read and validate run metadata
    run_json_path = run_dir / "run.json"
    if not run_json_path.exists():
        return None

    try:
        run_data = json.loads(run_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    status = run_data.get("status", "")
    if status not in _SUCCESS_STATUSES:
        return None

    # Read operations
    ops_json_path = run_dir / "operation_batch.json"
    operations: list[dict[str, Any]] = []
    if ops_json_path.exists():
        try:
            ops_data = json.loads(ops_json_path.read_text(encoding="utf-8"))
            operations = ops_data.get("operations", [])
        except (json.JSONDecodeError, OSError):
            pass

    # Read context for handoff description
    handoff_description = ""
    ctx_path = run_dir / "context_packet.json"
    if ctx_path.exists():
        try:
            ctx_data = json.loads(ctx_path.read_text(encoding="utf-8"))
            handoff = ctx_data.get("handoff", {})
            handoff_description = handoff.get("description", "")
        except (json.JSONDecodeError, OSError):
            pass

    # Generate title from handoff description
    title = _generate_title(handoff_description, operations, run_data.get("language", "unknown"))

    language = run_data.get("language", "unknown")
    tags = _generate_tags(language, handoff_description)

    now = datetime.now(UTC).isoformat()

    return {
        "schema_id": "forgewrite.knowledge_entry.v1",
        "id": str(uuid.uuid4()),
        "title": title,
        "description": handoff_description or title,
        "tags": tags,
        "language": language,
        "source_run_id": run_id,
        "problem_statement": handoff_description,
        "operations": operations,
        "validation_summary": {
            "passed": True,
            "commands_run": [],
        },
        "status": "draft",
        "curator_notes": curator_notes,
        "created_at": now,
        "usage_count": 0,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

_TITLE_MAX_LEN: int = 100


def _generate_title(description: str, operations: list[dict[str, Any]], language: str) -> str:
    """Generate a short title from the description or first operation."""
    if description:
        # Use first sentence or first 100 chars
        title = description.split(".")[0].strip()
        if len(title) > _TITLE_MAX_LEN:
            title = title[:_TITLE_MAX_LEN - 3] + "..."
        if title:
            return title

    # Fallback: use first operation type
    if operations:
        first_op = operations[0]
        op_type = first_op.get("op", "unknown")
        file_path = first_op.get("path", "unknown")
        return f"{language}: {op_type} on {file_path}"

    return f"{language}: unknown pattern"


def _generate_tags(language: str, description: str) -> list[str]:
    """Generate search tags from language and description keywords."""
    tags = [language]
    # Simple keyword extraction from description
    keywords = {
        "error": "error",
        "fix": "fix",
        "import": "import",
        "compile": "compile-error",
        "test": "test",
        "refactor": "refactor",
        "create": "create",
        "delete": "delete",
        "replace": "replace",
        "async": "async",
        "scaffold": "scaffold",
    }
    lower = description.lower()
    for word, tag in keywords.items():
        if word in lower and tag not in tags:
            tags.append(tag)
    return tags
