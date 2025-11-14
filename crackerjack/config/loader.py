"""Settings loader for ACB configuration with YAML support.

This module provides utilities for loading ACB Settings from YAML files
with support for configuration layering and environment-specific overrides.

Configuration Priority (highest to lowest):
    1. settings/local.yaml (local overrides, gitignored)
    2. settings/crackerjack.yaml (main configuration)
    3. Default values from Settings class

Example:
    >>> from crackerjack.config import CrackerjackSettings
    >>> settings = CrackerjackSettings.load()
    >>> settings.verbose
    False

    >>> # Async loading with full ACB initialization
    >>> settings = await CrackerjackSettings.load_async()
"""

from __future__ import annotations

import logging
import typing as t
from pathlib import Path
from typing import TypeVar

import yaml
from acb.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Settings)


def _load_single_config_file(config_file: Path) -> dict[str, t.Any]:
    """Load a single config file and return its data."""
    if not config_file.exists():
        logger.debug(f"Configuration file not found: {config_file}")
        return {}

    try:
        with config_file.open() as f:
            loaded_data: t.Any = yaml.safe_load(f)
            if isinstance(loaded_data, dict):
                logger.debug(f"Loaded configuration from {config_file}")
                return loaded_data
            else:
                logger.warning(
                    f"Invalid YAML format in {config_file}: expected dict, got {type(loaded_data).__name__}"
                )
                return {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML from {config_file}: {e}")
        return {}
    except OSError as e:
        logger.error(f"Failed to read {config_file}: {e}")
        return {}


def _merge_config_data(config_files: list[Path]) -> dict[str, t.Any]:
    """Merge data from all config files."""
    merged_data = {}
    for config_file in config_files:
        file_data = _load_single_config_file(config_file)
        merged_data.update(file_data)
    return merged_data


def load_settings[T: Settings](
    settings_class: type[T],
    settings_dir: Path | None = None,
) -> T:
    """Load settings from YAML files with layered configuration.

    This function loads configuration from multiple YAML files and merges them
    with priority-based overriding. Unknown YAML fields are silently ignored.

    Args:
        settings_class: The Settings class to instantiate
        settings_dir: Directory containing YAML files (default: ./settings)

    Returns:
        Initialized Settings instance with merged configuration

    Configuration Priority (highest to lowest):
        1. settings/local.yaml (local overrides, gitignored)
        2. settings/crackerjack.yaml (main configuration)
        3. Default values from Settings class

    Example:
        >>> class MySettings(Settings):
        ...     debug: bool = False
        ...     max_workers: int = 4
        >>> settings = load_settings(MySettings)
        >>> settings.debug
        False
    """
    if settings_dir is None:
        settings_dir = Path.cwd() / "settings"

    # Configuration files in priority order (lowest to highest)
    config_files = [
        settings_dir / "crackerjack.yaml",
        settings_dir / "local.yaml",
    ]

    # Load and merge data from all config files
    merged_data = _merge_config_data(config_files)

    # Filter to only fields defined in the Settings class
    # This prevents validation errors from unknown YAML keys
    relevant_data = {
        k: v for k, v in merged_data.items() if k in settings_class.model_fields
    }

    # Log filtered fields if any were excluded
    excluded_fields = set(merged_data.keys()) - set(relevant_data.keys())
    if excluded_fields:
        logger.debug(
            f"Ignored unknown configuration fields: {', '.join(sorted(excluded_fields))}"
        )

    logger.info(
        f"Loaded {len(relevant_data)} configuration values for {settings_class.__name__}"
    )

    # Synchronous initialization (safe for module-level code)
    return settings_class(**relevant_data)


async def load_settings_async[T: Settings](
    settings_class: type[T],
    settings_dir: Path | None = None,
) -> T:
    """Load settings asynchronously with full ACB initialization.

    This function provides the same configuration loading as load_settings()
    but uses ACB's async initialization which includes secret loading and
    other async setup operations.

    Args:
        settings_class: The Settings class to instantiate
        settings_dir: Directory containing YAML files (default: ./settings)

    Returns:
        Initialized Settings instance with async initialization complete

    Note:
        Use this for application runtime when async context is available.
        For module-level initialization, use synchronous load_settings().

    Example:
        >>> settings = await load_settings_async(CrackerjackSettings)
        >>> settings.verbose
        False
    """
    if settings_dir is None:
        settings_dir = Path.cwd() / "settings"

    # Configuration files in priority order (lowest to highest)
    config_files = [
        settings_dir / "crackerjack.yaml",
        settings_dir / "local.yaml",
    ]

    # Load and merge YAML data from all files
    merged_data = await _load_yaml_data(config_files)

    # Process the loaded data
    relevant_data = _filter_relevant_data(merged_data, settings_class)
    _log_filtered_fields(merged_data, relevant_data)
    _log_load_info(settings_class, relevant_data)

    # Async initialization (loads secrets, performs async setup)
    return await settings_class.create_async(**relevant_data)


async def _load_yaml_data(config_files: list[Path]) -> dict[str, t.Any]:
    """Load and merge YAML data from configuration files."""
    merged_data: dict[str, t.Any] = {}
    for config_file in config_files:
        file_data = await _load_single_yaml_file(config_file)
        if file_data is not None:
            merged_data.update(file_data)
        elif not config_file.exists():
            logger.debug(f"Configuration file not found: {config_file}")
    return merged_data


async def _load_single_yaml_file(config_file: Path) -> dict[str, t.Any] | None:
    """Load a single YAML file and return its content."""
    if not config_file.exists():
        return None

    try:
        with config_file.open() as f:
            loaded_data: t.Any = yaml.safe_load(f)
            if isinstance(loaded_data, dict):
                logger.debug(f"Loaded configuration from {config_file}")
                return loaded_data
            else:
                logger.warning(
                    f"Invalid YAML format in {config_file}: expected dict, got {type(loaded_data).__name__}"
                )
                return {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML from {config_file}: {e}")
        return None
    except OSError as e:
        logger.error(f"Failed to read {config_file}: {e}")
        return None


def _filter_relevant_data[T: Settings](
    merged_data: dict[str, t.Any], settings_class: type[T]
) -> dict[str, t.Any]:
    """Filter the loaded data to only fields defined in the Settings class."""
    return {k: v for k, v in merged_data.items() if k in settings_class.model_fields}


def _log_filtered_fields(
    merged_data: dict[str, t.Any], relevant_data: dict[str, t.Any]
) -> None:
    """Log any fields that were excluded due to not being in the settings class."""
    excluded_fields = set(merged_data.keys()) - set(relevant_data.keys())
    if excluded_fields:
        logger.debug(
            f"Ignored unknown configuration fields: {', '.join(sorted(excluded_fields))}"
        )


def _log_load_info[T: Settings](
    settings_class: type[T], relevant_data: dict[str, t.Any]
) -> None:
    """Log information about the loaded configuration."""
    logger.info(
        f"Loaded {len(relevant_data)} configuration values for {settings_class.__name__} (async)"
    )
