#!/usr/bin/env bash
# Launch the ForgeWrite TUI dashboard.
#
# Usage: bash scripts/tui.sh
# Requires: python 3.12+, uv sync --group dev

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -d .venv ]; then
    echo "No .venv found. Run: uv sync --group dev"
    exit 1
fi

exec .venv/bin/forgerwrite tui
