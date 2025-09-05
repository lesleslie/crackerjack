import os
import typing as t
from contextlib import suppress
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from rich.console import Console

from crackerjack.errors import ValidationError
from crackerjack.models.protocols import OptionsProtocol
from crackerjack.services.logging import LoggingContext, get_logger


class CrackerjackConfig(BaseModel):
    package_path: Path = Field(default_factory=Path.cwd)
    cache_enabled: bool = True
    cache_size: int = 1000
    cache_ttl: float = 300.0

    hook_batch_size: int = 10
    hook_timeout: int = 300
    max_concurrent_hooks: int = 4
    enable_async_hooks: bool = True

    test_timeout: int = 300
    test_workers: int = Field(default_factory=lambda: os.cpu_count() or 1)
    min_coverage: float = 10.0

    log_level: str = "INFO"
    log_json: bool = False
    log_file: Path | None = None
    enable_correlation_ids: bool = True

    autofix: bool = True
    skip_hooks: bool = False
    experimental_hooks: bool = False

    # Removed unused configuration fields: performance_tracking, benchmark_mode, publish_enabled, keyring_provider

    batch_file_operations: bool = True
    file_operation_batch_size: int = 10

    precommit_mode: str = "comprehensive"

    @field_validator("package_path", mode="before")
    @classmethod
    def validate_package_path(cls, v: Any) -> Path:
        if isinstance(v, str):
            v = Path(v)
        return v.resolve()

    @field_validator("log_file", mode="before")
    @classmethod
    def validate_log_file(cls, v: Any) -> Path | None:
        if v is None:
            return v
        if isinstance(v, str):
            v = Path(v)
        return v

    @field_validator("test_workers")
    @classmethod
    def validate_test_workers(cls, v: int) -> int:
        return max(1, min(v, 16))

    @field_validator("min_coverage")
    @classmethod
    def validate_min_coverage(cls, v: float) -> float:
        return max(0.0, min(v, 100.0))

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            msg = f"Invalid log level: {v}. Must be one of {valid_levels}"
            raise ValueError(msg)
        return v.upper()

    class Config:
        extra = "allow"

        use_enum_values = True


class ConfigSource:
    def __init__(self, priority: int = 0) -> None:
        self.priority = priority
        self.logger = get_logger("crackerjack.config.source")

    def load(self) -> dict[str, t.Any]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


class EnvironmentConfigSource(ConfigSource):
    ENV_PREFIX = "CRACKERJACK_"

    def __init__(self, priority: int = 100) -> None:
        super().__init__(priority)

    def load(self) -> dict[str, t.Any]:
        config: dict[str, t.Any] = {}

        for key, value in os.environ.items():
            if key.startswith(self.ENV_PREFIX):
                config_key = key[len(self.ENV_PREFIX) :].lower()

                config[config_key] = self._convert_value(value)

        return config

    def _convert_value(self, value: str) -> t.Any:
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off"):
            return False

        # Handle negative numbers with spaces (e.g., "- 10")
        cleaned_value = value.replace(" ", "")

        with suppress(ValueError):
            return int(cleaned_value)

        with suppress(ValueError):
            return float(cleaned_value)

        return value


class FileConfigSource(ConfigSource):
    def __init__(self, config_path: Path, priority: int = 50) -> None:
        super().__init__(priority)
        self.config_path = config_path

    def is_available(self) -> bool:
        return self.config_path.exists() and self.config_path.is_file()

    def load(self) -> dict[str, t.Any]:
        if not self.is_available():
            return {}

        try:
            with self.config_path.open("r") as f:
                if self.config_path.suffix in (".yaml", ".yml"):
                    import yaml

                    result = yaml.safe_load(f)
                    return result if isinstance(result, dict) else {}
                elif self.config_path.suffix == ".json":
                    import json

                    result = json.load(f)
                    return result if isinstance(result, dict) else {}
                else:
                    self.logger.warning(
                        f"Unsupported config file format: {self.config_path.suffix}"
                    )
                    return {}
        except Exception as e:
            self.logger.exception(
                f"Failed to load config from file: {self.config_path}",
                error=str(e),
            )
            return {}


class PyprojectConfigSource(ConfigSource):
    def __init__(self, pyproject_path: Path, priority: int = 25) -> None:
        super().__init__(priority)
        self.pyproject_path = pyproject_path

    def is_available(self) -> bool:
        return self.pyproject_path.exists() and self.pyproject_path.is_file()

    def load(self) -> dict[str, t.Any]:
        if not self.is_available():
            return {}

        try:
            import tomllib

            with self.pyproject_path.open("rb") as f:
                pyproject_data = tomllib.load(f)

            config = pyproject_data.get("tool", {}).get("crackerjack", {})

            self.logger.debug("Loaded pyproject config", keys=list(config.keys()))
            return config

        except ImportError:
            try:
                import tomllib

                with self.pyproject_path.open("rb") as f:
                    pyproject_data = tomllib.load(f)
                config = pyproject_data.get("tool", {}).get("crackerjack", {})
                self.logger.debug("Loaded pyproject config", keys=list(config.keys()))
                return config
            except ImportError:
                self.logger.warning(
                    "No TOML library available for pyproject.toml parsing",
                )
                return {}
        except Exception as e:
            self.logger.exception("Failed to load pyproject.toml", error=str(e))
            return {}


