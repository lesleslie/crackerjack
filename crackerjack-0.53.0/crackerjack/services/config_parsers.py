import json
import logging
import typing as t
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class ConfigParser(t.Protocol):
    def load(self, path: Path) -> dict[str, t.Any]: ...

    def save(self, config: dict[str, t.Any], path: Path) -> None: ...

    @property
    def extensions(self) -> list[str]: ...


class JSONParser:
    @property
    def extensions(self) -> list[str]:
        return [".json"]

    def load(self, path: Path) -> dict[str, t.Any]:
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
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)


class YAMLParser:
    @property
    def extensions(self) -> list[str]:
        return [".yml", ".yaml"]

    def load(self, path: Path) -> dict[str, t.Any]:
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
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


class TOMLParser:
    @property
    def extensions(self) -> list[str]:
        return [".toml"]

    def load(self, path: Path) -> dict[str, t.Any]:
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
        path.parent.mkdir(parents=True, exist_ok=True)
        toml_content = self._dump_toml(config)
        path.write_text(toml_content, encoding="utf-8")

    @staticmethod
    def _load_toml_from_text(content: str) -> dict[str, t.Any]:
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
        try:
            import toml
        except ImportError:
            msg = "TOML save requires 'toml' package (tomllib is read-only)"
            raise ImportError(msg) from None

        return t.cast(str, toml.dumps(config))


class ConfigParserRegistry:
    _parsers: dict[str, ConfigParser] = {}

    @classmethod
    def register(cls, parser: ConfigParser) -> None:
        for ext in parser.extensions:
            normalized_ext = ext.lower().lstrip(".")
            if normalized_ext in cls._parsers:
                logger.debug(
                    f"Parser for {normalized_ext} already registered, skipping"
                )
                continue
            cls._parsers[normalized_ext] = parser
            logger.debug(f"Registered config parser for: {normalized_ext}")

    @classmethod
    def get_parser(cls, path: Path | str) -> ConfigParser:
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
        format = format.lower()
        if format not in cls._parsers:
            supported = ", ".join(sorted(cls._parsers.keys()))
            raise ValueError(
                f"Unsupported config format: {format}. Supported: {supported}"
            )

        return cls._parsers[format]

    @classmethod
    def list_formats(cls) -> list[str]:
        return sorted(cls._parsers.keys())

    @classmethod
    def is_supported(cls, path: Path | str) -> bool:
        path = Path(path)
        ext = path.suffix.lower().lstrip(".")
        return ext in cls._parsers


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
