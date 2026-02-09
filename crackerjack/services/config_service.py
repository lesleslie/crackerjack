from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, ValidationError

from crackerjack.services.config_parsers import ConfigParserRegistry


class ConfigService:
    @staticmethod
    def load_config(path: str | Path) -> dict[str, Any]:
        path = Path(path)

        if not path.exists():
            msg = f"Configuration file does not exist: {path}"
            raise FileNotFoundError(msg)

        parser = ConfigParserRegistry.get_parser(path)
        return parser.load(path)

    @staticmethod
    async def load_config_async(path: str | Path) -> dict[str, Any]:
        from crackerjack.services.file_io_service import FileIOService

        path = Path(path)

        if not path.exists():
            msg = f"Configuration file does not exist: {path}"
            raise FileNotFoundError(msg)

        content = await FileIOService.read_text_file(path)

        parser = ConfigParserRegistry.get_parser(path)

        import tempfile

        # TODO: Implement async parsing in parsers
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=path.suffix, delete=False
        ) as f:
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
        path = Path(path)
        format_name = format or path.suffix.lower().lstrip(".")

        parser = ConfigParserRegistry.get_parser_by_format(format_name)
        parser.save(config, path)

    @staticmethod
    def merge_configs(
        base_config: dict[str, Any],
        override_config: dict[str, Any],
    ) -> dict[str, Any]:
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
