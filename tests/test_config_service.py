"""Tests for the ConfigService."""

import json
import tempfile
from pathlib import Path
import yaml
import pytest
from pydantic import BaseModel, Field
from crackerjack.services.config_service import ConfigService


class TestConfigModel(BaseModel):
    """Test Pydantic model for configuration validation."""
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")  # Example: "1.0.0"
    enabled: bool = True
    settings: dict = {}


class TestConfigService:
    """Test cases for ConfigService functionality."""

    def test_load_json_config(self):
        """Test loading JSON configuration."""
        test_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(test_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            config = ConfigService.load_config(tmp_path)
            assert config == test_data
        finally:
            tmp_path.unlink()

    def test_load_yaml_config(self):
        """Test loading YAML configuration."""
        test_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            yaml.dump(test_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            config = ConfigService.load_config(tmp_path)
            assert config == test_data
        finally:
            tmp_path.unlink()

    def test_load_toml_config(self):
        """Test loading TOML configuration."""
        test_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        toml_content = (
            "name = \"test_app\"\n"
            "version = \"1.0.0\"\n"
            "enabled = true\n"
            "\n"
            "[settings]\n"
            "debug = true\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as tmp:
            tmp.write(toml_content)
            tmp_path = Path(tmp.name)

        try:
            config = ConfigService.load_config(tmp_path)
            assert config == test_data
        finally:
            tmp_path.unlink()

    def test_validate_config_success(self):
        """Test successful configuration validation."""
        config_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        validated_config = ConfigService.validate_config(config_data, TestConfigModel)
        assert isinstance(validated_config, TestConfigModel)
        assert validated_config.name == "test_app"
        assert validated_config.version == "1.0.0"

    def test_validate_config_failure(self):
        """Test configuration validation failure."""
        invalid_config = {
            "name": "test_app",
            "version": "invalid_version",  # Doesn't match pattern
            "enabled": True
        }

        with pytest.raises(Exception):  # Validation error
            ConfigService.validate_config(invalid_config, TestConfigModel)

    def test_save_json_config(self):
        """Test saving JSON configuration."""
        config_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            ConfigService.save_config(config_data, tmp_path)

            # Verify the saved file
            with open(tmp_path) as f:
                saved_data = json.load(f)
            assert saved_data == config_data
        finally:
            tmp_path.unlink()

    def test_save_yaml_config(self):
        """Test saving YAML configuration."""
        config_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            ConfigService.save_config(config_data, tmp_path)

            # Verify the saved file
            with open(tmp_path) as f:
                saved_data = yaml.safe_load(f)
            assert saved_data == config_data
        finally:
            tmp_path.unlink()

    def test_save_toml_config(self):
        """Test saving TOML configuration."""
        config_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            ConfigService.save_config(config_data, tmp_path)

            # Verify the saved file
            import tomllib
            with open(tmp_path, "rb") as f:
                saved_data = tomllib.load(f)
            assert saved_data == config_data
        finally:
            tmp_path.unlink()

    def test_save_config_with_format_override(self):
        """Test saving configuration with explicit format."""
        config_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "config.txt"  # Intentionally wrong extension

            # Save as JSON format despite .txt extension
            ConfigService.save_config(config_data, tmp_path, format="json")

            # Verify it was saved as JSON
            with open(tmp_path) as f:
                saved_data = json.load(f)
            assert saved_data == config_data

    def test_merge_configs_simple(self):
        """Test simple configuration merging."""
        base = {"name": "app", "version": "1.0.0"}
        override = {"version": "2.0.0", "enabled": True}
        expected = {"name": "app", "version": "2.0.0", "enabled": True}

        result = ConfigService.merge_configs(base, override)
        assert result == expected

    def test_merge_configs_nested(self):
        """Test nested configuration merging."""
        base = {
            "name": "app",
            "settings": {"debug": True, "port": 8080}
        }
        override = {
            "settings": {"port": 9000, "host": "localhost"}
        }
        expected = {
            "name": "app",
            "settings": {"debug": True, "port": 9000, "host": "localhost"}
        }

        result = ConfigService.merge_configs(base, override)
        assert result == expected

    def test_unsupported_format(self):
        """Test error for unsupported configuration format."""
        with tempfile.NamedTemporaryFile(suffix='.unsupported', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(ValueError):
                ConfigService.load_config(tmp_path)
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_load_config_async(self):
        """Test asynchronous configuration loading."""
        test_data = {
            "name": "test_app",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"debug": True}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(test_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            config = await ConfigService.load_config_async(tmp_path)
            assert config == test_data
        finally:
            tmp_path.unlink()
