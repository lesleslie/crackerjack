import logging
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.config import load_settings
from crackerjack.config.settings import CrackerjackSettings
from crackerjack.errors import ValidationError
from crackerjack.models.protocols import OptionsProtocol


class UnifiedConfigurationService:
    def __init__(
        self,
        pkg_path: Path,
        options: OptionsProtocol | None = None,
    ) -> None:
        self.console = Console()
        self.pkg_path = pkg_path
        self.logger = logging.getLogger(__name__)
        self._config: CrackerjackSettings | None = None

    def get_config(self, reload: bool = False) -> CrackerjackSettings:
        if self._config is None or reload:
            self._config = self._load_unified_config()

        return self._config

    def _load_unified_config(self) -> CrackerjackSettings:
        try:
            settings = load_settings(CrackerjackSettings)
            self.logger.info("Unified configuration loaded")
            return settings
        except Exception as e:
            self.logger.exception("Configuration validation failed", error=str(e))
            raise ValidationError(
                message="Invalid configuration",
                details=str(e),
                recovery="Check configuration files and environment variables",
            ) from e

    def get_logging_config(self) -> dict[str, t.Any]:
        self.get_config()

        return {
            "level": "INFO",
            "json_output": False,
            "log_file": None,
            "enable_correlation_ids": True,
        }

    def get_hook_execution_config(self) -> dict[str, t.Any]:
        config = self.get_config()

        return {
            "batch_size": 10,
            "timeout": 300,
            "max_concurrent": 4,
            "enable_async": True,
            "autofix": config.ai.autofix,
            "skip_hooks": config.hooks.skip_hooks,
        }

    def get_testing_config(self) -> dict[str, t.Any]:
        config = self.get_config()

        return {
            "timeout": config.testing.test_timeout,
            "workers": config.testing.test_workers,
            "min_coverage": 10.0,
        }

    @staticmethod
    def get_cache_config() -> dict[str, t.Any]:
        return {
            "enabled": True,
            "size": 1000,
            "ttl": 300.0,
            "batch_operations": True,
            "batch_size": 10,
        }

    def validate_current_config(self) -> bool:
        try:
            config = self.get_config()

            validation_errors: list[str] = []

            if config.testing.test_workers <= 0:
                validation_errors.append("test_workers must be positive")

            if validation_errors:
                for error in validation_errors:
                    self.logger.error("Configuration validation error", error=error)
                return False

            self.logger.info("Configuration validation passed")
            return True

        except Exception as e:
            self.logger.exception("Configuration validation failed", error=str(e))
            return False
