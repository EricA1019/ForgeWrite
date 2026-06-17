"""Token usage tracker — records local model token consumption.

Appends JSONL records to ``.forgerwrite/token_usage.jsonl``. Provides
statistics and estimated cloud cost savings (DeepSeek Flash, DeepSeek Pro, Claude, GPT-4o).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

_TRACKER_FILE = "token_usage.jsonl"

# Cloud pricing per million tokens (USD, as of 2026-06)
_CLOUD_PRICES: dict[str, dict[str, float]] = {
    "deepseek-flash": {
        "input_per_m": 0.14,
        "output_per_m": 0.28,
        "label": "DeepSeek Flash",
    },
    "deepseek-pro": {
        "input_per_m": 0.27,
        "output_per_m": 1.10,
        "label": "DeepSeek Pro",
    },
    "claude": {
        "input_per_m": 3.00,
        "output_per_m": 15.00,
        "label": "Claude 3.5 Sonnet",
    },
    "gpt4o": {
        "input_per_m": 2.50,
        "output_per_m": 10.00,
        "label": "GPT-4o",
    },
}


# ── TokenTracker ─────────────────────────────────────────────────────────────


class TokenTracker:
    """Tracks local model token usage and estimates cloud savings.

    Records are appended to a JSONL file — one line per model call.
    Thread-safe for writes within the same process (single-writer pattern).
    """

    def __init__(self, tracker_dir: Path) -> None:
        self._dir = tracker_dir.resolve()
        self._path = self._dir / _TRACKER_FILE

    # ── Write ───────────────────────────────────────────────────────────────

    def record(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
        purpose: str,
    ) -> None:
        """Record a single model call's token usage."""
        self._dir.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "model_name": model_name,
            "purpose": purpose,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # ── Read / Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return aggregated token usage statistics.

        Returns:
            Dict with ``total_calls``, ``total_input_tokens``,
            ``total_output_tokens``, ``total_tokens``, ``by_purpose``,
            and ``estimated_savings``.
        """
        records = self._read_all()
        if not records:
            return {
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "by_purpose": {},
                "by_model": {},
                "estimated_savings": self._compute_savings(0, 0),
            }

        total_input = sum(r["prompt_tokens"] for r in records)
        total_output = sum(r["completion_tokens"] for r in records)

        # By purpose
        by_purpose: dict[str, dict[str, int]] = {}
        for r in records:
            p = r["purpose"]
            if p not in by_purpose:
                by_purpose[p] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }
            by_purpose[p]["calls"] += 1
            by_purpose[p]["input_tokens"] += r["prompt_tokens"]
            by_purpose[p]["output_tokens"] += r["completion_tokens"]
            by_purpose[p]["total_tokens"] += r["total_tokens"]

        # By model
        by_model: dict[str, dict[str, int]] = {}
        for r in records:
            m = r.get("model_name", "unknown")
            if m not in by_model:
                by_model[m] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }
            by_model[m]["calls"] += 1
            by_model[m]["input_tokens"] += r["prompt_tokens"]
            by_model[m]["output_tokens"] += r["completion_tokens"]
            by_model[m]["total_tokens"] += r["total_tokens"]

        return {
            "total_calls": len(records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "by_purpose": by_purpose,
            "by_model": by_model,
            "estimated_savings": self._compute_savings(total_input, total_output),
        }

    # ── Internal ────────────────────────────────────────────────────────────

    def _read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    @staticmethod
    def _compute_savings(input_tokens: int, output_tokens: int) -> dict[str, Any]:
        """Estimate cost savings for each cloud provider."""
        result: dict[str, Any] = {}
        for key, pricing in _CLOUD_PRICES.items():
            input_cost = (input_tokens / 1_000_000) * pricing["input_per_m"]
            output_cost = (output_tokens / 1_000_000) * pricing["output_per_m"]
            result[key] = {
                "label": pricing["label"],
                "input_cost": round(input_cost, 4),
                "output_cost": round(output_cost, 4),
                "total": round(input_cost + output_cost, 4),
            }
        return result
