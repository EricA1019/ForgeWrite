"""Tests for the Operation Registry (Protocol + Registry class)."""

import pytest


class TestOperationRegistry:
    """Tests for OperationRegistry and default_registry()."""

    def test_default_registry_has_all_6_handlers(self) -> None:
        """default_registry() returns a registry with all 6 MVP handlers."""
        from forgerwrite_mcp.operations.registry import default_registry

        reg = default_registry()
        handler_names = {
            "create_file",
            "replace_file",
            "replace_line_range",
            "insert_after_line",
            "insert_before_line",
            "delete_file",
        }
        for name in handler_names:
            handler = reg.dispatch({"op": name, "path": "test.rs"})
            assert handler.op_name == name

    def test_dispatch_raises_on_unknown_op(self) -> None:
        """dispatch() raises OperationApplyError for unknown operation names."""
        from forgerwrite_mcp.operations.registry import (
            OperationApplyError,
            OperationRegistry,
        )

        reg = OperationRegistry()
        with pytest.raises(OperationApplyError, match="Unknown operation"):
            reg.dispatch({"op": "nonexistent_op", "path": "x.rs"})

    def test_register_adds_new_handler(self) -> None:
        """register() adds a handler that dispatch() can then find."""
        from dataclasses import dataclass

        from forgerwrite_mcp.operations.registry import (
            OperationRegistry,
        )

        @dataclass
        class FakeHandler:
            op_name: str = "fake_op"

            def validate(self, op: dict, slice_contract: dict, limits: object) -> None:
                pass

            def apply(self, repo_root: object, op: dict) -> object:
                return None

        reg = OperationRegistry()
        reg.register(FakeHandler())
        handler = reg.dispatch({"op": "fake_op", "path": "test.rs"})
        assert handler.op_name == "fake_op"
