"""Config parser strategies for different file formats.

This module implements the Strategy Pattern for configuration file parsing,
eliminating the Open/Closed Principle violation where adding new formats
required modifying the ConfigService class.

New formats can be added by:
1. Implementing the ConfigParser protocol
2. Registering with ConfigParserRegistry
3. No changes to ConfigService required

Usage:
    >>> parser = ConfigParserRegistry.get_parser("yaml")
    >>> config = parser.load(Path("config.yaml"))
    >>> parser.save(config, Path("output.yaml"))
"""

import abc
import json
import logging
import typing as t
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class ConfigParser(t.Protocol):
    """Protocol for configuration file parsers.

    All config parsers must implement load() and save() methods.
    This enables the Strategy Pattern for config file handling.
    """

    def load(self, path: Path) -> dict[str, t.Any]:
        """Load configuration from file.

        Args:
            path: Path to config file

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        ...

    def save(self, config: dict[str, t.Any], path: Path) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary
            path: Path to save config file

        Raises:
            ValueError: If config cannot be serialized
        """
        ...

    @property
    def extensions(self) -> list[str]:
        """List of supported file extensions.

        Returns:
            List of extensions (e.g., [".yaml", ".yml"])
        """
        ...


class JSONParser:
    """JSON configuration file parser."""

    @property
    def extensions(self) -> list[str]:
        return [".json"]

    def load(self, path: Path) -> dict[str, t.Any]:
        """Load JSON config file."""
        if not path.exists():
            msg = f"Configuration file does not exist: {path}"
            raise FileNotFoundError(msg)

        try:
            with path.open(encoding="utf-8") as f:
                return t.cast(dict[str, t.Any], json.load(f))
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in {path}: {e}"
            raise ValueError(msg) from e

    def save(self, config: dict[str, t.Any], path: Path) -> None:
        """Save config as JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)


class YAMLParser:
    """YAML configuration file parser."""

    @property
    def extensions(self) -> list[str]:
        return [".yml", ".yaml"]

    def load(self, path: Path) -> dict[str, t.Any]:
        """Load YAML config file."""
        if not path.exists():
            msg = f"Configuration file does not exist: {path}"
            raise FileNotFoundError(msg)

        try:
            with path.open(encoding="utf-8") as f:
                return t.cast(dict[str, t.Any], yaml.safe_load(f))
        except yaml.YAMLError as e:
            msg = f"Invalid YAML in {path}: {e}"
            raise ValueError(msg) from e

    def save(self, config: dict[str, t.Any], path: Path) -> None:
        """Save config as YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


class TOMLParser:
    """TOML configuration file parser."""

    @property
    def extensions(self) -> list[str]:
        return [".toml"]

    def load(self, path: Path) -> dict[str, t.Any]:
        """Load TOML config file."""
        if not path.exists():
            msg = f"Configuration file does not exist: {path}"
            raise FileNotFoundError(msg)

        try:
            content = path.read_text(encoding="utf-8")
            return self._load_toml_from_text(content)
        except Exception as e:
            msg = f"Invalid TOML in {path}: {e}"
            raise ValueError(msg) from e

    def save(self, config: dict[str, t.Any], path: Path) -> None:
        """Save config as TOML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        toml_content = self._dump_toml(config)
        path.write_text(toml_content, encoding="utf-8")

    @staticmethod
    def _load_toml_from_text(content: str) -> dict[str, t.Any]:
        """Load TOML from text string."""
        try:
            import tomllib
        except ImportError:
            tomllib = None  # type: ignore[assignment]

        if tomllib is not None:
            return t.cast(dict[str, t.Any], tomllib.loads(content))

        import toml

        return t.cast(dict[str, t.Any], toml.loads(content))

    @staticmethod
    def _dump_toml(config: dict[str, t.Any]) -> str:
        """Dump config to TOML string."""
        try:
            import toml
        except ImportError:
            msg = "TOML save requires 'toml' package (tomllib is read-only)"
            raise ImportError(msg) from None

        return t.cast(str, toml.dumps(config))


class ConfigParserRegistry:
    """Registry for config parsers with self-registration capability.

    This implements the Open/Closed Principle by allowing parsers to
    register themselves without requiring modification of core code.

    Usage:
        # Parsers self-register on module import
        ConfigParserRegistry.register(JSONParser())
        ConfigParserRegistry.register(YAMLParser())

        # Get parser by file extension
        parser = ConfigParserRegistry.get_parser("config.yaml")
        config = parser.load(Path("config.yaml"))
    """

    _parsers: dict[str, ConfigParser] = {}

    @classmethod
    def register(cls, parser: ConfigParser) -> None:
        """Register a config parser for all its extensions.

        Args:
            parser: Parser instance to register

        Example:
            >>> ConfigParserRegistry.register(YAMLParser())
        """
        for ext in parser.extensions:
            normalized_ext = ext.lower().lstrip(".")
            if normalized_ext in cls._parsers:
                logger.debug(f"Parser for {normalized_ext} already registered, skipping")
                continue
            cls._parsers[normalized_ext] = parser
            logger.debug(f"Registered config parser for: {normalized_ext}")

    @classmethod
    def get_parser(cls, path: Path | str) -> ConfigParser:
        """Get parser for given config file path.

        Args:
            path: Path to config file

        Returns:
            Config parser for this file type

        Raises:
            ValueError: If file extension not supported
        """
        path = Path(path)
        ext = path.suffix.lower().lstrip(".")

        if ext not in cls._parsers:
            supported = ", ".join(sorted(cls._parsers.keys()))
            raise ValueError(
                f"Unsupported config format: {ext}. Supported: {supported}"
            )

        return cls._parsers[ext]

    @classmethod
    def get_parser_by_format(cls, format: str) -> ConfigParser:
        """Get parser by format name.

        Args:
            format: Format name (e.g., "yaml", "json", "toml")

        Returns:
            Config parser for this format

        Raises:
            ValueError: If format not supported
        """
        format = format.lower()
        if format not in cls._parsers:
            supported = ", ".join(sorted(cls._parsers.keys()))
            raise ValueError(
                f"Unsupported config format: {format}. Supported: {supported}"
            )

        return cls._parsers[format]

    @classmethod
    def list_formats(cls) -> list[str]:
        """List all supported config formats.

        Returns:
            Sorted list of format names
        """
        return sorted(cls._parsers.keys())

    @classmethod
    def is_supported(cls, path: Path | str) -> bool:
        """Check if config file format is supported.

        Args:
            path: Path to config file

        Returns:
            True if format is supported, False otherwise
        """
        path = Path(path)
        ext = path.suffix.lower().lstrip(".")
        return ext in cls._parsers


# Register built-in parsers on module import
ConfigParserRegistry.register(JSONParser())
ConfigParserRegistry.register(YAMLParser())
ConfigParserRegistry.register(TOMLParser())


__all__ = [
    "ConfigParser",
    "ConfigParserRegistry",
    "JSONParser",
    "YAMLParser",
    "TOMLParser",
]
