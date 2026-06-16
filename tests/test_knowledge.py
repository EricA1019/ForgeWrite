"""Tests for Saved Work KB — schemas, store, promotion, indexer."""

from __future__ import annotations

from pathlib import Path

import pytest


# ── Constants ────────────────────────────────────────────────────────────────

_VALID_ENTRY = {
    "schema_id": "forgewrite.knowledge_entry.v1",
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Fix unresolved import",
    "description": "Use the exact crate name from Cargo.toml, never append _lib.",
    "tags": ["rust", "import", "compile-error"],
    "language": "rust",
    "source_run_id": "run-2026-06-16-001",
    "problem_statement": "Rust compiler says unresolved import when the crate exists.",
    "operations": [
        {"op": "replace_file", "path": "src/main.rs", "content": "use calc::add;\nfn main() {}\n"}
    ],
    "validation_summary": {
        "passed": True,
        "commands_run": ["cargo check", "cargo test"]
    },
    "status": "active",
    "curator_notes": "Common error in Rust dogfood slices.",
    "created_at": "2026-06-16T12:00:00Z",
    "promoted_at": "2026-06-16T12:30:00Z",
    "usage_count": 3,
}

_VALID_USAGE = {
    "schema_id": "forgewrite.knowledge_usage.v1",
    "entry_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-06-16T13:00:00Z",
    "context_slice_id": "slice-abc-123",
    "outcome": "helped",
    "notes": "Fixed the compile error immediately.",
}

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


# ── Schema tests ─────────────────────────────────────────────────────────────


class TestKnowledgeEntrySchema:
    """Contract tests for knowledge_entry.v1.json."""

    def test_valid_entry_passes_validation(self) -> None:
        """A well-formed knowledge entry passes Draft 2020-12 validation."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        registry = ContractRegistry(_SCHEMAS_DIR)
        registry.validate("knowledge_entry.v1.json", _VALID_ENTRY)

    def test_missing_title_fails(self) -> None:
        """Entry without title must fail."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(_SCHEMAS_DIR)
        entry = {**{k: v for k, v in _VALID_ENTRY.items() if k != "title"}}
        with pytest.raises(ContractValidationError):
            registry.validate("knowledge_entry.v1.json", entry)

    def test_empty_problem_statement_fails(self) -> None:
        """Entry with empty problem_statement must fail."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(_SCHEMAS_DIR)
        entry = {**_VALID_ENTRY, "problem_statement": ""}
        with pytest.raises(ContractValidationError):
            registry.validate("knowledge_entry.v1.json", entry)

    def test_invalid_status_fails(self) -> None:
        """Entry with status outside enum must fail."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(_SCHEMAS_DIR)
        entry = {**_VALID_ENTRY, "status": "deleted"}
        with pytest.raises(ContractValidationError):
            registry.validate("knowledge_entry.v1.json", entry)

    def test_draft_entry_without_promoted_at_is_valid(self) -> None:
        """A draft entry may omit promoted_at."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        registry = ContractRegistry(_SCHEMAS_DIR)
        draft = {
            **_VALID_ENTRY,
            "status": "draft",
            "promoted_at": None,  # Remove promoted_at
        }
        del draft["promoted_at"]
        registry.validate("knowledge_entry.v1.json", draft)

    def test_negative_usage_count_fails(self) -> None:
        """Entry with negative usage_count must fail."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(_SCHEMAS_DIR)
        entry = {**_VALID_ENTRY, "usage_count": -1}
        with pytest.raises(ContractValidationError):
            registry.validate("knowledge_entry.v1.json", entry)


class TestKnowledgeUsageSchema:
    """Contract tests for knowledge_usage.v1.json."""

    def test_valid_usage_passes_validation(self) -> None:
        """A well-formed usage record passes validation."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        registry = ContractRegistry(_SCHEMAS_DIR)
        registry.validate("knowledge_usage.v1.json", _VALID_USAGE)

    def test_missing_outcome_fails(self) -> None:
        """Usage record without outcome must fail."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(_SCHEMAS_DIR)
        rec = {k: v for k, v in _VALID_USAGE.items() if k != "outcome"}
        with pytest.raises(ContractValidationError):
            registry.validate("knowledge_usage.v1.json", rec)

    def test_invalid_outcome_fails(self) -> None:
        """Usage record with outcome outside enum must fail."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(_SCHEMAS_DIR)
        rec = {**_VALID_USAGE, "outcome": "maybe"}
        with pytest.raises(ContractValidationError):
            registry.validate("knowledge_usage.v1.json", rec)

    def test_usage_without_notes_is_valid(self) -> None:
        """Usage record without notes is still valid."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        registry = ContractRegistry(_SCHEMAS_DIR)
        rec = {k: v for k, v in _VALID_USAGE.items() if k != "notes"}
        registry.validate("knowledge_usage.v1.json", rec)


# ── Store tests ──────────────────────────────────────────────────────────────

