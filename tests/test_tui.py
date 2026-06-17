"""Tests for the ForgeWrite TUI dashboard rendering."""

from __future__ import annotations

import pytest


class TestRenderTokens:
    """Tests for ForgerwriteTUI._render_tokens (static method)."""

    _FIXTURE = {
        "total_calls": 134,
        "total_input_tokens": 52819,
        "total_output_tokens": 26274,
        "total_tokens": 79093,
        "by_purpose": {
            "scout": {"calls": 1, "input_tokens": 500, "output_tokens": 0, "total_tokens": 500},
            "validate_operations": {"calls": 1, "input_tokens": 300, "output_tokens": 0, "total_tokens": 300},
            "generate_operations": {"calls": 1, "input_tokens": 169, "output_tokens": 349, "total_tokens": 518},
            "stress-test": {"calls": 131, "input_tokens": 51850, "output_tokens": 25925, "total_tokens": 77775},
        },
        "by_model": {
            "forgewrite-pipeline": {"calls": 2, "input_tokens": 800, "output_tokens": 0, "total_tokens": 800},
            "omnicoder-9b": {"calls": 1, "input_tokens": 169, "output_tokens": 349, "total_tokens": 518},
            "stress-model-0": {"calls": 46, "input_tokens": 17640, "output_tokens": 8820, "total_tokens": 26460},
            "stress-model-1": {"calls": 43, "input_tokens": 16990, "output_tokens": 8495, "total_tokens": 25485},
            "stress-model-2": {"calls": 42, "input_tokens": 17220, "output_tokens": 8610, "total_tokens": 25830},
        },
        "estimated_savings": {
            "deepseek-flash": {"label": "DeepSeek Flash", "input_cost": 0.0074, "output_cost": 0.0074, "total": 0.0148},
            "deepseek-pro": {"label": "DeepSeek Pro", "input_cost": 0.0143, "output_cost": 0.0289, "total": 0.0432},
            "claude": {"label": "Claude 3.5 Sonnet", "input_cost": 0.1585, "output_cost": 0.3941, "total": 0.5526},
            "gpt4o": {"label": "GPT-4o", "input_cost": 0.132, "output_cost": 0.2627, "total": 0.3948},
        },
    }

    _EMPTY_FIXTURE = {
        "total_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "by_purpose": {},
        "by_model": {},
        "estimated_savings": {
            "deepseek-flash": {"label": "DeepSeek Flash", "input_cost": 0.0, "output_cost": 0.0, "total": 0.0},
            "deepseek-pro": {"label": "DeepSeek Pro", "input_cost": 0.0, "output_cost": 0.0, "total": 0.0},
            "claude": {"label": "Claude 3.5 Sonnet", "input_cost": 0.0, "output_cost": 0.0, "total": 0.0},
            "gpt4o": {"label": "GPT-4o", "input_cost": 0.0, "output_cost": 0.0, "total": 0.0},
        },
    }

    def test_render_empty_stats(self) -> None:
        """Empty stats show the no-data message."""
        from forgerwrite_mcp.tui import ForgerwriteTUI

        result = ForgerwriteTUI._render_tokens(self._EMPTY_FIXTURE)
        assert "No token data yet" in result
        assert "Run fw_generate_operations_local" in result

    def test_render_with_data_contains_headline(self) -> None:
        """Stats with data show calls, in/out split, and total."""
        from forgerwrite_mcp.tui import ForgerwriteTUI

        result = ForgerwriteTUI._render_tokens(self._FIXTURE)
        assert "134 calls" in result
        assert "52,819" in result  # input tokens formatted
        assert "26,274" in result  # output tokens formatted
        assert "67%" in result     # input percentage
        assert "79,093" in result  # total tokens

    def test_render_with_data_contains_by_usage(self) -> None:
        """Stats include per-purpose breakdown with percentages."""
        from forgerwrite_mcp.tui import ForgerwriteTUI

        result = ForgerwriteTUI._render_tokens(self._FIXTURE)
        assert "By usage" in result
        assert "stress-test" in result
        assert "98%" in result  # stress-test is ~98% of all tokens

    def test_render_with_data_contains_by_model(self) -> None:
        """Stats include per-model breakdown."""
        from forgerwrite_mcp.tui import ForgerwriteTUI

        result = ForgerwriteTUI._render_tokens(self._FIXTURE)
        assert "Local model" in result
        assert "omnicoder-9b" in result
        assert "stress-model-0" in result

    def test_render_with_data_contains_savings(self) -> None:
        """Stats include cloud cost savings."""
        from forgerwrite_mcp.tui import ForgerwriteTUI

        result = ForgerwriteTUI._render_tokens(self._FIXTURE)
        assert "DeepSeek Flash" in result
        assert "0.0148" in result
        assert "DeepSeek Pro" in result
        assert "Claude 3.5 Sonnet" in result
        assert "0.5526" in result
        assert "GPT-4o" in result

    def test_render_with_missing_total_tokens_returns_empty(self) -> None:
        """Missing total_tokens key doesn't crash — returns no-data message."""
        from forgerwrite_mcp.tui import ForgerwriteTUI

        bad = dict(self._EMPTY_FIXTURE)
        bad.pop("total_tokens", None)
        result = ForgerwriteTUI._render_tokens(bad)
        # Should handle gracefully without KeyError
        assert isinstance(result, str)
