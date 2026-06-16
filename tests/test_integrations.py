"""Tests for integration adapters — fail-soft MEX, Graphify, Headroom."""

from __future__ import annotations

from pathlib import Path

import pytest


# ── Constants ────────────────────────────────────────────────────────────────

_REPO_WITH_MEX = Path(__file__).parent.parent  # This repo has .mex/


# ── MEX adapter tests ────────────────────────────────────────────────────────


class TestMexAdapter:
    """MEX adapter detects and reports .mex/ project memory."""

    def test_mex_available_in_this_repo(self) -> None:
        """This repo has .mex/ — adapter should report available."""
        from forgerwrite_mcp.integrations.mex_adapter import MexAdapter

        adapter = MexAdapter()
        assert adapter.check_available(_REPO_WITH_MEX) is True

    def test_mex_unavailable_in_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory has no .mex/ — adapter reports unavailable."""
        from forgerwrite_mcp.integrations.mex_adapter import MexAdapter

        adapter = MexAdapter()
        assert adapter.check_available(tmp_path) is False

    def test_mex_get_info_returns_dict(self) -> None:
        """get_info always returns a dict, never raises."""
        from forgerwrite_mcp.integrations.mex_adapter import MexAdapter

        adapter = MexAdapter()
        info = adapter.get_info(_REPO_WITH_MEX)
        assert isinstance(info, dict)
        assert "available" in info

    def test_mex_get_info_unavailable_has_reason(self, tmp_path: Path) -> None:
        """When unavailable, get_info includes a reason."""
        from forgerwrite_mcp.integrations.mex_adapter import MexAdapter

        adapter = MexAdapter()
        info = adapter.get_info(tmp_path)
        assert info["available"] is False
        assert "reason" in info

    def test_mex_never_raises(self, tmp_path: Path) -> None:
        """Adapter never raises, even with None or invalid input."""
        from forgerwrite_mcp.integrations.mex_adapter import MexAdapter

        adapter = MexAdapter()
        # Should not raise
        adapter.get_info(tmp_path / "nonexistent")


# ── Graphify adapter tests ───────────────────────────────────────────────────


class TestGraphifyAdapter:
    """Graphify adapter detects graphify binary."""

    def test_get_info_returns_dict(self) -> None:
        """get_info always returns a dict."""
        from forgerwrite_mcp.integrations.graphify_adapter import GraphifyAdapter

        adapter = GraphifyAdapter()
        info = adapter.get_info()
        assert isinstance(info, dict)
        assert "available" in info

    def test_check_available_returns_bool(self) -> None:
        """check_available returns a boolean."""
        from forgerwrite_mcp.integrations.graphify_adapter import GraphifyAdapter

        adapter = GraphifyAdapter()
        result = adapter.check_available()
        assert isinstance(result, bool)

    def test_graphify_unavailable_has_reason(self) -> None:
        """When graphify is not installed, reason is included."""
        from forgerwrite_mcp.integrations.graphify_adapter import GraphifyAdapter

        adapter = GraphifyAdapter()
        info = adapter.get_info()
        if not info["available"]:
            assert "reason" in info

    def test_never_raises(self) -> None:
        """Adapter never raises."""
        from forgerwrite_mcp.integrations.graphify_adapter import GraphifyAdapter

        adapter = GraphifyAdapter()
        adapter.check_available()
        adapter.get_info()


# ── Headroom adapter tests ───────────────────────────────────────────────────


class TestHeadroomAdapter:
    """Headroom adapter — optional orchestrator, likely unavailable."""

    def test_get_info_returns_dict(self) -> None:
        """get_info always returns a dict."""
        from forgerwrite_mcp.integrations.headroom_adapter import HeadroomAdapter

        adapter = HeadroomAdapter()
        info = adapter.get_info()
        assert isinstance(info, dict)
        assert "available" in info

    def test_check_available_returns_bool(self) -> None:
        """check_available returns a boolean."""
        from forgerwrite_mcp.integrations.headroom_adapter import HeadroomAdapter

        adapter = HeadroomAdapter()
        result = adapter.check_available()
        assert isinstance(result, bool)

    def test_headroom_unavailable_has_reason(self) -> None:
        """When headroom is not installed, reason is included."""
        from forgerwrite_mcp.integrations.headroom_adapter import HeadroomAdapter

        adapter = HeadroomAdapter()
        info = adapter.get_info()
        if not info["available"]:
            assert "reason" in info

    def test_never_raises(self) -> None:
        """Adapter never raises."""
        from forgerwrite_mcp.integrations.headroom_adapter import HeadroomAdapter

        adapter = HeadroomAdapter()
        adapter.check_available()
        adapter.get_info()


# ── Integration registry tests ───────────────────────────────────────────────


class TestIntegrationRegistry:
    """Fail-soft registry that loads all adapters."""

    def test_registry_lists_all_adapters(self) -> None:
        """Registry returns all three adapter names."""
        from forgerwrite_mcp.integrations import list_integrations

        names = list_integrations()
        assert "mex" in names
        assert "graphify" in names
        assert "headroom" in names
        assert len(names) == 3

    def test_registry_get_info_all(self) -> None:
        """get_all_info returns info for every adapter without raising."""
        from forgerwrite_mcp.integrations import get_all_info

        info = get_all_info(Path.cwd())
        assert isinstance(info, dict)
        assert "mex" in info
        assert "graphify" in info
        assert "headroom" in info
        # All must have "available" key
        for adapter_info in info.values():
            assert "available" in adapter_info

    def test_registry_get_info_works_without_repo(self, tmp_path: Path) -> None:
        """get_all_info works even in empty directories."""
        from forgerwrite_mcp.integrations import get_all_info

        info = get_all_info(tmp_path)
        assert isinstance(info, dict)
        assert len(info) == 3
