"""Tests for the pluggable semantic validator."""

import pytest


class TestSemanticValidator:
    """Tests for SemanticValidator with built-in rules."""

    def _make_validator(self):
        from forgerwrite_mcp.validation.semantic import (
            default_validator,
        )

        return default_validator()

    def test_rejects_operation_targeting_forbidden_file(self) -> None:
        """Operation targeting a forbidden file is rejected."""
        from forgerwrite_mcp.validation.semantic import SemanticValidationError

        v = self._make_validator()
        batch = {
            "operations": [{"op": "create_file", "path": "Cargo.lock", "content": "x"}],
        }
        slice_contract = {
            "allowed_files": ["Cargo.lock"],
            "forbidden_files": ["Cargo.lock"],
        }
        with pytest.raises(SemanticValidationError, match="forbidden"):
            v.validate(batch, slice_contract)

    def test_rejects_operation_targeting_generated_path(self) -> None:
        """Operation targeting a generated path is rejected."""
        from forgerwrite_mcp.validation.semantic import (
            SemanticValidationError,
            SemanticValidator,
        )

        v = SemanticValidator()
        from forgerwrite_mcp.validation.semantic import GeneratedPathRule

        v.register(GeneratedPathRule(globs=["target/**"]))
        batch = {
            "operations": [{"op": "create_file", "path": "target/debug/output", "content": "x"}],
        }
        slice_contract = {"allowed_files": ["target/debug/output"]}
        with pytest.raises(SemanticValidationError, match="generated"):
            v.validate(batch, slice_contract)

    def test_rejects_batch_exceeding_max_operations(self) -> None:
        """Batch with more operations than allowed is rejected."""
        from forgerwrite_mcp.validation.semantic import (
            SemanticValidationError,
            SemanticValidator,
            SizeRule,
        )

        v = SemanticValidator()
        v.register(SizeRule(max_operations=2))
        batch = {
            "operations": [
                {"op": "create_file", "path": "a.rs", "content": "a"},
                {"op": "create_file", "path": "b.rs", "content": "b"},
                {"op": "create_file", "path": "c.rs", "content": "c"},
            ],
        }
        slice_contract = {"allowed_files": ["a.rs", "b.rs", "c.rs"]}
        with pytest.raises(SemanticValidationError, match="exceeds max"):
            v.validate(batch, slice_contract)

    def test_rejects_create_file_outside_allowed_files(self) -> None:
        """Operation targeting a file not in allowed_files is rejected."""
        from forgerwrite_mcp.validation.semantic import SemanticValidationError

        v = self._make_validator()
        batch = {
            "operations": [{"op": "create_file", "path": "secret.rs", "content": "x"}],
        }
        slice_contract = {"allowed_files": ["main.rs"]}
        with pytest.raises(SemanticValidationError, match="outside allowed"):
            v.validate(batch, slice_contract)

    def test_permission_rule_reads_config_for_replace_file(self) -> None:
        """PermissionRule reads require_approval_for_full_file_replace from config."""
        from forgerwrite_mcp.config import PermissionsConfig
        from forgerwrite_mcp.validation.semantic import SemanticValidator

        v = SemanticValidator()
        from forgerwrite_mcp.validation.semantic import PermissionRule

        v.register(PermissionRule())
        batch = {
            "operations": [{"op": "replace_file", "path": "main.rs", "content": "new"}],
        }
        slice_contract = {"allowed_files": ["main.rs"]}
        # With approval disabled in config, no error should be raised
        perms = PermissionsConfig(require_approval_for_full_file_replace=False)
        v.validate(batch, slice_contract, permissions=perms)

    def test_permission_rule_reads_config_for_delete_file(self) -> None:
        """PermissionRule reads require_approval_for_delete from config."""
        from forgerwrite_mcp.config import PermissionsConfig
        from forgerwrite_mcp.validation.semantic import SemanticValidator

        v = SemanticValidator()
        from forgerwrite_mcp.validation.semantic import PermissionRule

        v.register(PermissionRule())
        batch = {
            "operations": [{"op": "delete_file", "path": "main.rs"}],
        }
        slice_contract = {"allowed_files": ["main.rs"]}
        # With delete approval disabled in config, no error should be raised
        perms = PermissionsConfig(require_approval_for_delete=False)
        v.validate(batch, slice_contract, permissions=perms)

    def test_permission_rule_still_blocks_when_config_enforces(self) -> None:
        """PermissionRule still blocks when config requires approval."""
        from forgerwrite_mcp.config import PermissionsConfig
        from forgerwrite_mcp.validation.semantic import (
            SemanticValidationError,
            SemanticValidator,
        )

        v = SemanticValidator()
        from forgerwrite_mcp.validation.semantic import PermissionRule

        v.register(PermissionRule())
        batch = {
            "operations": [{"op": "replace_file", "path": "main.rs", "content": "new"}],
        }
        slice_contract = {"allowed_files": ["main.rs"]}
        # Default config has require_approval_for_full_file_replace=True
        with pytest.raises(SemanticValidationError, match="requires approval"):
            v.validate(batch, slice_contract)

    def test_allows_valid_batch_within_scope(self) -> None:
        """Valid batch within scope passes validation."""
        v = self._make_validator()
        batch = {
            "operations": [
                {"op": "create_file", "path": "src/lib.rs", "content": "// lib"},
                {
                    "op": "replace_line_range",
                    "path": "src/main.rs",
                    "start_line": 1,
                    "end_line": 1,
                    "content": "// fixed",
                },
            ],
        }
        slice_contract = {"allowed_files": ["src/lib.rs", "src/main.rs"]}
        # Should not raise
        v.validate(batch, slice_contract)

    def test_rejects_delete_file_without_permission(self) -> None:
        """Delete operation rejected when require_approval_for_delete is set."""
        from forgerwrite_mcp.validation.semantic import (
            PermissionRule,
            SemanticValidationError,
            SemanticValidator,
        )

        v = SemanticValidator()
        v.register(PermissionRule(require_approval_for_delete=True))
        batch = {
            "operations": [{"op": "delete_file", "path": "src/old.rs"}],
        }
        slice_contract = {"allowed_files": ["src/old.rs"]}
        with pytest.raises(SemanticValidationError, match="requires approval"):
            v.validate(batch, slice_contract)

    def test_custom_rule_can_be_registered(self) -> None:
        """A custom SemanticRule can be registered and is called during validation."""
        from forgerwrite_mcp.validation.semantic import (
            SemanticValidationError,
            SemanticValidator,
        )

        class CustomRule:
            def check(self, batch, slice_contract, limits, permissions) -> list[str]:
                return ["Custom rule always fails"]

        v = SemanticValidator()
        v.register(CustomRule())
        batch = {"operations": []}
        slice_contract = {"allowed_files": []}
        with pytest.raises(SemanticValidationError, match="Custom rule"):
            v.validate(batch, slice_contract)
