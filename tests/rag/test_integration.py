"""Integration tests: RAG pipeline wired through SliceCoordinator (C8-C9)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


# ── Helpers ─────────────────────────────────────────────────────────────────


def _init_repo(tmp_path: Path) -> None:
    """Create a minimal git repo with a basic Rust project."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Minimal Rust project
    cargo = tmp_path / "Cargo.toml"
    cargo.write_text('[package]\nname = "test"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n')

    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    (src / "main.rs").write_text('fn main() {\n    println!("hello");\n}\n')
    (src / "lib.rs").write_text("")

    subprocess.run(
        ["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True
    )


def _write_config(tmp_path: Path, *, rag_enabled: bool = True) -> None:
    """Write a minimal forgerwrite.toml."""
    cfg_dir = tmp_path / ".forgerwrite"
    cfg_dir.mkdir()

    rag = "true" if rag_enabled else "false"
    config = f"""
[project]
name = "test"
language = "rust"
repo_root = "."

[local_model]
provider = "llama_cpp"
endpoint = "http://127.0.0.1:8080/v1"
model = "test-model"
temperature = 1.0
top_p = 0.95
top_k = 64
max_tokens = 4096

[limits]
context_file_max_bytes = 200000

[validation]
commands = {{ fmt = "echo ok", check = "echo ok", test = "echo ok" }}
profiles = {{ rust_default = ["fmt", "check", "test"] }}
default_timeout_seconds = 300

[permissions]
require_clean_worktree = false
require_approval_for_new_dependencies = false
require_approval_for_delete = false
require_approval_for_full_file_replace = false

[hygiene]
generated_globs = ["target/**"]

[repair]
max_attempts = 0

[rag]
enabled = {rag}
index_path = "data/rag/index.tqi"
k_documents = 3
max_rag_tokens = 2048
"""
    (cfg_dir / "forgerwrite.toml").write_text(config)


def _build_mini_index(tmp_path: Path) -> None:
    """Build a small turbovec index with test documents in the tmp repo."""
    import numpy as np
    from turbovec import TurboQuantIndex
    from sentence_transformers import SentenceTransformer

    from forgerwrite_mcp.rag.retriever import RagDocument

    docs = [
        RagDocument(
            doc_id="rust-edition",
            title="Edition rules",
            content="ALWAYS use edition = 2021. The gen keyword is reserved in 2024.",
        ),
        RagDocument(
            doc_id="fix-import",
            title="Fix wrong crate name",
            content="Error: unresolved import calc_lib. Use exact Cargo.toml name.",
        ),
        RagDocument(
            doc_id="create-file-template",
            title="create_file template",
            content='{"op": "create_file", "path": "x.rs", "content": "fn main() {}\\n"}',
        ),
        RagDocument(
            doc_id="clap-pattern",
            title="clap v4 CLI pattern",
            content="use clap::Parser; #[derive(Parser)] enum Cli { Add { a: i32, b: i32 } }",
        ),
        RagDocument(
            doc_id="scaffold-cargo",
            title="Cargo.toml template",
            content='[package] name = "crate" version = "0.1.0" edition = "2021"',
        ),
    ]

    model = SentenceTransformer("Alibaba-NLP/gte-modernbert-base", device="cpu")
    vectors = np.array([model.encode(d.embeddable_text) for d in docs]).astype(np.float32)
    idx = TurboQuantIndex(dim=vectors.shape[1], bit_width=4)
    idx.add(vectors)

    # Also write a minimal KB file so build_rag_enricher can find it
    kb_dir = tmp_path / "data" / "rag"
    kb_dir.mkdir(parents=True, exist_ok=True)
    kb_content = """# Test KB

<!-- RAG-ID: rust-edition -->
### Edition rules
ALWAYS use edition = "2021". The gen keyword is reserved in 2024.

<!-- RAG-ID: fix-import -->
### Fix wrong crate name
Error: unresolved import calc_lib. Use exact Cargo.toml name.

<!-- RAG-ID: create-file-template -->
### create_file template
{"op": "create_file", "path": "x.rs", "content": "fn main() {}\\n"}

<!-- RAG-ID: clap-pattern -->
### clap v4 CLI pattern
use clap::Parser; #[derive(Parser)] enum Cli { Add { a: i32, b: i32 } }

<!-- RAG-ID: scaffold-cargo -->
### Cargo.toml template
[package] name = "crate" version = "0.1.0" edition = "2021"
"""
    (kb_dir / "rust-knowledge-base.md").write_text(kb_content)

    idx_path = tmp_path / "data" / "rag" / "index.tqi"
    idx.write(str(idx_path))


class FakeBackend:
    """A fake model backend that records the prompt it received."""

    def __init__(self) -> None:
        self.last_system_prompt: str = ""
        self.last_user_prompt: str = ""

    async def generate_operation_batch(
        self, system_prompt: str, user_prompt: str, schema: dict
    ) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return '{"batch_id":"test","slice_id":"s1","operations":[]}'


# ── Tests ───────────────────────────────────────────────────────────────────


class TestRagCoordinatorIntegration:
    """Full pipeline: config → enricher → coordinator → enriched prompt."""

    def test_build_rag_enricher_from_config_returns_enricher(self, tmp_path: Path):
        """When RAG is enabled and index exists, build_rag_enricher returns enricher."""
        _init_repo(tmp_path)
        _write_config(tmp_path, rag_enabled=True)
        _build_mini_index(tmp_path)

        from forgerwrite_mcp.config import load_config
        from forgerwrite_mcp.rag import build_rag_enricher

        config = load_config(tmp_path)
        enricher = build_rag_enricher(config, project_root=tmp_path)
        assert enricher is not None
        assert enricher._max_rag_tokens == 2048

    def test_build_rag_enricher_returns_none_when_disabled(self, tmp_path: Path):
        """When RAG is disabled, build_rag_enricher returns None."""
        _init_repo(tmp_path)
        _write_config(tmp_path, rag_enabled=False)

        from forgerwrite_mcp.config import load_config
        from forgerwrite_mcp.rag import build_rag_enricher

        config = load_config(tmp_path)
        enricher = build_rag_enricher(config)
        assert enricher is None

    def test_build_rag_enricher_returns_none_when_index_missing(self, tmp_path: Path):
        """When index file doesn't exist, build_rag_enricher returns None."""
        _init_repo(tmp_path)
        _write_config(tmp_path, rag_enabled=True)
        # Don't build index

        from forgerwrite_mcp.config import load_config
        from forgerwrite_mcp.rag import build_rag_enricher

        config = load_config(tmp_path)
        enricher = build_rag_enricher(config, project_root=tmp_path)
        assert enricher is None

    def test_coordinator_enriches_prompt_with_rag(self, tmp_path: Path):
        """Coordinator with enricher injects RELEVANT KNOWLEDGE into the prompt."""
        _init_repo(tmp_path)
        _write_config(tmp_path, rag_enabled=True)
        _build_mini_index(tmp_path)

        from forgerwrite_mcp.config import load_config
        from forgerwrite_mcp.operations.registry import default_registry
        from forgerwrite_mcp.rag import build_rag_enricher
        from forgerwrite_mcp.coordinator import SliceCoordinator

        config = load_config(tmp_path)
        enricher = build_rag_enricher(config)
        assert enricher is not None

        backend = FakeBackend()
        coord = SliceCoordinator(
            repo_root=tmp_path,
            config=config,
            registry=default_registry(),
            backend=backend,
            auto_approve=True,
            enricher=enricher,
        )

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust", "description": "Fix the gen keyword error in Rust code"}
        slice_contract = {
            "slice_id": "s1",
            "allowed_files": ["src/main.rs"],
        }

        # Run the pipeline — it will call generate_operation_batch on our fake
        outcome = coord.run(handoff, slice_contract)

        # The fake backend should have received an enriched prompt
        assert "RELEVANT KNOWLEDGE" in backend.last_user_prompt, (
            f"Expected RAG enrichment in prompt, got: {backend.last_user_prompt[:200]}..."
        )
        assert "TASK" in backend.last_user_prompt
        # Knowledge should come before task
        assert backend.last_user_prompt.index("RELEVANT KNOWLEDGE") < backend.last_user_prompt.index("TASK")

    def test_coordinator_retrieves_relevant_docs(self, tmp_path: Path):
        """The enriched prompt should contain relevant docs for the query."""
        _init_repo(tmp_path)
        _write_config(tmp_path, rag_enabled=True)
        _build_mini_index(tmp_path)

        from forgerwrite_mcp.config import load_config
        from forgerwrite_mcp.operations.registry import default_registry
        from forgerwrite_mcp.rag import build_rag_enricher
        from forgerwrite_mcp.coordinator import SliceCoordinator

        config = load_config(tmp_path)
        enricher = build_rag_enricher(config)
        assert enricher is not None

        backend = FakeBackend()
        coord = SliceCoordinator(
            repo_root=tmp_path,
            config=config,
            registry=default_registry(),
            backend=backend,
            auto_approve=True,
            enricher=enricher,
        )

        # Query about edition errors → should retrieve rust-edition doc
        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust", "description": "Fix the gen keyword error in Rust edition 2024 code"}
        slice_contract = {"slice_id": "s1", "allowed_files": ["src/main.rs"]}

        coord.run(handoff, slice_contract)

        # The enriched prompt should mention edition rules
        assert "edition" in backend.last_user_prompt.lower()
        assert "gen" in backend.last_user_prompt.lower()

    def test_coordinator_without_enricher_has_no_rag(self, tmp_path: Path):
        """Without enricher, the prompt should NOT contain RAG headers."""
        _init_repo(tmp_path)
        _write_config(tmp_path, rag_enabled=True)
        _build_mini_index(tmp_path)

        from forgerwrite_mcp.config import load_config
        from forgerwrite_mcp.operations.registry import default_registry
        from forgerwrite_mcp.coordinator import SliceCoordinator

        config = load_config(tmp_path)

        backend = FakeBackend()
        coord = SliceCoordinator(
            repo_root=tmp_path,
            config=config,
            registry=default_registry(),
            backend=backend,
            auto_approve=True,
            enricher=None,  # No enricher
        )

        handoff = {"schema_id": "forgerwrite.handoff.v1", "project": "test", "language": "rust", "description": "Fix the gen keyword error in Rust code"}
        slice_contract = {"slice_id": "s1", "allowed_files": ["src/main.rs"]}

        coord.run(handoff, slice_contract)

        assert "RELEVANT KNOWLEDGE" not in backend.last_user_prompt


class TestRagBuildIndexFunction:
    """Tests for build_rag_index() factory."""

    def test_build_rag_index_creates_file(self, tmp_path: Path):
        """build_rag_index creates an index file from a mini KB."""
        # Create a mini curated KB
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "rust-knowledge-base.md").write_text("""\
# Test KB

<!-- RAG-ID: test-doc-1 -->
### Document One
Content of document one.

<!-- RAG-ID: test-doc-2 -->
### Document Two
Content of document two.
""")

        idx_path = tmp_path / "index.tqi"

        from forgerwrite_mcp.rag import build_rag_index

        index = build_rag_index(
            kb_dir=str(kb_dir),
            index_path=str(idx_path),
        )

        assert idx_path.exists()
        assert index.dim == 768

    def test_build_rag_index_survives_empty_kb_dir(self, tmp_path: Path):
        """build_rag_index handles an empty KB directory gracefully."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        idx_path = tmp_path / "index.tqi"

        from forgerwrite_mcp.rag import build_rag_index

        index = build_rag_index(
            kb_dir=str(kb_dir),
            index_path=str(idx_path),
        )

        # Should not crash, but also may produce an empty index
        assert index is not None


class TestTurbovecHealthTool:
    """Tests for fw_turbovec_health MCP tool."""

    def test_health_reports_index_not_found_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When RAG index doesn't exist, health reports healthy=False."""
        import json
        from pathlib import Path as _Path

        # Point CWD to tmp_path so .forgerwrite/forgerwrite.toml doesn't interfere
        monkeypatch.chdir(tmp_path)

        # Create minimal config with rag enabled but index pointing nowhere
        config_dir = tmp_path / ".forgerwrite"
        config_dir.mkdir()
        config_file = config_dir / "forgerwrite.toml"
        config_file.write_text("""\
[project]
name = "test"
language = "rust"
repo_root = "."

[local_model]
endpoint = "http://127.0.0.1:8080/v1"
model = "test"

[validation]
commands = {}
profiles = {}

[permissions]

[hygiene]

[repair]

[rag]
enabled = true
index_path = "nonexistent.tqi"
""")

        # Import the tool function
        from forgerwrite_mcp.server import fw_turbovec_health

        # We need to run the async tool. Use asyncio.run.
        import asyncio

        result = asyncio.run(fw_turbovec_health())
        assert result["ok"] is True
        assert result["healthy"] is False
        assert "not found" in result["reason"].lower()

    def test_health_reports_healthy_when_index_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When RAG index exists, health reports healthy=True with doc count."""
        import asyncio
        from pathlib import Path as _Path

        # Build a small index in tmp_path using ProcessedDoc directly
        from forgerwrite_mcp.rag.preprocessor import ProcessedDoc
        from forgerwrite_mcp.rag.index import RagIndex

        docs = [
            ProcessedDoc(
                doc_id="test-doc",
                title="Test Doc",
                content="Some knowledge content.",
            ),
        ]

        index_path = tmp_path / "test_index.tqi"
        index = RagIndex(dim=768, bit_width=4)
        index.build(docs)
        index.save(str(index_path))

        # Create config pointing to this index
        config_dir = tmp_path / ".forgerwrite"
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / "forgerwrite.toml"
        config_file.write_text(f"""\
