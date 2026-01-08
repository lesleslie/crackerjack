from __future__ import annotations

import logging
import typing as t
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseSettings)


def _load_single_config_file(config_file: Path) -> dict[str, t.Any]:
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
    merged_data = {}
    for config_file in config_files:
        file_data = _load_single_config_file(config_file)
        merged_data.update(file_data)
    return merged_data


def _extract_adapter_timeouts(crackerjack_config: dict[str, t.Any]) -> None:
    adapter_timeouts_data: dict[str, t.Any] = {}

    for key, value in list(crackerjack_config.items()):
        if key.endswith("_timeout"):
            adapter_timeouts_data[key] = value

            del crackerjack_config[key]

    if adapter_timeouts_data:
        crackerjack_config["adapter_timeouts"] = adapter_timeouts_data


def _load_pyproject_toml(settings_dir: Path) -> dict[str, t.Any]:
    pyproject_path = settings_dir.parent / "pyproject.toml"

    if not pyproject_path.exists():
        logger.debug(f"pyproject.toml not found at {pyproject_path}")
        return {}

    try:
        import tomllib

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)

        crackerjack_config = data.get("tool", {}).get("crackerjack", {})

        if crackerjack_config:
            logger.debug("Loaded configuration from pyproject.toml")
            _extract_adapter_timeouts(crackerjack_config)

        return crackerjack_config

    except ImportError:
        try:
            import tomli

            with pyproject_path.open("rb") as f:
                data = tomli.load(f)

            crackerjack_config = data.get("tool", {}).get("crackerjack", {})

            if crackerjack_config:
                logger.debug("Loaded configuration from pyproject.toml (via tomli)")
                _extract_adapter_timeouts(crackerjack_config)

            return crackerjack_config

        except ImportError:
            logger.warning(
                "Neither tomllib nor tomli available for pyproject.toml parsing"
            )
            return {}
    except Exception as e:
        logger.error(f"Failed to parse pyproject.toml: {e}")
        return {}


def load_settings[T: BaseSettings](
    settings_class: type[T],
    settings_dir: Path | None = None,
) -> T:
    if settings_dir is None:
        settings_dir = Path.cwd() / "settings"

    config_files = [
        settings_dir / "crackerjack.yaml",
        settings_dir / "local.yaml",
    ]

    merged_data = _merge_config_data(config_files)

    pyproject_data = _load_pyproject_toml(settings_dir)
    merged_data.update(pyproject_data)

    relevant_data = {
        k: v for k, v in merged_data.items() if k in settings_class.model_fields
    }

    excluded_fields = set(merged_data.keys()) - set(relevant_data.keys())
    if excluded_fields:
        logger.debug(
            f"Ignored unknown configuration fields: {', '.join(sorted(excluded_fields))}"
        )

    logger.debug(
        f"Loaded {len(relevant_data)} configuration values for {settings_class.__name__}"
    )

    return settings_class(**relevant_data)


async def load_settings_async[T: BaseSettings](
    settings_class: type[T],
    settings_dir: Path | None = None,
) -> T:
    if settings_dir is None:
        settings_dir = Path.cwd() / "settings"

    config_files = [
        settings_dir / "crackerjack.yaml",
        settings_dir / "local.yaml",
    ]

    merged_data = await _load_yaml_data(config_files)

    pyproject_data = _load_pyproject_toml(settings_dir)
    merged_data.update(pyproject_data)

    relevant_data = _filter_relevant_data(merged_data, settings_class)
    _log_filtered_fields(merged_data, relevant_data)
    _log_load_info(settings_class, relevant_data)

    return settings_class(**relevant_data)


async def _load_yaml_data(config_files: list[Path]) -> dict[str, t.Any]:
    merged_data: dict[str, t.Any] = {}
    for config_file in config_files:
        file_data = await _load_single_yaml_file(config_file)
        if file_data is not None:
            merged_data.update(file_data)
        elif not config_file.exists():
            logger.debug(f"Configuration file not found: {config_file}")
    return merged_data


async def _load_single_yaml_file(config_file: Path) -> dict[str, t.Any] | None:
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


def _filter_relevant_data[T: BaseSettings](
    merged_data: dict[str, t.Any], settings_class: type[T]
) -> dict[str, t.Any]:
    return {k: v for k, v in merged_data.items() if k in settings_class.model_fields}


def _log_filtered_fields(
    merged_data: dict[str, t.Any], relevant_data: dict[str, t.Any]
) -> None:
    excluded_fields = set(merged_data.keys()) - set(relevant_data.keys())
    if excluded_fields:
        logger.debug(
            f"Ignored unknown configuration fields: {', '.join(sorted(excluded_fields))}"
        )


def _log_load_info[T: BaseSettings](
    settings_class: type[T], relevant_data: dict[str, t.Any]
) -> None:
    logger.debug(
        f"Loaded {len(relevant_data)} configuration values for {settings_class.__name__} (async)"
    )
