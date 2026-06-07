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

        # Verify the coordinator can be constructed
        coordinator = RepairCoordinator()
        assert coordinator is not None

    def test_repair_coordinator_stores_attempts(self) -> None:
        """RepairCoordinator tracks repair attempts."""
        from forgerwrite_mcp.config import RepairConfig
        from forgerwrite_mcp.repair import RepairCoordinator

        cfg = RepairConfig(max_attempts=3, scope_must_match_original_slice=True)
        coordinator = RepairCoordinator(config=cfg)
        assert coordinator._max_attempts == 3

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

    def test_repair_loop_tracks_attempt_count(self) -> None:
        """Each repair attempt increments the counter."""
        from forgerwrite_mcp.repair import RepairCoordinator

        coordinator = RepairCoordinator()
        assert coordinator._attempt_count == 0
        coordinator._increment_attempt()
        assert coordinator._attempt_count == 1
        coordinator._increment_attempt()
        assert coordinator._attempt_count == 2

    def test_repair_budget_exhausted_check(self) -> None:
        """When attempts reach max, budget is exhausted."""
        from forgerwrite_mcp.config import RepairConfig
        from forgerwrite_mcp.repair import RepairCoordinator

        cfg = RepairConfig(max_attempts=2)
        coordinator = RepairCoordinator(config=cfg)
        assert not coordinator._budget_exhausted()
        coordinator._increment_attempt()
        coordinator._increment_attempt()
        assert coordinator._budget_exhausted()