_KNOWLEDGE_DIR_NAME = ".forgerwrite/knowledge"


class TestKnowledgeStore:
    """Tests for file-backed KnowledgeStore."""

    def test_save_and_get_entry(self, tmp_path: Path) -> None:
        """Saving an entry and getting it back returns the same data."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        store.save(_VALID_ENTRY)
        found = store.get("550e8400-e29b-41d4-a716-446655440000")
        assert found is not None
        assert found["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert found["title"] == "Fix unresolved import"

    def test_get_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Getting a missing entry returns None."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        assert store.get("nonexistent-id") is None

    def test_list_all_entries(self, tmp_path: Path) -> None:
        """Listing entries returns all saved entries."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        store.save({**_VALID_ENTRY, "id": "id-1", "status": "active"})
        store.save({**_VALID_ENTRY, "id": "id-2", "status": "draft"})
        store.save({**_VALID_ENTRY, "id": "id-3", "status": "active"})

        all_entries = store.list()
        assert len(all_entries) == 3

    def test_list_filter_by_status(self, tmp_path: Path) -> None:
        """Listing entries with status filter returns only matching."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        store.save({**_VALID_ENTRY, "id": "id-1", "status": "active"})
        store.save({**_VALID_ENTRY, "id": "id-2", "status": "draft"})
        store.save({**_VALID_ENTRY, "id": "id-3", "status": "deprecated"})

        active = store.list(status="active")
        assert len(active) == 1
        assert active[0]["id"] == "id-1"

    def test_list_empty_store(self, tmp_path: Path) -> None:
        """Listing an empty store returns empty list."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        assert store.list() == []

    def test_deprecate_entry(self, tmp_path: Path) -> None:
        """Deprecating an entry sets status to deprecated."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        store.save(_VALID_ENTRY)
        store.deprecate("550e8400-e29b-41d4-a716-446655440000")
        found = store.get("550e8400-e29b-41d4-a716-446655440000")
        assert found is not None
        assert found["status"] == "deprecated"

    def test_deprecate_nonexistent_is_noop(self, tmp_path: Path) -> None:
        """Deprecating a missing entry does nothing (no crash)."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        store.deprecate("nonexistent-id")  # Should not raise

    def test_entries_persist_on_disk(self, tmp_path: Path) -> None:
        """Entries are written to disk as JSON files."""
        from forgerwrite_mcp.knowledge.store import KnowledgeStore

        store = KnowledgeStore(repo_root=tmp_path)
        store.save(_VALID_ENTRY)

        expected_path = (
            tmp_path / _KNOWLEDGE_DIR_NAME / "550e8400-e29b-41d4-a716-446655440000.json"
        )
        assert expected_path.exists()


# ── Promotion tests ──────────────────────────────────────────────────────────

_RUN_DIR = ".forgerwrite/runs"


