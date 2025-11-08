"""Unit tests for orchestration configuration (Phase 4).

Tests configuration management including:
- Default values
- File-based configuration
- Environment variable overrides
- Configuration merging and priority
- Validation
- Conversion to HookOrchestratorSettings
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from crackerjack.orchestration.config import OrchestrationConfig
from crackerjack.orchestration.hook_orchestrator import HookOrchestratorSettings


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Create temporary config file."""
    config_path = tmp_path / ".crackerjack.yaml"
    config_content = """
orchestration:
  enable: true
  mode: acb
  enable_caching: true
  cache_backend: memory
  cache_ttl: 7200
  cache_max_entries: 200
  max_parallel_hooks: 8
  default_timeout: 900
  stop_on_critical_failure: false
  enable_dependency_resolution: true
  log_cache_stats: true
  log_execution_timing: true
"""
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
def minimal_config_file(tmp_path: Path) -> Path:
    """Create minimal config file."""
    config_path = tmp_path / ".crackerjack.yaml"
    config_content = """
orchestration:
  enable: true
"""
    config_path.write_text(config_content)
    return config_path


class TestOrchestrationConfigDefaults:
    """Test default configuration values."""

    def test_default_values(self):
        """Test that default values are sensible."""
        config = OrchestrationConfig()

        assert config.enable_orchestration is True
        assert config.orchestration_mode == "acb"
        assert config.enable_caching is True
        assert config.cache_backend == "memory"
        assert config.cache_ttl == 3600
        assert config.cache_max_entries == 100
        assert config.max_parallel_hooks == 4
        assert config.default_timeout == 600
        assert config.stop_on_critical_failure is True
        assert config.enable_dependency_resolution is True
        assert config.log_cache_stats is False
        assert config.log_execution_timing is False
        assert config.config_file_path is None


class TestOrchestrationConfigFromFile:
    """Test file-based configuration loading."""

    def test_load_from_file(self, config_file: Path):
        """Test loading configuration from file."""
        config = OrchestrationConfig.from_file(config_file)

        assert config.enable_orchestration is True
        assert config.orchestration_mode == "acb"
        assert config.enable_caching is True
        assert config.cache_backend == "memory"
        assert config.cache_ttl == 7200
        assert config.cache_max_entries == 200
        assert config.max_parallel_hooks == 8
        assert config.default_timeout == 900
        assert config.stop_on_critical_failure is False
        assert config.enable_dependency_resolution is True
        assert config.log_cache_stats is True
        assert config.log_execution_timing is True
        assert config.config_file_path == config_file

    def test_load_minimal_file(self, minimal_config_file: Path):
        """Test loading minimal config file uses defaults."""
        config = OrchestrationConfig.from_file(minimal_config_file)

        assert config.enable_orchestration is True  # From file
        assert config.orchestration_mode == "acb"  # Default
        assert config.enable_caching is True  # Default
        assert config.cache_backend == "memory"  # Default

    def test_nonexistent_file_raises(self):
        """Test that loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            OrchestrationConfig.from_file(Path("/nonexistent/path.yaml"))

    def test_invalid_yaml_raises(self, tmp_path: Path):
        """Test that invalid YAML raises error."""
        config_path = tmp_path / ".crackerjack.yaml"
        config_path.write_text("invalid: yaml: content: :")

        with pytest.raises(ValueError, match="Invalid YAML"):
            OrchestrationConfig.from_file(config_path)


class TestOrchestrationConfigFromEnv:
    """Test environment variable configuration."""

    def test_load_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("CRACKERJACK_ENABLE_ORCHESTRATION", "true")
        monkeypatch.setenv("CRACKERJACK_ORCHESTRATION_MODE", "legacy")
        monkeypatch.setenv("CRACKERJACK_ENABLE_CACHING", "false")
        monkeypatch.setenv("CRACKERJACK_CACHE_BACKEND", "tool_proxy")
        monkeypatch.setenv("CRACKERJACK_CACHE_TTL", "1800")
        monkeypatch.setenv("CRACKERJACK_CACHE_MAX_ENTRIES", "50")
        monkeypatch.setenv("CRACKERJACK_MAX_PARALLEL_HOOKS", "2")
        monkeypatch.setenv("CRACKERJACK_DEFAULT_TIMEOUT", "300")
        monkeypatch.setenv("CRACKERJACK_STOP_ON_CRITICAL_FAILURE", "false")

        config = OrchestrationConfig.from_env()

        assert config.enable_orchestration is True
        assert config.orchestration_mode == "legacy"
        assert config.enable_caching is False
        assert config.cache_backend == "tool_proxy"
        assert config.cache_ttl == 1800
        assert config.cache_max_entries == 50
        assert config.max_parallel_hooks == 2
        assert config.default_timeout == 300
        assert config.stop_on_critical_failure is False

    def test_env_bool_parsing(self, monkeypatch):
        """Test boolean environment variable parsing."""
        # Test true values
        for val in ("true", "1", "yes"):
            monkeypatch.setenv("CRACKERJACK_ENABLE_ORCHESTRATION", val)
            config = OrchestrationConfig.from_env()
            assert config.enable_orchestration is True

        # Test false values
        for val in ("false", "0", "no"):
            monkeypatch.setenv("CRACKERJACK_ENABLE_ORCHESTRATION", val)
            config = OrchestrationConfig.from_env()
            assert config.enable_orchestration is False

    def test_env_invalid_int_uses_default(self, monkeypatch):
        """Test that invalid integers fall back to defaults."""
        monkeypatch.setenv("CRACKERJACK_CACHE_TTL", "invalid")

        config = OrchestrationConfig.from_env()

        assert config.cache_ttl == OrchestrationConfig.cache_ttl  # Default


class TestOrchestrationConfigMerging:
    """Test configuration merging and priority."""

    def test_env_overrides_file(self, config_file: Path, monkeypatch):
        """Test that environment variables override file settings."""
        monkeypatch.setenv("CRACKERJACK_ORCHESTRATION_MODE", "legacy")
        monkeypatch.setenv("CRACKERJACK_MAX_PARALLEL_HOOKS", "16")

        config = OrchestrationConfig.load(config_file)

        # From env (overrides file)
        assert config.orchestration_mode == "legacy"
        assert config.max_parallel_hooks == 16

        # From file (not overridden)
        assert config.enable_orchestration is True
        assert config.cache_ttl == 7200

    def test_file_overrides_defaults(self, minimal_config_file: Path):
        """Test that file settings override defaults."""
        config = OrchestrationConfig.load(minimal_config_file)

        # From file
        assert config.enable_orchestration is True

        # Defaults (not in file)
        assert config.orchestration_mode == "acb"
        assert config.cache_backend == "memory"

    def test_load_without_file_uses_defaults(self, tmp_path: Path):
        """Test that load() uses defaults when file doesn't exist."""
        nonexistent = tmp_path / ".crackerjack.yaml"
        config = OrchestrationConfig.load(nonexistent)

        assert config.enable_orchestration is True  # Default
        assert config.orchestration_mode == "acb"  # Default


