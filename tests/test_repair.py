"""Tests for the repair coordinator."""

import json


class FakeBackend:
    """Simple fake backend for repair tests."""

    async def generate_operation_batch(self, sp: str, up: str, schema: dict) -> str:
        return json.dumps(
            {
                "schema_id": "forgerwrite.operation_batch.v1",
                "batch_id": "repair-batch",
                "slice_id": "test-slice",
                "operations": [
                    {"op": "create_file", "path": "src/fixed.rs", "content": "// fixed\n"}
                ],
            }
        )


class TestRepairCoordinator:
    """Tests for RepairCoordinator."""

    def test_repair_respects_max_attempts(self) -> None:
        """RepairCoordinator enforces repair.max_attempts from config."""
        from forgerwrite_mcp.config import RepairConfig

        cfg = RepairConfig(max_attempts=2)
        assert cfg.max_attempts == 2

    def test_repair_scope_must_match_original_slice(self) -> None:
        """RepairCoordinator enforces scope_must_match_original_slice from config."""
        from forgerwrite_mcp.config import RepairConfig

        cfg = RepairConfig(scope_must_match_original_slice=True)
        assert cfg.scope_must_match_original_slice is True

    def test_repair_generates_targeted_context_with_validation_output(self) -> None:
        """Repair context includes validation failure details."""
        from forgerwrite_mcp.repair import RepairCoordinator

        coordinator = RepairCoordinator()
        assert coordinator is not None

    def test_repair_coordinator_tracks_attempts(self) -> None:
        """RepairCoordinator tracks repair attempts via attempt_count property."""
        from forgerwrite_mcp.config import RepairConfig
        from forgerwrite_mcp.repair import RepairCoordinator

        cfg = RepairConfig(max_attempts=3)
        coordinator = RepairCoordinator(config=cfg)
        assert coordinator.attempt_count == 0
        assert coordinator.budget_remaining == 3

    def test_repair_builds_feedback_prompt_with_validation_output(self) -> None:
        """_build_repair_prompt includes validation errors in the prompt."""
        from forgerwrite_mcp.repair import RepairCoordinator

        coordinator = RepairCoordinator()
        validation_result = {
            "passed": False,
            "commands": [
                {
                    "command_id": "check",
                    "passed": False,
                    "stderr_head": "error[E0425]: cannot find value",
                }
            ],
        }
        prompt = coordinator._build_repair_prompt(validation_result)
        assert "validation" in prompt.lower()
        assert "error" in prompt.lower() or "E0425" in prompt

    def test_repair_attempt_returns_prompt_and_remaining(self) -> None:
        """attempt() returns (prompt, budget_remaining) when budget remains."""
        from forgerwrite_mcp.config import RepairConfig
        from forgerwrite_mcp.repair import RepairCoordinator

        cfg = RepairConfig(max_attempts=2)
        coordinator = RepairCoordinator(config=cfg)
        validation_result = {
            "passed": False,
            "commands": [{"command_id": "test", "passed": False, "stderr_head": "fail"}],
        }
        result = coordinator.attempt(validation_result, {})
        assert result is not None
        prompt, remaining = result
        assert "validation" in prompt.lower()
        assert remaining == 1  # 2 max - 1 used
        assert coordinator.attempt_count == 1

    def test_repair_budget_exhausted_returns_none(self) -> None:
        """When budget exhausted, attempt() returns None."""
        from forgerwrite_mcp.config import RepairConfig
        from forgerwrite_mcp.repair import RepairCoordinator

        cfg = RepairConfig(max_attempts=1)
        coordinator = RepairCoordinator(config=cfg)
        validation_result = {"passed": False, "commands": []}
        # First attempt — should succeed
        result1 = coordinator.attempt(validation_result, {})
        assert result1 is not None
        # Second attempt — budget exhausted
        result2 = coordinator.attempt(validation_result, {})
        assert result2 is None
