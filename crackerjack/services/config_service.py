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
            import toml

            return toml.loads(content)
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
        import toml

        with path.open("r", encoding="utf-8") as f:
            return toml.load(f)

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
        import toml

        with path.open("w", encoding="utf-8") as f:
            toml.dump(config, f)

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