class OptionsConfigSource(ConfigSource):
    def __init__(self, options: OptionsProtocol, priority: int = 200) -> None:
        super().__init__(priority)
        self.options = options

    def load(self) -> dict[str, t.Any]:
        config: dict[str, t.Any] = {}

        option_mappings = {
            "testing": "test_mode",
            "autofix": "autofix",
            "skip_hooks": "skip_hooks",
            "experimental_hooks": "experimental_hooks",
            "test_timeout": "test_timeout",
            "test_workers": "test_workers",
            "benchmark": "benchmark_mode",
            "publish": "publish_enabled",
            "log_level": "log_level",
        }

        for option_attr, config_key in option_mappings.items():
            if hasattr(self.options, option_attr):
                value = getattr(self.options, option_attr)
                if value is not None:
                    config[config_key] = value

        self.logger.debug("Loaded options config", keys=list(config.keys()))
        return config


class UnifiedConfigurationService:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        options: OptionsProtocol | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.logger = get_logger("crackerjack.config.unified")

        self.sources: list[ConfigSource] = []

        pyproject_path = pkg_path / "pyproject.toml"
        self.sources.extend(
            (
                self._create_default_source(),
                PyprojectConfigSource(pyproject_path),
            ),
        )

        self.sources.append(EnvironmentConfigSource())

        if options:
            self.sources.append(OptionsConfigSource(options))

        self._config: CrackerjackConfig | None = None

    def _create_default_source(self) -> ConfigSource:
        pkg_path = self.pkg_path

        class DefaultConfigSource(ConfigSource):
            def load(self) -> dict[str, t.Any]:
                return {
                    "package_path": pkg_path,
                    "cache_enabled": True,
                    "autofix": True,
                    "log_level": "INFO",
                }

        return DefaultConfigSource(priority=0)

    def get_config(self, reload: bool = False) -> CrackerjackConfig:
        if self._config is None or reload:
            with LoggingContext("load_unified_config", source_count=len(self.sources)):
                self._config = self._load_unified_config()

        return self._config

    def _load_unified_config(self) -> CrackerjackConfig:
        merged_config: dict[str, Any] = {}

        sorted_sources = sorted(self.sources, key=lambda s: s.priority)

        for source in sorted_sources:
            if source.is_available():
                try:
                    source_config = source.load()
                    if source_config:
                        merged_config.update(source_config)
                        self.logger.debug(
                            "Merged config from source",
                            source_type=type(source).__name__,
                            priority=source.priority,
                            keys=list(source_config.keys()),
                        )
                except Exception as e:
                    self.logger.exception(
                        "Failed to load config from source",
                        source_type=type(source).__name__,
                        error=str(e),
                    )

        try:
            config = CrackerjackConfig(**merged_config)

            self.logger.info(
                "Unified configuration loaded",
                package_path=str(config.package_path),
                cache_enabled=config.cache_enabled,
                autofix=config.autofix,
                async_hooks=config.enable_async_hooks,
                test_workers=config.test_workers,
                log_level=config.log_level,
            )

            return config

        except Exception as e:
            self.logger.exception("Configuration validation failed", error=str(e))
            raise ValidationError(
                message="Invalid configuration",
                details=str(e),
                recovery="Check configuration files and environment variables",
            ) from e

    def get_precommit_config_mode(self) -> str:
        config = self.get_config()

        if config.experimental_hooks:
            return "experimental"
        if hasattr(config, "test") and getattr(config, "test", False):
            return "comprehensive"
        return config.precommit_mode

    def get_logging_config(self) -> dict[str, Any]:
        config = self.get_config()

        return {
            "level": config.log_level,
            "json_output": config.log_json,
            "log_file": config.log_file,
            "enable_correlation_ids": config.enable_correlation_ids,
        }

    def get_hook_execution_config(self) -> dict[str, Any]:
        config = self.get_config()

        return {
            "batch_size": config.hook_batch_size,
            "timeout": config.hook_timeout,
            "max_concurrent": config.max_concurrent_hooks,
            "enable_async": config.enable_async_hooks,
            "autofix": config.autofix,
            "skip_hooks": config.skip_hooks,
        }

    def get_testing_config(self) -> dict[str, Any]:
        config = self.get_config()

        return {
            "timeout": config.test_timeout,
            "workers": config.test_workers,
            "min_coverage": config.min_coverage,
        }

    def get_cache_config(self) -> dict[str, Any]:
        config = self.get_config()

        return {
            "enabled": config.cache_enabled,
            "size": config.cache_size,
            "ttl": config.cache_ttl,
            "batch_operations": config.batch_file_operations,
            "batch_size": config.file_operation_batch_size,
        }

    def validate_current_config(self) -> bool:
        try:
            config = self.get_config()

            validation_errors: list[str] = []

            if config.test_workers <= 0:
                validation_errors.append("test_workers must be positive")

            if config.min_coverage < 0 or config.min_coverage > 100:
                validation_errors.append("min_coverage must be between 0 and 100")

            if config.cache_size <= 0:
                validation_errors.append("cache_size must be positive")

            if validation_errors:
                for error in validation_errors:
                    self.logger.error("Configuration validation error", error=error)
                return False

            self.logger.info("Configuration validation passed")
            return True

        except Exception as e:
            self.logger.exception("Configuration validation failed", error=str(e))
            return False
