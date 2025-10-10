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
from pathlib import Path
from typing import TypeVar

import yaml
from acb.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Settings)


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

    # Merge YAML data from all files
    merged_data = {}
    for config_file in config_files:
        if config_file.exists():
            try:
                with open(config_file) as f:
                    file_data = yaml.safe_load(f) or {}
                    if not isinstance(file_data, dict):
                        logger.warning(
                            f"Invalid YAML format in {config_file}: expected dict, got {type(file_data).__name__}"
                        )
                        continue
                    merged_data.update(file_data)
                    logger.debug(f"Loaded configuration from {config_file}")
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse YAML from {config_file}: {e}")
                # Continue with other files even if one fails
                continue
            except OSError as e:
                logger.error(f"Failed to read {config_file}: {e}")
                continue
        else:
            logger.debug(f"Configuration file not found: {config_file}")

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

    # Merge YAML data from all files
    merged_data = {}
    for config_file in config_files:
        if config_file.exists():
            try:
                with open(config_file) as f:
                    file_data = yaml.safe_load(f) or {}
                    if not isinstance(file_data, dict):
                        logger.warning(
                            f"Invalid YAML format in {config_file}: expected dict, got {type(file_data).__name__}"
                        )
                        continue
                    merged_data.update(file_data)
                    logger.debug(f"Loaded configuration from {config_file}")
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse YAML from {config_file}: {e}")
                continue
            except OSError as e:
                logger.error(f"Failed to read {config_file}: {e}")
                continue
        else:
            logger.debug(f"Configuration file not found: {config_file}")

    # Filter to only fields defined in the Settings class
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
        f"Loaded {len(relevant_data)} configuration values for {settings_class.__name__} (async)"
    )

    # Async initialization (loads secrets, performs async setup)
    return await settings_class.create_async(**relevant_data)
