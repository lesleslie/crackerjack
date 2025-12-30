"""Generic configuration loading and validation service."""

import json
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, ValidationError


class ConfigService:
    """Generic configuration loading and validation service."""

    @staticmethod
    def load_config(path: str | Path) -> dict[str, Any]:
        """
        Load configuration file based on extension.

        Args:
            path: Path to the configuration file

        Returns:
            Dictionary with configuration data

        Raises:
            ValueError: If file extension is not supported
            FileNotFoundError: If the file doesn't exist
            Exception: For other file loading errors
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file does not exist: {path}")

        if path.suffix.lower() == ".json":
            return ConfigService._load_json(path)
        elif path.suffix.lower() in (".yml", ".yaml"):
            return ConfigService._load_yaml(path)
        elif path.suffix.lower() == ".toml":
            return ConfigService._load_toml(path)
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")

    @staticmethod
    async def load_config_async(path: str | Path) -> dict[str, Any]:
        """
        Asynchronously load configuration file based on extension.

        Args:
            path: Path to the configuration file

        Returns:
            Dictionary with configuration data

        Raises:
            ValueError: If file extension is not supported
            FileNotFoundError: If the file doesn't exist
            Exception: For other file loading errors
        """
        from crackerjack.services.file_io_service import FileIOService

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file does not exist: {path}")

        if path.suffix.lower() == ".json":
            content = await FileIOService.read_text_file(path)
            return json.loads(content)
        elif path.suffix.lower() in (".yml", ".yaml"):
            content = await FileIOService.read_text_file(path)
            return yaml.safe_load(content)
        elif path.suffix.lower() == ".toml":
            content = await FileIOService.read_text_file(path)
            return _load_toml_from_text(content)
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        """Load JSON configuration."""
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """Load YAML configuration."""
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _load_toml(path: Path) -> dict[str, Any]:
        """Load TOML configuration."""
        with path.open("r", encoding="utf-8") as f:
            return _load_toml_from_text(f.read())

    @staticmethod
    def validate_config(
        config: dict[str, Any], model_class: type[BaseModel]
    ) -> BaseModel:
        """
        Validate configuration against a Pydantic model.

        Args:
            config: Configuration dictionary to validate
            model_class: Pydantic model class to validate against

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If the configuration doesn't match the model
        """
        try:
            return model_class.model_validate(config)
        except ValidationError as e:
            logger.error(f"Config validation failed: {e}")
            raise

    @staticmethod
    def save_config(
        config: dict[str, Any], path: str | Path, format: str | None = None
    ) -> None:
        """
        Save configuration to file.

        Args:
            config: Configuration dictionary to save
            path: Path to save the configuration to
            format: Format to save as ('json', 'yaml', 'toml'). If None, inferred from path extension.
        """
        path = Path(path)
        format = format or path.suffix.lower().lstrip(".")

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            ConfigService._save_json(config, path)
        elif format in ("yml", "yaml"):
            ConfigService._save_yaml(config, path)
        elif format == "toml":
            ConfigService._save_toml(config, path)
        else:
            raise ValueError(f"Unsupported config format: {format}")

    @staticmethod
    def _save_json(config: dict[str, Any], path: Path) -> None:
        """Save configuration as JSON."""
        with path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _save_yaml(config: dict[str, Any], path: Path) -> None:
        """Save configuration as YAML."""
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def _save_toml(config: dict[str, Any], path: Path) -> None:
        """Save configuration as TOML."""
        with path.open("w", encoding="utf-8") as f:
            f.write(_dump_toml(config))

    @staticmethod
    def merge_configs(
        base_config: dict[str, Any], override_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Recursively merge two configuration dictionaries.

        Args:
            base_config: Base configuration
            override_config: Configuration to merge on top of base

        Returns:
            Merged configuration dictionary
        """
        result = base_config.copy()

        for key, value in override_config.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigService.merge_configs(result[key], value)
            else:
                result[key] = value

        return result


def _load_toml_from_text(content: str) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]

    if tomllib is not None:
        return tomllib.loads(content)

    import toml

    return toml.loads(content)


def _dump_toml(config: dict[str, Any]) -> str:
    try:
        import toml
    except ImportError:
        toml = None  # type: ignore[assignment]

    if toml is not None:
        return toml.dumps(config)

    lines: list[str] = []

    def emit_table(data: dict[str, Any], prefix: list[str]) -> None:
        scalars: list[tuple[str, Any]] = []
        tables: list[tuple[str, dict[str, Any]]] = []
        for key, value in data.items():
            if isinstance(value, dict):
                tables.append((key, value))
            else:
                scalars.append((key, value))

        if prefix:
            lines.append(f"[{'.'.join(prefix)}]")

        for key, value in scalars:
            lines.append(f"{key} = {_format_toml_value(value)}")

        for key, value in tables:
            if lines and lines[-1] != "":
                lines.append("")
            emit_table(value, prefix + [key])

    emit_table(config, [])
    return "\n".join(lines) + "\n"


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    raise ValueError(f"Unsupported TOML value: {value!r}")
