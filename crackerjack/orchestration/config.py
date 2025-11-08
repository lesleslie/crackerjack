from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Self
else:
    Self = "OrchestrationConfig"

import yaml
from acb.depends import depends

from crackerjack.config.settings import CrackerjackSettings


def _bool_from_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_from_env(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class OrchestrationConfig:
    enable_orchestration: bool = True
    orchestration_mode: str = "acb"
    enable_caching: bool = True
    cache_backend: str = "memory"
    cache_ttl: int = 3600
    cache_max_entries: int = 100
    max_parallel_hooks: int = 4
    default_timeout: int = 600
    stop_on_critical_failure: bool = True
    enable_dependency_resolution: bool = True
    log_cache_stats: bool = False
    log_execution_timing: bool = False
    enable_strategy_parallelism: bool = True
    enable_adaptive_execution: bool = True
    max_concurrent_strategies: int = 2
    enable_tool_proxy: bool = True
    use_precommit_legacy: bool = True
    config_file_path: Path | None = field(default=None, repr=False)

    # --------------------------------------------------------------------- #
    # Construction helpers
    # --------------------------------------------------------------------- #

    @classmethod
    def from_settings(
        cls,
        settings: CrackerjackSettings | None = None,
    ) -> OrchestrationConfig:
        """Build configuration from CrackerjackSettings via DI."""
        if settings is None:
            try:
                # Use synchronous DI retrieval to avoid coroutine leakage in tests
                settings = depends.get_sync(CrackerjackSettings)  # type: ignore[attr-defined]
            except Exception:
                settings = None

        if settings is None:
            return cls()

        return cls(
            enable_orchestration=settings.enable_orchestration,
            orchestration_mode=settings.orchestration_mode,
            enable_caching=settings.enable_caching,
            cache_backend=settings.cache_backend,
            cache_ttl=settings.cache_ttl,
            cache_max_entries=settings.cache_max_entries,
            max_parallel_hooks=settings.max_parallel_hooks,
            default_timeout=settings.default_timeout,
            stop_on_critical_failure=settings.stop_on_critical_failure,
            enable_dependency_resolution=settings.enable_dependency_resolution,
            log_cache_stats=settings.log_cache_stats,
            log_execution_timing=settings.log_execution_timing,
            enable_strategy_parallelism=settings.enable_strategy_parallelism,
            enable_adaptive_execution=settings.enable_adaptive_execution,
            max_concurrent_strategies=settings.max_concurrent_strategies,
            enable_tool_proxy=getattr(settings, "enable_tool_proxy", True),
            use_precommit_legacy=settings.use_precommit_legacy,
        )

    @classmethod
    def from_file(cls, config_path: Path) -> OrchestrationConfig:
        if not config_path.exists():
            msg = f"Config file not found: {config_path}"
            raise FileNotFoundError(msg)

        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        except yaml.YAMLError as exc:
            msg = f"Invalid YAML in {config_path}: {exc}"
            raise ValueError(msg) from exc

        if not isinstance(data, dict):
            msg = f"Invalid config structure in {config_path}"
            raise ValueError(msg)

        section_any = data.get("orchestration", {})
        section: dict[str, Any] = section_any if isinstance(section_any, dict) else {}

        config = cls()
        config.config_file_path = config_path
        config._apply_dict(section)
        return config

    @classmethod
    def _env_overrides(cls) -> dict[str, Any]:
        """Return environment variable overrides."""
        env = os.environ
        overrides: dict[str, Any] = {}

        mapping: dict[str, str] = {
            "CRACKERJACK_ORCHESTRATION_MODE": "orchestration_mode",
            "CRACKERJACK_CACHE_BACKEND": "cache_backend",
        }

        for env_key, attr in mapping.items():
            if env_key in env:
                overrides[attr] = env[env_key]

        bool_vars = {
            "CRACKERJACK_ENABLE_ORCHESTRATION": "enable_orchestration",
            "CRACKERJACK_ENABLE_CACHING": "enable_caching",
            "CRACKERJACK_STOP_ON_CRITICAL_FAILURE": "stop_on_critical_failure",
            "CRACKERJACK_ENABLE_DEPENDENCY_RESOLUTION": "enable_dependency_resolution",
            "CRACKERJACK_LOG_CACHE_STATS": "log_cache_stats",
            "CRACKERJACK_LOG_EXECUTION_TIMING": "log_execution_timing",
            "CRACKERJACK_ENABLE_STRATEGY_PARALLELISM": "enable_strategy_parallelism",
            "CRACKERJACK_ENABLE_ADAPTIVE_EXECUTION": "enable_adaptive_execution",
            "CRACKERJACK_ENABLE_TOOL_PROXY": "enable_tool_proxy",
            "CRACKERJACK_USE_PRECOMMIT_LEGACY": "use_precommit_legacy",
        }

        for env_key, attr in bool_vars.items():
            if env_key in env:
                overrides[attr] = _bool_from_env(env[env_key])

        int_vars = {
            "CRACKERJACK_CACHE_TTL": ("cache_ttl", 3600),
            "CRACKERJACK_CACHE_MAX_ENTRIES": ("cache_max_entries", 100),
            "CRACKERJACK_MAX_PARALLEL_HOOKS": ("max_parallel_hooks", 4),
            "CRACKERJACK_DEFAULT_TIMEOUT": ("default_timeout", 600),
            "CRACKERJACK_MAX_CONCURRENT_STRATEGIES": ("max_concurrent_strategies", 2),
        }

        for env_key, (attr, default) in int_vars.items():
            if env_key in env:
                overrides[attr] = _int_from_env(env[env_key], default)

        return overrides

    @classmethod
    def from_env(cls) -> OrchestrationConfig:
        overrides = cls._env_overrides()
        config = cls()
        config._apply_dict(overrides)
        return config

    @classmethod
    def load(cls, config_path: Path) -> OrchestrationConfig:
        # Start from hard defaults; only override from file/env.
        config = cls()

        if config_path.exists():
            file_config = cls.from_file(config_path)
            config = config.merge(file_config)  # type: ignore[assignment]

        env_overrides = cls._env_overrides()
        config = config.with_overrides(**env_overrides)  # type: ignore[assignment]

        return config

    # ------------------------------------------------------------------ #
    # Mutation helpers
    # ------------------------------------------------------------------ #

    def _apply_dict(self, values: dict[str, Any]) -> None:
        # Accept aliases from YAML where keys are shorter (e.g., enable, mode)
        aliases = {
            "enable": "enable_orchestration",
            "mode": "orchestration_mode",
        }
        for key, value in values.items():
            attr = aliases.get(key, key)
            if not hasattr(self, attr):
                continue
            if isinstance(value, str):
                value = value.strip()
            setattr(self, attr, value)

    def merge(self, other: OrchestrationConfig) -> OrchestrationConfig:
        data = dataclasses.asdict(self)
        other_data = dataclasses.asdict(other)
        data.update(other_data)
        merged = OrchestrationConfig(**data)
        merged.config_file_path = other.config_file_path or self.config_file_path
        return merged

    def with_overrides(self, **overrides: Any) -> OrchestrationConfig:
        # Create a shallow copy without using dataclasses.replace to satisfy type checker
        updated = OrchestrationConfig(**dataclasses.asdict(self))
        for key, value in overrides.items():
            if value is not None and hasattr(updated, key):
                setattr(updated, key, value)
        return updated

    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        return {
            "orchestration": {
                "enable": self.enable_orchestration,
                "mode": self.orchestration_mode,
                "enable_caching": self.enable_caching,
                "cache_backend": self.cache_backend,
                "cache_ttl": self.cache_ttl,
                "cache_max_entries": self.cache_max_entries,
                "max_parallel_hooks": self.max_parallel_hooks,
                "default_timeout": self.default_timeout,
                "stop_on_critical_failure": self.stop_on_critical_failure,
                "enable_dependency_resolution": self.enable_dependency_resolution,
                "log_cache_stats": self.log_cache_stats,
                "log_execution_timing": self.log_execution_timing,
                "enable_strategy_parallelism": self.enable_strategy_parallelism,
                "enable_adaptive_execution": self.enable_adaptive_execution,
                "max_concurrent_strategies": self.max_concurrent_strategies,
                "enable_tool_proxy": self.enable_tool_proxy,
                "use_precommit_legacy": self.use_precommit_legacy,
            }
        }

    def save(self, config_path: Path) -> None:
        config_path.write_text(
            yaml.safe_dump(self.to_dict(), sort_keys=True),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ #
    # Validation / Conversion
    # ------------------------------------------------------------------ #

    def validate(self) -> list[str]:
        errors: list[str] = []

        if self.orchestration_mode not in {"acb", "legacy"}:
            errors.append("Invalid orchestration_mode; expected 'acb' or 'legacy'")

        if self.cache_backend not in {"memory", "tool_proxy", "redis"}:
            errors.append(
                "Invalid cache_backend; expected 'memory', 'tool_proxy', or 'redis'"
            )

        if self.cache_ttl <= 0:
            errors.append("cache_ttl must be positive")
        if self.cache_max_entries <= 0:
            errors.append("cache_max_entries must be positive")
        if self.max_parallel_hooks <= 0:
            errors.append("max_parallel_hooks must be positive")
        if self.default_timeout <= 0:
            errors.append("default_timeout must be positive")
        if self.max_concurrent_strategies <= 0:
            errors.append("max_concurrent_strategies must be positive")

        return errors

    def to_orchestrator_settings(self) -> Any:
        from crackerjack.orchestration.hook_orchestrator import HookOrchestratorSettings

        execution_mode = self.orchestration_mode
        if not self.enable_orchestration:
            execution_mode = "legacy"

        return HookOrchestratorSettings(
            execution_mode=execution_mode,
            enable_caching=self.enable_caching,
            cache_backend=self.cache_backend,
            max_parallel_hooks=self.max_parallel_hooks,
            default_timeout=self.default_timeout,
            enable_adaptive_execution=self.enable_adaptive_execution,
        )


# Convenience re-export for legacy imports
__all__ = ["OrchestrationConfig"]
