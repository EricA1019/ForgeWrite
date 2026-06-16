# Contributing to ForgeWrite

## Setup

### Prerequisites
- Python 3.12+
- Rust 1.85+ (for slang tests)
- CUDA-capable GPU with 8GB+ VRAM (for local model)

### Get Started

```bash
# Clone the repository
git clone https://github.com/EricA1019/ForgeWrite
cd ForgeWrite

# Create virtual environment and install dependencies
uv sync --group dev

# Activate the environment
source .venv/bin/activate
```

### Start the Model Server (optional, needed for generation)

```bash
# Launch Gemma 4 12B via llama.cpp
bash scripts/launch-gemma4.sh
```

## Development Workflow

### Run Tests

```bash
uv run pytest tests/ -q          # All 354 tests
uv run pytest tests/test_coordinator.py -v  # Specific file
uv run pytest -k "test_name" -v  # Specific test
```

### Lint and Type Check

```bash
uv run ruff check forgerwrite_mcp/ tests/
uv run ruff format --check .
uv run mypy forgerwrite_mcp/
```

### All Gates

```bash
uv run ruff check forgerwrite_mcp/ tests/ && uv run mypy forgerwrite_mcp/ && uv run pytest tests/ -q
```

## Code Style

- Follow existing patterns. Each MCP tool wraps its body in `try/except` returning `envelope_from(exc, "tool_name").to_dict()`.
- All file paths go through `forgerwrite_mcp.paths.safe_resolve_path()` — never use `Path(...)` directly for file access.
- Config is loaded via `load_config(Path.cwd())`, returns `ForgerWriteConfig` Pydantic model.
- Artifacts are written via `write_artifact(run_dir, "name.json", data)` from `forgerwrite_mcp.artifacts`.
- Tests use `tmp_path` fixture, `FakeLocalModelBackend`, and `_init_repo()` helper from existing tests.
- Async code uses `asyncio.run()` only at the sync entrypoint. Use `await` inside async functions.

## PR Process

1. Create a feature branch from `main`.
2. Make changes following the code style above.
3. Ensure all tests pass: `uv run pytest tests/ -q`
4. Ensure lint clean: `uv run ruff check forgerwrite_mcp/ tests/`
5. Ensure type check clean: `uv run mypy forgerwrite_mcp/`
6. Push and open a pull request against `main`.
7. The PR title should follow conventional commit format: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`.

## Dogfooding

ForgeWrite should be used to edit itself. When contributing:

1. Work on a clean git worktree.
2. Use ForgeWrite MCP tools for file operations (not direct edits).
3. Preview before applying.
4. Run validation after applying.
5. Promote successful runs to the knowledge base.

## Project Structure

```
forgerwrite_mcp/           # Main Python package
├── server.py              # FastMCP stdio server — 22 MCP tools
├── coordinator.py         # SliceCoordinator — state machine
├── cli.py                 # Typer CLI — 12 commands
├── config.py              # Config loading (Pydantic)
├── paths.py               # Path safety (safe_resolve_path)
├── errors.py              # Public error envelope
├── llm_client.py          # HTTP client for llama.cpp
├── operations/            # 6 file operation handlers
├── validation/            # CI validation runner + semantic rules
├── scout/                 # Evidence discovery pipeline
├── knowledge/             # Saved Work KB
├── rag/                   # TurboVec RAG index
├── languages/             # Language adapters (Rust, Python)
├── contracts/             # JSON Schema loading + validation
├── forge/                 # Git snapshot + diff utilities
tests/                     # 354 pytest tests
docs/                      # Documentation suite
schemas/                   # 9 JSON Schema contract files
scripts/                   # Launch scripts
```

## Documentation

All documentation lives in `docs/`. See [docs/README.md](docs/README.md) for the full index.

## License

MIT — see [LICENSE](LICENSE).
