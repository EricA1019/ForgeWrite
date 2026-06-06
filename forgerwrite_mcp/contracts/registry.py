"""Contract Registry — loads and validates JSON schemas.

Design reference: §5.3
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..errors import CONTRACT_VALIDATION_ERROR, PublicError


class ContractValidationError(PublicError):
    """A contract (handoff, slice, operation batch, etc.) failed schema validation."""

    def __init__(self, message: str) -> None:
        super().__init__(code=CONTRACT_VALIDATION_ERROR, message=message)


class ContractRegistry:
    """Load and validate JSON Schema contracts.

    Schemas are loaded from a directory and cached in memory.
    """

    def __init__(self, schema_dir: Path) -> None:
        self._schema_dir: Path = schema_dir.resolve()
        if not self._schema_dir.exists():
            raise FileNotFoundError(f"Schema directory not found: {self._schema_dir}")
        self._schemas: dict[str, dict[str, Any]] = {}

    def load_schema(self, name: str) -> dict[str, Any]:
        """Load a JSON Schema by filename from the schema directory.

        Results are cached — subsequent calls return the same dict.
        """
        if name in self._schemas:
            return self._schemas[name]
        path = self._schema_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContractValidationError(f"Invalid schema {path}: {exc}") from exc
        self._schemas[name] = schema
        return schema

    def validate(self, schema_name: str, instance: dict[str, Any]) -> None:
        """Validate an instance against a named JSON Schema.

        Args:
            schema_name: Schema filename (e.g. 'handoff.v1.json').
            instance: The JSON data to validate.

        Raises:
            ContractValidationError: If validation fails, with readable error paths.
        """
        schema = self.load_schema(schema_name)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        if errors:
            lines = [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
            raise ContractValidationError("\n".join(lines))
