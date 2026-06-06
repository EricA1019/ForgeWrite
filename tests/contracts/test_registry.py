"""Tests for the Contract Registry."""

import json
from pathlib import Path

import pytest


class TestContractRegistry:
    """Tests for ContractRegistry class."""

    @pytest.fixture
    def registry(self) -> object:
        """Create a ContractRegistry pointing at the real schemas dir."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        schema_dir = Path(__file__).parent.parent.parent / "schemas"
        return ContractRegistry(schema_dir)

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        return Path(__file__).parent / "fixtures"

    # -- load_schema tests --

    def test_load_schema_returns_dict(self, registry: object) -> None:
        """load_schema returns a dict for a valid schema name."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        reg: ContractRegistry = registry  # type: ignore[assignment]
        schema = reg.load_schema("handoff.v1.json")
        assert isinstance(schema, dict)
        assert "$id" in schema

    def test_load_schema_raises_on_missing_file(self, registry: object) -> None:
        """load_schema raises FileNotFoundError for unknown schema."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        reg: ContractRegistry = registry  # type: ignore[assignment]
        with pytest.raises(FileNotFoundError):
            reg.load_schema("nonexistent.v1.json")

    def test_load_schema_raises_on_invalid_json(self, tmp_path: Path) -> None:
        """load_schema raises ContractValidationError for malformed JSON."""
        from forgerwrite_mcp.contracts.registry import (
            ContractRegistry,
            ContractValidationError,
        )

        bad_dir = tmp_path / "bad_schemas"
        bad_dir.mkdir()
        (bad_dir / "bad.json").write_text("not json {{{", encoding="utf-8")
        reg = ContractRegistry(bad_dir)
        with pytest.raises(ContractValidationError, match="Invalid schema"):
            reg.load_schema("bad.json")

    # -- validate tests: valid fixtures (parametrized) --

    @pytest.mark.parametrize(
        "schema_name, fixture_name",
        [
            ("handoff.v1.json", "valid_handoff.json"),
            ("slice.v1.json", "valid_slice.json"),
            ("operation_batch.v1.json", "valid_operation_batch.json"),
            ("approval_record.v1.json", "valid_approval_record.json"),
            ("validation_result.v1.json", "valid_validation_result.json"),
            ("run.v1.json", "valid_run.json"),
        ],
    )
    def test_validate_passes_on_valid_fixture(
        self, registry: object, fixtures_dir: Path, schema_name: str, fixture_name: str
    ) -> None:
        """Each valid fixture passes validation against its schema."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        reg: ContractRegistry = registry  # type: ignore[assignment]
        instance = json.loads((fixtures_dir / fixture_name).read_text(encoding="utf-8"))
        # Should not raise
        reg.validate(schema_name, instance)

    # -- validate tests: invalid fixtures (parametrized) --

    @pytest.mark.parametrize(
        "schema_name, fixture_name",
        [
            ("handoff.v1.json", "invalid_handoff_missing_project.json"),
            ("handoff.v1.json", "invalid_handoff_missing_schema_id.json"),
            ("handoff.v1.json", "invalid_handoff_empty_project.json"),
            ("slice.v1.json", "invalid_slice_missing_slice_id.json"),
            ("slice.v1.json", "invalid_slice_empty_allowed_files.json"),
            ("slice.v1.json", "invalid_slice_bad_operation_type.json"),
            ("operation_batch.v1.json", "invalid_opbatch_empty_ops.json"),
            ("operation_batch.v1.json", "invalid_opbatch_unknown_op.json"),
            ("operation_batch.v1.json", "invalid_opbatch_missing_content.json"),
            ("approval_record.v1.json", "invalid_approval_missing_sha256.json"),
            ("approval_record.v1.json", "invalid_approval_bad_sha256.json"),
            ("approval_record.v1.json", "invalid_approval_bad_approved_type.json"),
            ("validation_result.v1.json", "invalid_vresult_missing_passed.json"),
            ("validation_result.v1.json", "invalid_vresult_bad_returncode.json"),
            ("validation_result.v1.json", "invalid_vresult_missing_command_id.json"),
            ("run.v1.json", "invalid_run_missing_status.json"),
            ("run.v1.json", "invalid_run_bad_status.json"),
            ("run.v1.json", "invalid_run_missing_run_id.json"),
        ],
    )
    def test_validate_raises_on_invalid_fixture(
        self, registry: object, fixtures_dir: Path, schema_name: str, fixture_name: str
    ) -> None:
        """Each invalid fixture fails validation."""
        from forgerwrite_mcp.contracts.registry import (
            ContractRegistry,
            ContractValidationError,
        )

        reg: ContractRegistry = registry  # type: ignore[assignment]
        instance = json.loads((fixtures_dir / fixture_name).read_text(encoding="utf-8"))
        with pytest.raises(ContractValidationError):
            reg.validate(schema_name, instance)

    def test_validate_raises_with_readable_error_paths(
        self, registry: object, fixtures_dir: Path
    ) -> None:
        """Validation error messages include the failing field path."""
        from forgerwrite_mcp.contracts.registry import (
            ContractRegistry,
            ContractValidationError,
        )

        reg: ContractRegistry = registry  # type: ignore[assignment]
        instance = json.loads(
            (fixtures_dir / "invalid_handoff_missing_project.json").read_text(encoding="utf-8")
        )
        with pytest.raises(ContractValidationError) as exc_info:
            reg.validate("handoff.v1.json", instance)
        msg = str(exc_info.value)
        # Error message should reference the missing field
        assert "project" in msg.lower() or "required" in msg.lower()
