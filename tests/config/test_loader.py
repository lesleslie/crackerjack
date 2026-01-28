import tempfile
import yaml
from pathlib import Path
import pytest
from unittest.mock import patch, mock_open
from pydantic import BaseModel
from crackerjack.config.loader import (
    _load_single_config_file,
    _merge_config_data,
    _extract_adapter_timeouts,
    _load_pyproject_toml,
    load_settings,
    load_settings_async,
    _load_yaml_data,
    _load_single_yaml_file,
    _filter_relevant_data,
    _log_filtered_fields,
    _log_load_info
)


class MockSettings(BaseModel):
    """Mock settings class for testing."""
    name: str = "default"
    value: int = 42
    timeout: int = 30


def test_load_single_config_file_exists():
    """Test loading a single config file that exists."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        yaml.dump({"name": "test", "value": 100}, tmp)
        tmp_path = Path(tmp.name)

    try:
        data = _load_single_config_file(tmp_path)
        assert data == {"name": "test", "value": 100}
    finally:
        tmp_path.unlink()


def test_load_single_config_file_not_exists():
    """Test loading a single config file that doesn't exist."""
    data = _load_single_config_file(Path("nonexistent.yaml"))
    assert data == {}


def test_load_single_config_file_invalid_yaml():
    """Test loading a config file with invalid YAML."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        tmp.write("invalid: [ yaml: content")
        tmp_path = Path(tmp.name)

    try:
        data = _load_single_config_file(tmp_path)
        assert data == {}  # Should return empty dict on error
    finally:
        tmp_path.unlink()


def test_merge_config_data():
    """Test merging multiple config files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        # Create first config file
        config1_path = tmp_dir_path / "config1.yaml"
        with config1_path.open('w') as f:
            yaml.dump({"name": "first", "value": 1}, f)

        # Create second config file
        config2_path = tmp_dir_path / "config2.yaml"
        with config2_path.open('w') as f:
            yaml.dump({"name": "second", "extra": "data"}, f)

        merged = _merge_config_data([config1_path, config2_path])

        # Second file should override first for overlapping keys
        assert merged["name"] == "second"
        assert merged["value"] == 1
        assert merged["extra"] == "data"


def test_extract_adapter_timeouts():
    """Test extracting adapter timeouts from config."""
    config = {
        "name": "test",
        "ruff_timeout": 60,
        "mypy_timeout": 120,
        "value": 42
    }

    _extract_adapter_timeouts(config)

    # Check that timeouts were extracted
    assert "adapter_timeouts" in config
    assert config["adapter_timeouts"]["ruff_timeout"] == 60
    assert config["adapter_timeouts"]["mypy_timeout"] == 120

    # Check that original timeout keys were removed
    assert "ruff_timeout" not in config
    assert "mypy_timeout" not in config

    # Check that non-timeout keys remain
    assert config["name"] == "test"
    assert config["value"] == 42


def test_load_pyproject_toml_exists():
    """Test loading configuration from pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        # Create a pyproject.toml file
        pyproject_path = tmp_dir_path.parent / "pyproject.toml"  # Need to simulate parent structure
        with tempfile.TemporaryDirectory() as outer_tmp:
            outer_path = Path(outer_tmp)
            pyproject_path = outer_path / "pyproject.toml"

            with pyproject_path.open('w') as f:
                f.write("""
[tool.crackerjack]
name = "from_pyproject"
value = 999
ruff_timeout = 45
""")

            # Create a settings directory to match the expected structure
            settings_dir = outer_path / "settings"
            settings_dir.mkdir()

            data = _load_pyproject_toml(settings_dir)

            # Check that the data was loaded correctly
            assert data["name"] == "from_pyproject"
            assert data["value"] == 999
            assert data["adapter_timeouts"]["ruff_timeout"] == 45


def test_load_settings():
    """Test loading settings with the main function."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        # Create settings directory
        settings_dir = tmp_dir_path / "settings"
        settings_dir.mkdir()

        # Create a config file
        config_path = settings_dir / "crackerjack.yaml"
        with config_path.open('w') as f:
            yaml.dump({"name": "configured", "value": 200}, f)

        # Load settings
        settings = load_settings(MockSettings, settings_dir)

        assert settings.name == "configured"
        assert settings.value == 200
        assert settings.timeout == 30  # Default value


@pytest.mark.asyncio
async def test_load_settings_async():
    """Test loading settings with the async function."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        # Create settings directory
        settings_dir = tmp_dir_path / "settings"
        settings_dir.mkdir()

        # Create a config file
        config_path = settings_dir / "crackerjack.yaml"
        with config_path.open('w') as f:
            yaml.dump({"name": "async_configured", "value": 300}, f)

        # Load settings
        settings = await load_settings_async(MockSettings, settings_dir)

        assert settings.name == "async_configured"
        assert settings.value == 300
        assert settings.timeout == 30  # Default value


@pytest.mark.asyncio
async def test_load_yaml_data():
    """Test loading YAML data asynchronously."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        # Create a config file
        config_path = tmp_dir_path / "test.yaml"
        with config_path.open('w') as f:
            yaml.dump({"name": "yaml_test", "value": 400}, f)

        data = await _load_yaml_data([config_path])

        assert data["name"] == "yaml_test"
        assert data["value"] == 400


@pytest.mark.asyncio
async def test_load_single_yaml_file():
    """Test loading a single YAML file asynchronously."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        yaml.dump({"name": "single_file", "value": 500}, tmp)
        tmp_path = Path(tmp.name)

    try:
        data = await _load_single_yaml_file(tmp_path)
        assert data == {"name": "single_file", "value": 500}
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_load_single_yaml_file_not_exists():
    """Test loading a single YAML file that doesn't exist asynchronously."""
    data = await _load_single_yaml_file(Path("nonexistent.yaml"))
    assert data is None


def test_filter_relevant_data():
    """Test filtering relevant data for a settings class."""
    merged_data = {
        "name": "test",
        "value": 100,
        "unknown_field": "should_be_filtered",
        "another_unknown": "also_filtered"
    }

    filtered_data = _filter_relevant_data(merged_data, MockSettings)

    # Should only contain fields that exist in MockSettings
    assert "name" in filtered_data
    assert "value" in filtered_data
    assert "unknown_field" not in filtered_data
    assert "another_unknown" not in filtered_data
    assert filtered_data["name"] == "test"
    assert filtered_data["value"] == 100


def test_log_filtered_fields(caplog):
    """Test logging of filtered fields."""
    merged_data = {
        "name": "test",
        "value": 100,
        "unknown_field": "should_be_filtered"
    }

    relevant_data = {
        "name": "test",
        "value": 100
    }

    with caplog.at_level("DEBUG"):
        _log_filtered_fields(merged_data, relevant_data)

        # Check that the unknown field was logged
        assert "unknown_field" in caplog.text


def test_log_load_info(caplog):
    """Test logging of load information."""
    relevant_data = {
        "name": "test",
        "value": 100
    }

    with caplog.at_level("DEBUG"):
        _log_load_info(MockSettings, relevant_data)

        # Check that the load info was logged
        assert "Loaded 2 configuration values" in caplog.text
        assert "MockSettings" in caplog.text
