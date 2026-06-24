"""Configuration module for ForgerWrite MCP.

Loads .forgerwrite/forgerwrite.toml and returns a typed ForgerWriteConfig.
Every limit, timeout, and parameter lives here — no magic numbers in any
other module.

Design reference: §5.1
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, ValidationError

from .errors import CONFIG_ERROR, PublicError

# ── Config error ────────────────────────────────────────────────────────────


class ConfigError(PublicError):
    """Configuration loading or validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(code=CONFIG_ERROR, message=message)


# ── Config section models ────────────────────────────────────────────────────


class ProjectConfig(BaseModel):
    """Project identity and language settings."""

    name: str
    language: str = "rust"
    repo_root: str = "."


class LocalModelConfig(BaseModel):
    """Local model backend connection and generation parameters."""

    provider: str = "llama_cpp"
    endpoint: str = "http://127.0.0.1:8080/v1"
    model: str = "omnicoder-9b"
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.20
    top_p: Annotated[float, Field(gt=0.0, le=1.0)] = 0.90
    top_k: Annotated[int, Field(ge=1)] = 20
    max_tokens: Annotated[int, Field(ge=128, le=32768)] = 8192
    json_retries: Annotated[int, Field(ge=0, le=5)] = 2
    request_timeout_seconds: Annotated[float, Field(ge=5.0, le=3600.0)] = 180.0
    retry_base_delay_seconds: Annotated[float, Field(gt=0.0, le=60.0)] = 0.5
    retry_max_delay_seconds: Annotated[float, Field(gt=0.0, le=300.0)] = 8.0
    retry_multiplier: Annotated[float, Field(gt=1.0, le=10.0)] = 2.0


class LimitsConfig(BaseModel):
    """Resource limits for context building and validation output."""

    context_file_max_bytes: Annotated[int, Field(ge=1024, le=100_000_000)] = 200_000
    context_total_max_bytes: Annotated[int, Field(ge=10_000, le=500_000_000)] = 8_000_000
    validation_output_max_chars: Annotated[int, Field(ge=1_000, le=1_000_000)] = 16_000
    operation_batch_max_operations: Annotated[int, Field(ge=1, le=256)] = 32
    operation_content_max_bytes: Annotated[int, Field(ge=64, le=10_000_000)] = 200_000
    artifact_retention_days: Annotated[int, Field(ge=1, le=3_650)] = 90


class ValidationConfig(BaseModel):
    """Validation profile and command configuration."""

    commands: dict[str, str]
    profiles: dict[str, list[str]]
    default_timeout_seconds: Annotated[int, Field(ge=1, le=3600)] = 300
    graceful_kill_timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 5


class PermissionsConfig(BaseModel):
    """Safety permissions and approval requirements."""

    require_clean_worktree: bool = True
    allow_unknown_commands: bool = False
    require_approval_for_new_dependencies: bool = True
    require_approval_for_delete: bool = True
    require_approval_for_full_file_replace: bool = True
    allow_unified_diff_fallback: bool = False


class HygieneConfig(BaseModel):
    """Path patterns excluded from context building."""

    generated_globs: list[str] = Field(default_factory=lambda: ["target/**"])
    vendor_globs: list[str] = Field(default_factory=lambda: ["vendor/**"])


class RepairConfig(BaseModel):
    """Bounded repair loop configuration."""

    max_attempts: Annotated[int, Field(ge=0, le=10)] = 2
    scope_must_match_original_slice: bool = True


class RagConfig(BaseModel):
    """RAG (Retrieval-Augmented Generation) configuration."""

    enabled: bool = False
    index_path: str = "data/rag/index.tqi"
    k_documents: Annotated[int, Field(ge=1, le=20)] = 5
    embedding_model_name: str = "Alibaba-NLP/gte-modernbert-base"
    max_rag_tokens: Annotated[int, Field(ge=64, le=16384)] = 2048


# ── Root config model ───────────────────────────────────────────────────────


class ForgerWriteConfig(BaseModel):
    """Root configuration for a ForgerWrite MCP project."""

    project: ProjectConfig
    local_model: LocalModelConfig
    validation: ValidationConfig
    permissions: PermissionsConfig
    hygiene: HygieneConfig
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    repair: RepairConfig = Field(default_factory=RepairConfig)
    rag: RagConfig = Field(default_factory=RagConfig)


# ── Loader ──────────────────────────────────────────────────────────────────

_CONFIG_RELATIVE_PATH: str = ".forgerwrite/forgerwrite.toml"


def load_config(project_root: Path) -> ForgerWriteConfig:
    """Load and validate forgerwrite.toml from a project root directory.

    Args:
        project_root: The root of the project containing .forgerwrite/.

    Returns:
        A fully validated ForgerWriteConfig.

    Raises:
        ConfigError: If the config file is missing, malformed, or invalid.
    """
    config_path = project_root.resolve() / _CONFIG_RELATIVE_PATH
    if not config_path.exists():
        raise ConfigError(f"Config not found: {config_path}")
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        return ForgerWriteConfig.model_validate(raw)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML: {exc}") from exc
    except ValidationError as exc:
        raise ConfigError(f"Invalid config: {exc}") from exc
