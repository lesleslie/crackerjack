"""Configuration management for orchestration layer (Phase 4).

Provides:
- Schema validation for orchestration settings
- File-based configuration (.crackerjack.yaml)
- Environment variable overrides
- Sensible defaults for all settings
- Configuration merging and inheritance
"""

from __future__ import annotations

import os
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from crackerjack.orchestration.hook_orchestrator import HookOrchestratorSettings


@dataclass
class OrchestrationConfig:
    """Complete orchestration configuration.

    Supports three configuration sources (in priority order):
    1. Environment variables (CRACKERJACK_*)
    2. Project config file (.crackerjack.yaml)
    3. Defaults (from this class)
    """

    # Orchestration settings
    enable_orchestration: bool = False
    orchestration_mode: str = "acb"  # 'legacy' or 'acb'

    # Cache settings
    enable_caching: bool = True
    cache_backend: str = "memory"  # 'memory' or 'tool_proxy'
    cache_ttl: int = 3600  # seconds
    cache_max_entries: int = 100  # memory cache only

    # Execution settings
    max_parallel_hooks: int = 4
    default_timeout: int = 600  # seconds
    stop_on_critical_failure: bool = True

    # Advanced settings
    enable_dependency_resolution: bool = True
    log_cache_stats: bool = False
    log_execution_timing: bool = False

    # Triple parallelism settings (Phase 5-7)
    enable_strategy_parallelism: bool = True  # Run fast + comprehensive concurrently
    enable_adaptive_execution: bool = True  # Use adaptive strategy (dependency-aware)
    max_concurrent_strategies: int = 2  # Usually 2 (fast + comprehensive)

    # Phase 8: Direct tool invocation settings
    use_precommit_legacy: bool = (
        True  # Use pre-commit wrapper (True) or direct invocation (False)
    )

    # Config file path (set during load)
    config_file_path: Path | None = field(default=None, repr=False)

    @classmethod
    def from_file(cls, config_path: Path) -> OrchestrationConfig:
        """Load configuration from YAML file.

        Args:
            config_path: Path to .crackerjack.yaml

        Returns:
            OrchestrationConfig with file settings

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with config_path.open() as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

        # Extract orchestration section
        orch_data = data.get("orchestration", {})

        # Create config from file data
        config = cls(
            enable_orchestration=orch_data.get("enable", cls.enable_orchestration),
            orchestration_mode=orch_data.get("mode", cls.orchestration_mode),
            enable_caching=orch_data.get("enable_caching", cls.enable_caching),
            cache_backend=orch_data.get("cache_backend", cls.cache_backend),
            cache_ttl=orch_data.get("cache_ttl", cls.cache_ttl),
            cache_max_entries=orch_data.get("cache_max_entries", cls.cache_max_entries),
            max_parallel_hooks=orch_data.get(
                "max_parallel_hooks", cls.max_parallel_hooks
            ),
            default_timeout=orch_data.get("default_timeout", cls.default_timeout),
            stop_on_critical_failure=orch_data.get(
                "stop_on_critical_failure", cls.stop_on_critical_failure
            ),
            enable_dependency_resolution=orch_data.get(
                "enable_dependency_resolution", cls.enable_dependency_resolution
            ),
            log_cache_stats=orch_data.get("log_cache_stats", cls.log_cache_stats),
            log_execution_timing=orch_data.get(
                "log_execution_timing", cls.log_execution_timing
            ),
            enable_strategy_parallelism=orch_data.get(
                "enable_strategy_parallelism", cls.enable_strategy_parallelism
            ),
            enable_adaptive_execution=orch_data.get(
                "enable_adaptive_execution", cls.enable_adaptive_execution
            ),
            max_concurrent_strategies=orch_data.get(
                "max_concurrent_strategies", cls.max_concurrent_strategies
            ),
            use_precommit_legacy=orch_data.get(
                "use_precommit_legacy", cls.use_precommit_legacy
            ),
            config_file_path=config_path,
        )

        return config

    @classmethod
    def from_env(cls) -> OrchestrationConfig:
        """Load configuration from environment variables.

        Environment variables:
            CRACKERJACK_ENABLE_ORCHESTRATION: 'true'/'false'
            CRACKERJACK_ORCHESTRATION_MODE: 'legacy'/'acb'
            CRACKERJACK_ENABLE_CACHING: 'true'/'false'
            CRACKERJACK_CACHE_BACKEND: 'memory'/'tool_proxy'
            CRACKERJACK_CACHE_TTL: integer seconds
            CRACKERJACK_CACHE_MAX_ENTRIES: integer
            CRACKERJACK_MAX_PARALLEL_HOOKS: integer
            CRACKERJACK_DEFAULT_TIMEOUT: integer seconds
            CRACKERJACK_STOP_ON_CRITICAL_FAILURE: 'true'/'false'
            CRACKERJACK_ENABLE_STRATEGY_PARALLELISM: 'true'/'false'
            CRACKERJACK_ENABLE_ADAPTIVE_EXECUTION: 'true'/'false'
            CRACKERJACK_MAX_CONCURRENT_STRATEGIES: integer
            CRACKERJACK_USE_PRECOMMIT_LEGACY: 'true'/'false'

        Returns:
            OrchestrationConfig with environment settings
        """

        def get_bool(key: str, default: bool) -> bool:
            """Get boolean from env var."""
            val = os.getenv(key, "").lower()
            if val in ("true", "1", "yes"):
                return True
            if val in ("false", "0", "no"):
                return False
            return default

        def get_int(key: str, default: int) -> int:
            """Get integer from env var."""
            val = os.getenv(key)
            if val:
                try:
                    return int(val)
                except ValueError:
                    return default
            return default

        def get_str(key: str, default: str) -> str:
            """Get string from env var."""
            return os.getenv(key, default)

        return cls(
            enable_orchestration=get_bool(
                "CRACKERJACK_ENABLE_ORCHESTRATION", cls.enable_orchestration
            ),
            orchestration_mode=get_str(
                "CRACKERJACK_ORCHESTRATION_MODE", cls.orchestration_mode
            ),
            enable_caching=get_bool("CRACKERJACK_ENABLE_CACHING", cls.enable_caching),
            cache_backend=get_str("CRACKERJACK_CACHE_BACKEND", cls.cache_backend),
            cache_ttl=get_int("CRACKERJACK_CACHE_TTL", cls.cache_ttl),
            cache_max_entries=get_int(
                "CRACKERJACK_CACHE_MAX_ENTRIES", cls.cache_max_entries
            ),
            max_parallel_hooks=get_int(
                "CRACKERJACK_MAX_PARALLEL_HOOKS", cls.max_parallel_hooks
            ),
            default_timeout=get_int("CRACKERJACK_DEFAULT_TIMEOUT", cls.default_timeout),
            stop_on_critical_failure=get_bool(
                "CRACKERJACK_STOP_ON_CRITICAL_FAILURE", cls.stop_on_critical_failure
            ),
            enable_strategy_parallelism=get_bool(
                "CRACKERJACK_ENABLE_STRATEGY_PARALLELISM",
                cls.enable_strategy_parallelism,
            ),
            enable_adaptive_execution=get_bool(
                "CRACKERJACK_ENABLE_ADAPTIVE_EXECUTION", cls.enable_adaptive_execution
            ),
            max_concurrent_strategies=get_int(
                "CRACKERJACK_MAX_CONCURRENT_STRATEGIES", cls.max_concurrent_strategies
            ),
            use_precommit_legacy=get_bool(
                "CRACKERJACK_USE_PRECOMMIT_LEGACY", cls.use_precommit_legacy
            ),
        )

    @classmethod
    def load(cls, config_path: Path | None = None) -> OrchestrationConfig:
        """Load configuration with priority: env vars > file > defaults.

        Args:
            config_path: Optional path to config file. If None, searches for
                        .crackerjack.yaml in current directory.

        Returns:
            Merged configuration from all sources
        """
        # Start with defaults
        config = cls()

        # Try to find config file if not specified
        if config_path is None:
            config_path = Path.cwd() / ".crackerjack.yaml"

        # Merge file settings if file exists
        if config_path.exists():
            file_config = cls.from_file(config_path)
            config = cls._merge(config, file_config)

        # Merge environment settings (highest priority)
        env_config = cls.from_env()
        config = cls._merge(config, env_config)

        return config

    @classmethod
    def _merge(
        cls, base: OrchestrationConfig, override: OrchestrationConfig
    ) -> OrchestrationConfig:
        """Merge two configurations, with override taking precedence.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        # Only override if value differs from class default
        defaults = cls()

        return cls(
            enable_orchestration=(
                override.enable_orchestration
                if override.enable_orchestration != defaults.enable_orchestration
                else base.enable_orchestration
            ),
            orchestration_mode=(
                override.orchestration_mode
                if override.orchestration_mode != defaults.orchestration_mode
                else base.orchestration_mode
            ),
            enable_caching=(
                override.enable_caching
                if override.enable_caching != defaults.enable_caching
                else base.enable_caching
            ),
            cache_backend=(
                override.cache_backend
                if override.cache_backend != defaults.cache_backend
                else base.cache_backend
            ),
            cache_ttl=(
                override.cache_ttl
                if override.cache_ttl != defaults.cache_ttl
                else base.cache_ttl
            ),
            cache_max_entries=(
                override.cache_max_entries
                if override.cache_max_entries != defaults.cache_max_entries
                else base.cache_max_entries
            ),
            max_parallel_hooks=(
                override.max_parallel_hooks
                if override.max_parallel_hooks != defaults.max_parallel_hooks
                else base.max_parallel_hooks
            ),
            default_timeout=(
                override.default_timeout
                if override.default_timeout != defaults.default_timeout
                else base.default_timeout
            ),
            stop_on_critical_failure=(
                override.stop_on_critical_failure
                if override.stop_on_critical_failure
                != defaults.stop_on_critical_failure
                else base.stop_on_critical_failure
            ),
            enable_dependency_resolution=(
                override.enable_dependency_resolution
                if override.enable_dependency_resolution
                != defaults.enable_dependency_resolution
                else base.enable_dependency_resolution
            ),
            log_cache_stats=(
                override.log_cache_stats
                if override.log_cache_stats != defaults.log_cache_stats
                else base.log_cache_stats
            ),
            log_execution_timing=(
                override.log_execution_timing
                if override.log_execution_timing != defaults.log_execution_timing
                else base.log_execution_timing
            ),
            enable_strategy_parallelism=(
                override.enable_strategy_parallelism
                if override.enable_strategy_parallelism
                != defaults.enable_strategy_parallelism
                else base.enable_strategy_parallelism
            ),
            enable_adaptive_execution=(
                override.enable_adaptive_execution
                if override.enable_adaptive_execution
                != defaults.enable_adaptive_execution
                else base.enable_adaptive_execution
            ),
            max_concurrent_strategies=(
                override.max_concurrent_strategies
                if override.max_concurrent_strategies
                != defaults.max_concurrent_strategies
                else base.max_concurrent_strategies
            ),
            use_precommit_legacy=(
                override.use_precommit_legacy
                if override.use_precommit_legacy != defaults.use_precommit_legacy
                else base.use_precommit_legacy
            ),
            config_file_path=override.config_file_path or base.config_file_path,
        )

    def validate(self) -> list[str]:
        """Validate configuration settings.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate orchestration_mode
        if self.orchestration_mode not in ("legacy", "acb"):
            errors.append(
                f"Invalid orchestration_mode: {self.orchestration_mode}. "
                "Must be 'legacy' or 'acb'."
            )

        # Validate cache_backend
        if self.cache_backend not in ("memory", "tool_proxy"):
            errors.append(
                f"Invalid cache_backend: {self.cache_backend}. "
                "Must be 'memory' or 'tool_proxy'."
            )

        # Validate numeric ranges
        if self.cache_ttl < 1:
            errors.append(f"cache_ttl must be positive, got {self.cache_ttl}")

        if self.cache_max_entries < 1:
            errors.append(
                f"cache_max_entries must be positive, got {self.cache_max_entries}"
            )

        if self.max_parallel_hooks < 1:
            errors.append(
                f"max_parallel_hooks must be positive, got {self.max_parallel_hooks}"
            )

        if self.default_timeout < 1:
            errors.append(
                f"default_timeout must be positive, got {self.default_timeout}"
            )

        if self.max_concurrent_strategies < 1:
            errors.append(
                f"max_concurrent_strategies must be positive, got {self.max_concurrent_strategies}"
            )

        return errors

    def to_orchestrator_settings(self) -> HookOrchestratorSettings:
        """Convert to HookOrchestratorSettings.

        Returns:
            HookOrchestratorSettings instance
        """
        return HookOrchestratorSettings(
            execution_mode=self.orchestration_mode,
            enable_caching=self.enable_caching,
            cache_backend=self.cache_backend,
            max_parallel_hooks=self.max_parallel_hooks,
            enable_adaptive_execution=self.enable_adaptive_execution,
        )

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
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
                "use_precommit_legacy": self.use_precommit_legacy,
            }
        }

    def save(self, config_path: Path) -> None:
        """Save configuration to YAML file.

        Args:
            config_path: Path to save .crackerjack.yaml
        """
        with config_path.open("w") as f:
            yaml.safe_dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
