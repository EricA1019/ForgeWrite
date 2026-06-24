"""Tests for model_state module — save-on-change behavior."""

import os
import time
from pathlib import Path

from forgerwrite_mcp.model_state import load_last_model, save_model_state


class TestSaveModelState:
    def test_skip_write_when_state_unchanged(self, tmp_path: Path) -> None:
        """Calling save_model_state with unchanged values should not
        rewrite the file."""
        save_model_state(tmp_path, "test-model", "http://localhost:8080/v1", True)
        state_path = tmp_path / ".forgerwrite" / "model_state.json"
        assert state_path.exists()
        mtime_after_first = os.path.getmtime(state_path)
        time.sleep(0.01)
        save_model_state(tmp_path, "test-model", "http://localhost:8080/v1", True)
        mtime_after_second = os.path.getmtime(state_path)
        assert mtime_after_second == mtime_after_first, (
            "file was rewritten despite unchanged state"
        )

    def test_writes_when_state_changed(self, tmp_path: Path) -> None:
        """Calling save_model_state with changed healthy should rewrite."""
        save_model_state(tmp_path, "test-model", "http://localhost:8080/v1", True)
        state_path = tmp_path / ".forgerwrite" / "model_state.json"
        mtime_after_first = os.path.getmtime(state_path)
        time.sleep(0.01)
        save_model_state(tmp_path, "test-model", "http://localhost:8080/v1", False)
        mtime_after_second = os.path.getmtime(state_path)
        assert mtime_after_second != mtime_after_first, (
            "file was not rewritten despite changed state"
        )

    def test_load_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        """load_last_model returns empty dict when no state file exists."""
        result = load_last_model(tmp_path)
        assert result == {}

    def test_load_returns_saved_state(self, tmp_path: Path) -> None:
        """load_last_model returns previously saved state."""
        save_model_state(tmp_path, "my-model", "http://example.com:8080/v1", True)
        result = load_last_model(tmp_path)
        assert result["model_name"] == "my-model"
        assert result["healthy"] is True
