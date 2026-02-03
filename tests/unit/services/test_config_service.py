"""Tests for configuration service."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from crackerjack.services.config_service import ConfigService
from crackerjack.config.settings import CrackerjackSettings


class TestConfigService:
    """Tests for ConfigService."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create a temporary config directory."""
        config_dir = tmp_path / ".crackerjack"
        config_dir.mkdir()
        return config_dir

    @pytest.fixture
    def sample_settings(self, temp_config_dir):
        """Create sample settings file."""
        settings_file = temp_config_dir / "settings.yaml"
        settings_file.write_text(
            """
ai:
  ai_provider: claude
  max_iterations: 10

test:
  test_workers: 4
  coverage: true

execution:
  verbose: false
  interactive: false
""",
        )
        return settings_file

    @pytest.fixture
    def config_service(self, temp_config_dir):
        """Create a ConfigService instance."""
        return ConfigService(config_dir=temp_config_dir)

    def test_initialization(self, config_service, temp_config_dir):
        """Test ConfigService initialization."""
        assert config_service.config_dir == temp_config_dir
        assert config_service.cache is not None

    def test_load_settings(self, config_service, sample_settings):
        """Test loading settings from file."""
        settings = config_service.load_settings()

        assert isinstance(settings, CrackerjackSettings)
        assert settings.ai.ai_provider == "claude"
        assert settings.ai.max_iterations == 10
        assert settings.test.test_workers == 4
        assert settings.test.coverage is True

    def test_load_settings_defaults(self, config_service):
        """Test loading settings with defaults when file doesn't exist."""
        settings = config_service.load_settings()

        assert isinstance(settings, CrackerjackSettings)
        # Should have default values
        assert settings.ai.ai_provider == "claude"
        assert settings.execution.verbose is False

    def test_save_settings(self, config_service, temp_config_dir):
        """Test saving settings to file."""
        settings = CrackerjackSettings(
            ai={
                "ai_provider": "qwen",
                "max_iterations": 15,
            },
            test={
                "test_workers": 8,
                "coverage": True,
            },
        )

        config_service.save_settings(settings)

        # Verify file was created
        settings_file = temp_config_dir / "settings.yaml"
        assert settings_file.exists()

        # Load and verify
        loaded_settings = config_service.load_settings()
        assert loaded_settings.ai.ai_provider == "qwen"
        assert loaded_settings.ai.max_iterations == 15
        assert loaded_settings.test.test_workers == 8

    def test_get_setting(self, config_service, sample_settings):
        """Test getting a specific setting."""
        value = config_service.get_setting("ai.ai_provider")
        assert value == "claude"

        value = config_service.get_setting("test.test_workers")
        assert value == 4

    def test_get_setting_nested(self, config_service, sample_settings):
        """Test getting nested setting values."""
        value = config_service.get_setting("execution.verbose")
        assert value is False

    def test_get_setting_nonexistent(self, config_service, sample_settings):
        """Test getting a non-existent setting."""
        value = config_service.get_setting("nonexistent.setting")
        assert value is None

    def test_set_setting(self, config_service, temp_config_dir):
        """Test setting a configuration value."""
        config_service.set_setting("ai.ai_provider", "ollama")
        config_service.set_setting("test.test_workers", 6)

        # Verify settings were updated
        settings = config_service.load_settings()
        assert settings.ai.ai_provider == "ollama"
        assert settings.test.test_workers == 6

    def test_update_settings(self, config_service, temp_config_dir):
        """Test updating multiple settings at once."""
        updates = {
            "ai.ai_provider": "qwen",
            "test.coverage": False,
            "execution.verbose": True,
        }

        config_service.update_settings(updates)

        settings = config_service.load_settings()
        assert settings.ai.ai_provider == "qwen"
        assert settings.test.coverage is False
        assert settings.execution.verbose is True

    def test_reset_to_defaults(self, config_service, sample_settings, temp_config_dir):
        """Test resetting settings to defaults."""
        # First, load custom settings
        settings = config_service.load_settings()
        assert settings.ai.ai_provider == "claude"

        # Reset to defaults
        config_service.reset_to_defaults()

        # Verify reset
        settings = config_service.load_settings()
        # Should have default values
        assert isinstance(settings, CrackerjackSettings)

    def test_validate_settings(self, config_service):
        """Test settings validation."""
        settings = CrackerjackSettings(
            ai={
                "ai_provider": "claude",
                "max_iterations": 10,
            }
        )

        is_valid, errors = config_service.validate_settings(settings)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_settings_invalid(self, config_service):
        """Test validation with invalid settings."""
        # Create invalid settings
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CrackerjackSettings(
                ai={
                    "ai_provider": "invalid_provider",  # Invalid value
                    "max_iterations": 10,
                }
            )

    def test_export_settings_json(self, config_service, sample_settings, tmp_path):
        """Test exporting settings to JSON."""
        settings = config_service.load_settings()
        export_file = tmp_path / "settings_export.json"

        config_service.export_settings(export_file, format="json")

        assert export_file.exists()

        # Verify content
        with export_file.open("r") as f:
            data = json.load(f)
            assert data["ai"]["ai_provider"] == "claude"
            assert data["test"]["test_workers"] == 4

    def test_export_settings_yaml(self, config_service, sample_settings, tmp_path):
        """Test exporting settings to YAML."""
        settings = config_service.load_settings()
        export_file = tmp_path / "settings_export.yaml"

        config_service.export_settings(export_file, format="yaml")

        assert export_file.exists()

    def test_import_settings_json(self, config_service, temp_config_dir, tmp_path):
        """Test importing settings from JSON."""
        import_file = tmp_path / "settings_import.json"
        import_data = {
            "ai": {"ai_provider": "ollama", "max_iterations": 20},
            "test": {"test_workers": 6, "coverage": True},
        }

        with import_file.open("w") as f:
            json.dump(import_data, f)

        config_service.import_settings(import_file, format="json")

        settings = config_service.load_settings()
        assert settings.ai.ai_provider == "ollama"
        assert settings.ai.max_iterations == 20
        assert settings.test.test_workers == 6

    def test_get_all_settings(self, config_service, sample_settings):
        """Test getting all settings as dictionary."""
        settings_dict = config_service.get_all_settings()

        assert isinstance(settings_dict, dict)
        assert "ai" in settings_dict
        assert "test" in settings_dict
        assert "execution" in settings_dict

    def test_reload_settings(self, config_service, sample_settings):
        """Test reloading settings."""
        # Load initial settings
        settings1 = config_service.load_settings()

        # Modify file externally
        sample_settings.write_text(
            """
ai:
  ai_provider: qwen
  max_iterations: 25
""",
        )

        # Reload
        settings2 = config_service.reload_settings()

        assert settings2.ai.ai_provider == "qwen"
        assert settings2.ai.max_iterations == 25

    def test_cache_invalidation(self, config_service, sample_settings):
        """Test cache invalidation."""
        # Load settings to populate cache
        settings1 = config_service.load_settings()
        assert settings1.ai.ai_provider == "claude"

        # Invalidate cache
        config_service.invalidate_cache()

        # Modify file
        sample_settings.write_text(
            """
ai:
  ai_provider: ollama
""",
        )

        # Load again - should get fresh data
        settings2 = config_service.load_settings()
        assert settings2.ai.ai_provider == "ollama"


class TestConfigIntegration:
    """Integration tests for configuration service."""

    def test_full_config_lifecycle(self, tmp_path):
        """Test complete configuration lifecycle."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        service = ConfigService(config_dir=config_dir)

        # Create initial settings
        settings = CrackerjackSettings(
            ai={"ai_provider": "claude", "max_iterations": 10},
            test={"test_workers": 4, "coverage": True},
        )

        service.save_settings(settings)

        # Load settings
        loaded = service.load_settings()
        assert loaded.ai.ai_provider == "claude"

        # Update specific setting
        service.set_setting("ai.max_iterations", 15)

        # Verify update
        reloaded = service.load_settings()
        assert reloaded.ai.max_iterations == 15

        # Export
        export_file = tmp_path / "export.json"
        service.export_settings(export_file, format="json")
        assert export_file.exists()

        # Reset
        service.reset_to_defaults()
        final = service.load_settings()
        assert isinstance(final, CrackerjackSettings)
