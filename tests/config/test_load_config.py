"""Tests for the configuration module."""

from pathlib import Path

import pytest


class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_config_returns_typed_model(self, tmp_path: Path) -> None:
        """load_config parses a valid forgerwrite.toml into typed model."""
        from forgerwrite_mcp.config import ForgerWriteConfig, load_config

        _write_fixture(tmp_path)
        cfg = load_config(tmp_path)
        assert isinstance(cfg, ForgerWriteConfig)
        assert cfg.project.name == "test-project"
        assert cfg.project.language == "rust"
        assert cfg.local_model.model == "omnicoder-9b"

    def test_load_config_rejects_missing_file(self, tmp_path: Path) -> None:
        """load_config raises when .forgerwrite/forgerwrite.toml is missing."""
        from forgerwrite_mcp.config import ConfigError, load_config

        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path)

    def test_load_config_rejects_invalid_toml(self, tmp_path: Path) -> None:
        """load_config raises ConfigError on malformed TOML."""
        from forgerwrite_mcp.config import ConfigError, load_config

        cfg_dir = tmp_path / ".forgerwrite"
        cfg_dir.mkdir()
        (cfg_dir / "forgerwrite.toml").write_text("this is not valid toml {{{", encoding="utf-8")
        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config(tmp_path)

    def test_load_config_rejects_invalid_values(self, tmp_path: Path) -> None:
        """load_config raises ConfigError when values fail Pydantic validation."""
        from forgerwrite_mcp.config import ConfigError, load_config

        _write_fixture(tmp_path, overrides={"temperature": "3.0"})
        with pytest.raises(ConfigError, match="Invalid config"):
            load_config(tmp_path)

    def test_limits_section_has_sane_defaults(self) -> None:
        """LimitsConfig fields all have reasonable default values."""
        from forgerwrite_mcp.config import LimitsConfig

        limits = LimitsConfig()
        assert limits.context_file_max_bytes >= 1024
        assert limits.context_total_max_bytes >= 10000
        assert limits.operation_batch_max_operations >= 1
        assert limits.operation_content_max_bytes >= 64

    def test_validation_timeout_bounded(self) -> None:
        """ValidationConfig default_timeout_seconds is in [1, 3600]."""
        from forgerwrite_mcp.config import ValidationConfig

        v = ValidationConfig(commands={}, profiles={})
        assert 1 <= v.default_timeout_seconds <= 3600

    def test_model_temperature_bounded_between_0_and_2(self) -> None:
        """LocalModelConfig temperature must be in [0.0, 2.0]."""
        import pydantic

        from forgerwrite_mcp.config import LocalModelConfig

        # Valid
        cfg = LocalModelConfig(temperature=0.5)
        assert cfg.temperature == 0.5

        # Below minimum
        with pytest.raises(pydantic.ValidationError):
            LocalModelConfig(temperature=-0.1)

        # Above maximum
        with pytest.raises(pydantic.ValidationError):
            LocalModelConfig(temperature=2.1)

    def test_all_sections_populated_in_default_config(self) -> None:
        """ForgerWriteConfig with minimal input populates all sections."""
        from forgerwrite_mcp.config import ForgerWriteConfig

        cfg = ForgerWriteConfig(
            project={"name": "test", "language": "rust", "repo_root": "."},
            local_model={},
            validation={"commands": {}, "profiles": {}},
            permissions={},
            hygiene={},
        )
        assert cfg.limits is not None
        assert cfg.repair is not None
        assert cfg.project.name == "test"

    def test_graceful_kill_timeout_in_config(self) -> None:
        """ValidationConfig has graceful_kill_timeout_seconds field."""
        from forgerwrite_mcp.config import ValidationConfig

        v = ValidationConfig(commands={}, profiles={})
        assert hasattr(v, "graceful_kill_timeout_seconds")
        assert v.graceful_kill_timeout_seconds >= 1

    def test_retry_backoff_fields_in_config(self) -> None:
        """LocalModelConfig has retry backoff configuration fields."""
        from forgerwrite_mcp.config import LocalModelConfig

        cfg = LocalModelConfig()
        assert hasattr(cfg, "retry_base_delay_seconds")
        assert hasattr(cfg, "retry_max_delay_seconds")
        assert hasattr(cfg, "retry_multiplier")
        assert cfg.retry_base_delay_seconds > 0


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_fixture(
    tmp_path: Path,
    overrides: dict[str, str] | None = None,
) -> None:
    """Copy the valid_config.toml fixture into tmp_path/.forgerwrite/,
    optionally overriding specific lines.
    """
    src = Path(__file__).parent / "valid_config.toml"
    cfg_dir = tmp_path / ".forgerwrite"
    cfg_dir.mkdir()
    dest = cfg_dir / "forgerwrite.toml"
    content = src.read_text(encoding="utf-8")
    if overrides:
        for key, val in overrides.items():
            # Simple string replacement for test overrides
            import re

            content = re.sub(rf"^{key}\s*=\s*.+", f"{key} = {val}", content, flags=re.MULTILINE)
    dest.write_text(content, encoding="utf-8")