class TestOrchestrationConfigValidation:
    """Test configuration validation."""

    def test_valid_config(self):
        """Test that valid configuration passes validation."""
        config = OrchestrationConfig()
        errors = config.validate()

        assert errors == []

    def test_invalid_orchestration_mode(self):
        """Test validation of invalid orchestration mode."""
        config = OrchestrationConfig(orchestration_mode="invalid")
        errors = config.validate()

        assert len(errors) == 1
        assert "orchestration_mode" in errors[0]
        assert "invalid" in errors[0].lower()

    def test_invalid_cache_backend(self):
        """Test validation of invalid cache backend."""
        config = OrchestrationConfig(cache_backend="invalid")
        errors = config.validate()

        assert len(errors) == 1
        assert "cache_backend" in errors[0]

    def test_invalid_numeric_values(self):
        """Test validation of invalid numeric values."""
        config = OrchestrationConfig(
            cache_ttl=-1,
            cache_max_entries=0,
            max_parallel_hooks=-5,
            default_timeout=0,
        )
        errors = config.validate()

        assert len(errors) == 4
        assert any("cache_ttl" in e for e in errors)
        assert any("cache_max_entries" in e for e in errors)
        assert any("max_parallel_hooks" in e for e in errors)
        assert any("default_timeout" in e for e in errors)


class TestOrchestrationConfigConversion:
    """Test configuration conversion."""

    def test_to_orchestrator_settings(self):
        """Test conversion to HookOrchestratorSettings."""
        config = OrchestrationConfig(
            orchestration_mode="legacy",
            enable_caching=False,
            cache_backend="tool_proxy",
            max_parallel_hooks=8,
        )

        settings = config.to_orchestrator_settings()

        assert isinstance(settings, HookOrchestratorSettings)
        assert settings.execution_mode == "legacy"
        assert settings.enable_caching is False
        assert settings.cache_backend == "tool_proxy"
        assert settings.max_parallel_hooks == 8

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = OrchestrationConfig(
            enable_orchestration=True, orchestration_mode="acb", cache_ttl=7200
        )

        config_dict = config.to_dict()

        assert config_dict["orchestration"]["enable"] is True
        assert config_dict["orchestration"]["mode"] == "acb"
        assert config_dict["orchestration"]["cache_ttl"] == 7200


class TestOrchestrationConfigSave:
    """Test configuration saving."""

    def test_save_to_file(self, tmp_path: Path):
        """Test saving configuration to file."""
        config_path = tmp_path / ".crackerjack.yaml"
        config = OrchestrationConfig(
            enable_orchestration=True, orchestration_mode="legacy", cache_ttl=1800
        )

        config.save(config_path)

        # Verify file was created
        assert config_path.exists()

        # Load and verify content
        loaded = OrchestrationConfig.from_file(config_path)
        assert loaded.enable_orchestration is True
        assert loaded.orchestration_mode == "legacy"
        assert loaded.cache_ttl == 1800
