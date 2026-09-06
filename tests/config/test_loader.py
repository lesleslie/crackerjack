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
            yaml.dump({"name": "first", "value":1}, f)

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
    import logging

    merged_data = {
        "name": "test",
        "value": 100,
        "unknown_field": "should_be_filtered"
    }

    relevant_data = {
        "name": "test",
        "value": 100
    }

    # Target the specific logger for crackerjack.config.loader
    with caplog.at_level(logging.DEBUG, logger="crackerjack.config.loader"):
        _log_filtered_fields(merged_data, relevant_data)

        # Check that the unknown field was logged
        assert "unknown_field" in caplog.text


def test_log_load_info(caplog):
    """Test logging of load information."""
    import logging

    relevant_data = {
        "name": "test",
        "value": 100
    }

    # Target the specific logger for crackerjack.config.loader
    with caplog.at_level(logging.DEBUG, logger="crackerjack.config.loader"):
        _log_load_info(MockSettings, relevant_data)

        # Check that the load info was logged
        assert "Loaded 2 configuration values" in caplog.text
        assert "MockSettings" in caplog.text


# --------------------------------------------------------------------------- #
# Extended tests for uncovered branches (push 85% -> 95%+).
# --------------------------------------------------------------------------- #


def test_load_single_config_file_non_dict_yaml():
    """YAML that parses to a non-dict (e.g. a bare scalar or list) should return {}."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        # Bare scalar (string), not a mapping.
        tmp.write("just_a_string_value\n")
        tmp_path = Path(tmp.name)

    try:
        with patch("crackerjack.config.loader.logger") as mock_logger:
            data = _load_single_config_file(tmp_path)
            assert data == {}
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Invalid YAML format" in warning_msg
            assert "str" in warning_msg
    finally:
        tmp_path.unlink()


def test_load_single_config_file_list_yaml():
    """YAML that parses to a list should be treated as invalid and return {}."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        yaml.dump([1, 2, 3], tmp)
        tmp_path = Path(tmp.name)

    try:
        data = _load_single_config_file(tmp_path)
        assert data == {}
    finally:
        tmp_path.unlink()