[project]
name = "test"
language = "rust"
repo_root = "."

[local_model]
endpoint = "http://127.0.0.1:8080/v1"
model = "test"

[validation]
commands = {{}}
profiles = {{}}

[permissions]

[hygiene]

[repair]

[rag]
enabled = true
index_path = "{index_path.relative_to(tmp_path)}"
""")

        monkeypatch.chdir(tmp_path)

        from forgerwrite_mcp.server import fw_turbovec_health

        result = asyncio.run(fw_turbovec_health())
        assert result["ok"] is True
        assert result["healthy"] is True
        assert result["file_size_bytes"] > 0


class TestTurbovecIndexTool:
    """Tests for fw_turbovec_index MCP tool."""

    def test_index_builds_and_returns_doc_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """fw_turbovec_index builds an index and reports document count."""
        import asyncio

        # Create a mini KB directory with a curated markdown file
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        kb_file = kb_dir / "rust-knowledge-base.md"
        kb_file.write_text("""\
# Test KB

<!-- RAG-ID: doc-1 -->
### Doc One
Content of first document.

<!-- RAG-ID: doc-2 -->
### Doc Two
Content of second document.
""")

        idx_path = tmp_path / "index.tqi"
        monkeypatch.chdir(tmp_path)

        from forgerwrite_mcp.server import fw_turbovec_index

        result = asyncio.run(fw_turbovec_index(
            kb_dir=str(kb_dir),
            index_path=str(idx_path),
        ))
        assert result["ok"] is True
        assert result["started"] is True
        # Background indexing may still be running; wait briefly then check
        import time
        time.sleep(0.5)
        assert idx_path.exists()