class TestKnowledgePromotion:
    """Tests for promoting a run to a knowledge entry."""

    @staticmethod
    def _make_run_dir(repo_root: Path, run_id: str) -> Path:
        run_dir = repo_root / _RUN_DIR / run_id
        run_dir.mkdir(parents=True)
        return run_dir

    def test_promote_successful_run(self, tmp_path: Path) -> None:
        """Promoting a run with complete artifacts creates a valid entry."""
        from forgerwrite_mcp.knowledge.promotion import promote_from_run

        # Set up a fake run with artifacts
        run_dir = self._make_run_dir(tmp_path, "run-001")
        (run_dir / "run.json").write_text(
            '{"schema_id":"forgewrite.run.v1","run_id":"run-001",'
            '"slice_id":"slice-abc","status":"validation_passed",'
            '"language":"rust","created_at":"2026-06-16T12:00:00Z"}'
        )
        (run_dir / "operation_batch.json").write_text(
            '{"batch_id":"b1","slice_id":"slice-abc","operations":['
            '{"op":"create_file","path":"src/main.rs","content":"fn main() {}"}]}'
        )
        (run_dir / "context_packet.json").write_text(
            '{"handoff":{"description":"Add a main function","project":"test","language":"rust"}}'
        )

        entry = promote_from_run(
            repo_root=tmp_path,
            run_id="run-001",
            curator_notes="Common scaffold pattern.",
        )

        assert entry["schema_id"] == "forgewrite.knowledge_entry.v1"
        assert entry["status"] == "draft"
        assert entry["language"] == "rust"
        assert entry["source_run_id"] == "run-001"
        assert entry["curator_notes"] == "Common scaffold pattern."
        assert len(entry["operations"]) == 1
        assert entry["title"] != ""  # Auto-generated title

    def test_promote_missing_run_returns_none(self, tmp_path: Path) -> None:
        """Promoting a nonexistent run returns None."""
        from forgerwrite_mcp.knowledge.promotion import promote_from_run

        entry = promote_from_run(
            repo_root=tmp_path,
            run_id="no-such-run",
            curator_notes="test",
        )
        assert entry is None

    def test_promote_validation_failed_run(self, tmp_path: Path) -> None:
        """Promoting a run that failed validation returns None."""
        from forgerwrite_mcp.knowledge.promotion import promote_from_run

        run_dir = self._make_run_dir(tmp_path, "run-fail")
        (run_dir / "run.json").write_text(
            '{"schema_id":"forgewrite.run.v1","run_id":"run-fail",'
            '"slice_id":"slice-fail","status":"validation_failed",'
            '"language":"python","created_at":"2026-06-16T12:00:00Z"}'
        )
        (run_dir / "operation_batch.json").write_text(
            '{"batch_id":"b1","slice_id":"slice-fail","operations":[]}'
        )

        entry = promote_from_run(
            repo_root=tmp_path,
            run_id="run-fail",
            curator_notes="test",
        )
        assert entry is None

    def test_promote_generates_reasonable_title(self, tmp_path: Path) -> None:
        """The auto-generated title uses the handoff description."""
        from forgerwrite_mcp.knowledge.promotion import promote_from_run

        run_dir = self._make_run_dir(tmp_path, "run-002")
        (run_dir / "run.json").write_text(
            '{"schema_id":"forgewrite.run.v1","run_id":"run-002",'
            '"slice_id":"slice-002","status":"validation_passed",'
            '"language":"python","created_at":"2026-06-16T12:00:00Z"}'
        )
        (run_dir / "operation_batch.json").write_text(
            '{"batch_id":"b1","slice_id":"slice-002","operations":['
            '{"op":"replace_file","path":"src/calc.py","content":"def add(a,b): return a+b"}]}'
        )
        (run_dir / "context_packet.json").write_text(
            '{"handoff":{"description":"Fix the calculator to return correct sum","project":"test","language":"python"}}'
        )

        entry = promote_from_run(
            repo_root=tmp_path,
            run_id="run-002",
        )

        assert entry is not None
        # Title should be derived from the handoff description
        assert "calculator" in entry["title"].lower() or "fix" in entry["title"].lower()


# ── Indexer tests ────────────────────────────────────────────────────────────


class TestKnowledgeIndexer:
    """Tests for indexing knowledge entries into TurboVec."""

    def test_index_and_search_returns_results(self) -> None:
        """Indexing entries and searching returns relevant results."""
        from forgerwrite_mcp.knowledge.indexer import KnowledgeIndexer

        entries = [
            {
                "id": "e1",
                "title": "Fix Rust unresolved import",
                "description": "Use the exact crate name from Cargo.toml.",
                "problem_statement": "Rust compiler says unresolved import.",
            },
            {
                "id": "e2",
                "title": "Python async HTTP client",
                "description": "Use httpx.AsyncClient for async HTTP.",
                "problem_statement": "Need to make async HTTP requests in Python.",
            },
            {
                "id": "e3",
                "title": "Fix pytest fixture scope",
                "description": "Use session-scoped fixtures for shared setup.",
                "problem_statement": "Fixtures are recreated for every test.",
            },
        ]

        indexer = KnowledgeIndexer()
        indexer.index(entries)

        results = indexer.search("Rust import problem", k=2)
        assert len(results) > 0
        # The Rust import entry should be the top result
        assert results[0]["id"] == "e1"

    def test_search_empty_index_returns_empty(self) -> None:
        """Searching an empty index returns an empty list."""
        from forgerwrite_mcp.knowledge.indexer import KnowledgeIndexer

        indexer = KnowledgeIndexer()
        results = indexer.search("anything")
        assert results == []

    def test_search_finds_second_best(self) -> None:
        """When the best match isn't first by ID, still find relevant results."""
        from forgerwrite_mcp.knowledge.indexer import KnowledgeIndexer

        entries = [
            {
                "id": "a",
                "title": "Generic stuff",
                "description": "Various things.",
                "problem_statement": "Generic problem.",
            },
            {
                "id": "b",
                "title": "Python asyncio guide",
                "description": "How to use asyncio for concurrent code.",
                "problem_statement": "Need to run multiple coroutines concurrently.",
            },
        ]

        indexer = KnowledgeIndexer()
        indexer.index(entries)

        results = indexer.search("concurrent async Python", k=1)
        assert len(results) == 1
        assert results[0]["id"] == "b"

    def test_search_respects_k_limit(self) -> None:
        """Search respects the k limit even with many entries."""
        from forgerwrite_mcp.knowledge.indexer import KnowledgeIndexer

        entries = [
            {
                "id": f"e{i}",
                "title": f"Entry {i}",
                "description": f"Description {i}.",
                "problem_statement": f"Problem {i}.",
            }
            for i in range(10)
        ]

        indexer = KnowledgeIndexer()
        indexer.index(entries)

        results = indexer.search("some query", k=3)
        assert len(results) <= 3