def test_load_single_config_file_oserror(monkeypatch):
    """An OSError while opening the file is caught and returns {}."""
    fake_path = Path("/does/not/matter.yaml")

    # Force exists() to True, then make .open() raise OSError.
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def _raise_oserror(self, *args, **kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(Path, "open", _raise_oserror)

    with patch("crackerjack.config.loader.logger") as mock_logger:
        data = _load_single_config_file(fake_path)
        assert data == {}
        mock_logger.exception.assert_called_once()
        exc_msg = mock_logger.exception.call_args[0][0]
        assert "Failed to read" in exc_msg


def test_merge_config_data_empty_list():
    """Merging no files returns an empty dict."""
    assert _merge_config_data([]) == {}


def test_merge_config_data_missing_file():
    """A single missing file produces an empty dict (via the not-exists branch)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        missing_path = Path(tmp_dir) / "missing.yaml"
        assert _merge_config_data([missing_path]) == {}


def test_merge_config_data_single_file():
    """Merging one file returns its data unchanged."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = Path(tmp_dir) / "only.yaml"
        with cfg.open("w") as f:
            yaml.dump({"only_key": "only_value", "value": 7}, f)
        merged = _merge_config_data([cfg])
        assert merged == {"only_key": "only_value", "value": 7}


def test_extract_adapter_timeouts_no_timeouts():
    """When no *_timeout keys exist, no adapter_timeouts key is added (56->exit)."""
    config = {"name": "test", "value": 42, "regular_key": "stay"}
    _extract_adapter_timeouts(config)
    assert "adapter_timeouts" not in config
    assert config == {"name": "test", "value": 42, "regular_key": "stay"}


def test_extract_adapter_timeouts_empty_dict():
    """An empty dict is a no-op."""
    config: dict[str, object] = {}
    _extract_adapter_timeouts(config)
    assert config == {}


def test_extract_adapter_timeouts_single_timeout():
    """A single _timeout key is moved into adapter_timeouts."""
    config = {"ruff_timeout": 30}
    _extract_adapter_timeouts(config)
    assert config == {"adapter_timeouts": {"ruff_timeout": 30}}


def test_load_pyproject_toml_missing(tmp_path):
    """When no pyproject.toml exists in the parent dir, returns {}."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    # tmp_path.parent is the test runner's tmpdir root; pyproject.toml does not exist there.
    data = _load_pyproject_toml(settings_dir)
    assert data == {}


def test_load_pyproject_toml_no_crackerjack_section(tmp_path):
    """pyproject.toml without [tool.crackerjack] returns {} (no extraction)."""
    outer = tmp_path
    pyproject = outer / "pyproject.toml"
    pyproject.write_text(
        '[tool.other]\nname = "unrelated"\n',
        encoding="utf-8",
    )
    settings_dir = outer / "settings"
    settings_dir.mkdir()
    data = _load_pyproject_toml(settings_dir)
    assert data == {}


def test_load_pyproject_toml_empty_tool_crackerjack(tmp_path):
    """[tool.crackerjack] present but empty -> {} and no extraction call (75->79)."""
    outer = tmp_path
    pyproject = outer / "pyproject.toml"
    pyproject.write_text("[tool.crackerjack]\n", encoding="utf-8")
    settings_dir = outer / "settings"
    settings_dir.mkdir()
    data = _load_pyproject_toml(settings_dir)
    assert data == {}


def test_load_pyproject_toml_invalid_contents(tmp_path):
    """Invalid TOML is caught by the generic exception handler (101-103)."""
    outer = tmp_path
    pyproject = outer / "pyproject.toml"
    pyproject.write_text("this is = not valid toml ====", encoding="utf-8")
    settings_dir = outer / "settings"
    settings_dir.mkdir()
    with patch("crackerjack.config.loader.logger") as mock_logger:
        data = _load_pyproject_toml(settings_dir)
        assert data == {}
        mock_logger.exception.assert_called_once()
        assert "Failed to parse pyproject.toml" in mock_logger.exception.call_args[0][0]


def test_load_pyproject_toml_no_toml_libraries(monkeypatch, tmp_path):
    """When neither tomllib nor tomli is importable, returns {} with a warning."""
    outer = tmp_path
    pyproject = outer / "pyproject.toml"
    pyproject.write_text("[tool.crackerjack]\nname = 'x'\n", encoding="utf-8")
    settings_dir = outer / "settings"
    settings_dir.mkdir()

    # Make both import statements raise ImportError.
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name in ("tomllib", "tomli"):
            raise ImportError(f"simulated missing {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with patch("crackerjack.config.loader.logger") as mock_logger:
        data = _load_pyproject_toml(settings_dir)
        assert data == {}
        mock_logger.warning.assert_called_once()
        assert "Neither tomllib nor tomli" in mock_logger.warning.call_args[0][0]


def test_load_settings_uses_pyproject_data(tmp_path):
    """load_settings merges pyproject.toml [tool.crackerjack] into the result."""
    outer = tmp_path
    pyproject = outer / "pyproject.toml"
    pyproject.write_text(
        '[tool.crackerjack]\nname = "from_pyproject"\nvalue = 777\n',
        encoding="utf-8",
    )
    settings_dir = outer / "settings"
    settings_dir.mkdir()

    settings = load_settings(MockSettings, settings_dir)
    assert settings.name == "from_pyproject"
    assert settings.value == 777


def test_load_settings_filters_unknown_fields(tmp_path):
    """load_settings logs ignored (non-model) fields but still constructs the model."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    config = settings_dir / "crackerjack.yaml"
    config.write_text(
        "name: configured\nvalue: 100\nsome_unknown_key: ignored\n",
        encoding="utf-8",
    )

    with patch("crackerjack.config.loader.logger") as mock_logger:
        settings = load_settings(MockSettings, settings_dir)
        assert settings.name == "configured"
        assert settings.value == 100
        # The "Ignored unknown configuration fields" debug log was emitted.
        debug_msgs = [c.args[0] for c in mock_logger.debug.call_args_list]
        assert any("Ignored unknown configuration fields" in m for m in debug_msgs)


def test_load_settings_uses_defaults(tmp_path):
    """Without any config files, defaults from the model are used."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    settings = load_settings(MockSettings, settings_dir)
    assert settings.name == "default"
    assert settings.value == 42
    assert settings.timeout == 30


@pytest.mark.asyncio
async def test_load_settings_async_uses_defaults(tmp_path, monkeypatch):
    """load_settings_async without settings_dir defaults to <cwd>/settings (line 145)."""
    import tempfile as _tf

    with _tf.TemporaryDirectory() as cwd:
        monkeypatch.chdir(cwd)
        # No settings dir in cwd; load_settings_async should fall back to defaults.
        settings = await load_settings_async(MockSettings)
        assert settings.name == "default"
        assert settings.value == 42


@pytest.mark.asyncio
async def test_load_settings_async_uses_pyproject_data(tmp_path):
    """load_settings_async pulls [tool.crackerjack] from pyproject.toml."""
    outer = tmp_path
    pyproject = outer / "pyproject.toml"
    pyproject.write_text(
        '[tool.crackerjack]\nname = "async_pyproject"\nvalue = 555\n',
        encoding="utf-8",
    )
    settings_dir = outer / "settings"
    settings_dir.mkdir()

    settings = await load_settings_async(MockSettings, settings_dir)
    assert settings.name == "async_pyproject"
    assert settings.value == 555


@pytest.mark.asyncio
async def test_load_yaml_data_skips_missing_files(tmp_path):
    """Files that do not exist are skipped (170->166)."""
    missing = tmp_path / "nope.yaml"
    data = await _load_yaml_data([missing])
    assert data == {}


@pytest.mark.asyncio
async def test_load_yaml_data_mixed_missing_and_present(tmp_path):
    """A missing file does not block loading from a present file."""
    present = tmp_path / "present.yaml"
    present.write_text("name: present\nvalue: 11\n", encoding="utf-8")
    missing = tmp_path / "missing.yaml"
    data = await _load_yaml_data([missing, present])
    assert data == {"name": "present", "value": 11}


@pytest.mark.asyncio
async def test_load_single_yaml_file_non_dict():
    """Non-dict YAML returns {} (not None) from _load_single_yaml_file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        tmp.write("just_a_string\n")
        tmp_path = Path(tmp.name)
    try:
        with patch("crackerjack.config.loader.logger") as mock_logger:
            data = await _load_single_yaml_file(tmp_path)
            assert data == {}
            mock_logger.warning.assert_called_once()
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_load_single_yaml_file_yamlerror(monkeypatch):
    """YAMLError during parsing is caught and returns None."""
    fake_path = Path("/fake/config.yaml")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def _raise_yamlerror(*args, **kwargs):
        import yaml as _yaml

        raise _yaml.YAMLError("simulated parse failure")

    monkeypatch.setattr(Path, "open", _raise_yamlerror)

    with patch("crackerjack.config.loader.logger") as mock_logger:
        data = await _load_single_yaml_file(fake_path)
        assert data is None
        mock_logger.exception.assert_called_once()
        assert "Failed to parse YAML" in mock_logger.exception.call_args[0][0]


@pytest.mark.asyncio
async def test_load_single_yaml_file_oserror(monkeypatch):
    """OSError during read is caught and returns None."""
    fake_path = Path("/fake/config.yaml")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def _raise_oserror(self, *args, **kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(Path, "open", _raise_oserror)

    with patch("crackerjack.config.loader.logger") as mock_logger:
        data = await _load_single_yaml_file(fake_path)
        assert data is None
        mock_logger.exception.assert_called_once()
        assert "Failed to read" in mock_logger.exception.call_args[0][0]


def test_filter_relevant_data_empty_input():
    """Empty dict passes through _filter_relevant_data unchanged."""
    assert _filter_relevant_data({}, MockSettings) == {}


def test_filter_relevant_data_all_unknown():
    """A dict with only unknown keys filters down to empty."""
    filtered = _filter_relevant_data({"a": 1, "b": 2}, MockSettings)
    assert filtered == {}


def test_log_filtered_fields_no_excluded(caplog):
    """No debug log is emitted when nothing is filtered out."""
    import logging

    merged = {"name": "x", "value": 1}
    relevant = {"name": "x", "value": 1}
    with caplog.at_level(logging.DEBUG, logger="crackerjack.config.loader"):
        _log_filtered_fields(merged, relevant)
    # No "Ignored unknown configuration fields" log expected.
    assert "Ignored unknown configuration fields" not in caplog.text


def test_log_load_info_empty_data(caplog):
    """_log_load_info reports 0 values when relevant_data is empty."""
    import logging

    with caplog.at_level(logging.DEBUG, logger="crackerjack.config.loader"):
        _log_load_info(MockSettings, {})
    assert "Loaded 0 configuration values" in caplog.text
    assert "MockSettings" in caplog.text
