import json
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, ValidationError

from crackerjack.services.config_parsers import ConfigParserRegistry


class ConfigService:
    @staticmethod
    def load_config(path: str | Path) -> dict[str, Any]:
        """Load configuration from file (format auto-detected from extension).

        This uses the ConfigParserRegistry to select the appropriate parser,
        eliminating the need for if-chains and making the system open for
        extension (new formats can be added without modifying this method).

        Args:
            path: Path to config file (extension determines format)

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
        """
        path = Path(path)

        if not path.exists():
            msg = f"Configuration file does not exist: {path}"
            raise FileNotFoundError(msg)

        parser = ConfigParserRegistry.get_parser(path)
        return parser.load(path)

    @staticmethod
    async def load_config_async(path: str | Path) -> dict[str, Any]:
        """Load configuration from file asynchronously (format auto-detected).

        This uses the ConfigParserRegistry to select the appropriate parser.
        For async loading, we read the file content first, then parse it.

        Args:
            path: Path to config file (extension determines format)

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
        """
        from crackerjack.services.file_io_service import FileIOService

        path = Path(path)

        if not path.exists():
            msg = f"Configuration file does not exist: {path}"
            raise FileNotFoundError(msg)

        # Read file content asynchronously
        content = await FileIOService.read_text_file(path)

        # Parse content synchronously (parsers are not async)
        parser = ConfigParserRegistry.get_parser(path)

        # For YAML/JSON/TOML, we can parse from string
        # This is a simplified approach - for true async we'd need async parsers
        import tempfile

        # Write to temp file and use parser (not ideal but works)
        # TODO: Implement async parsing in parsers
        with tempfile.NamedTemporaryFile(mode="w", suffix=path.suffix, delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            return parser.load(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def validate_config(
        config: dict[str, Any],
        model_class: type[BaseModel],
    ) -> BaseModel:
        """Validate config against Pydantic model.

        Args:
            config: Configuration dictionary
            model_class: Pydantic model class

        Returns:
            Validated model instance

        Raises:
            ValidationError: If config doesn't match model schema
        """
        try:
            return model_class.model_validate(config)
        except ValidationError as e:
            logger.error(f"Config validation failed: {e}")
            raise

    @staticmethod
    def save_config(
        config: dict[str, Any],
        path: str | Path,
        format: str | None = None,
    ) -> None:
        """Save configuration to file (format auto-detected or specified).

        This uses the ConfigParserRegistry to select the appropriate parser,
        eliminating if-chains and making the system open for extension.

        Args:
            config: Configuration dictionary
            path: Path to save config file
            format: Optional format override (auto-detected from path if None)

        Raises:
            ValueError: If file format is not supported
        """
        path = Path(path)
        format_name = format or path.suffix.lower().lstrip(".")

        parser = ConfigParserRegistry.get_parser_by_format(format_name)
        parser.save(config, path)

    @staticmethod
    def merge_configs(
        base_config: dict[str, Any],
        override_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Deep merge two configuration dictionaries.

        Args:
            base_config: Base configuration
            override_config: Override configuration (takes precedence)

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
