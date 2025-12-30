from __future__ import annotations

import socket
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.config import load_settings
from crackerjack.config.settings import CrackerjackSettings, GlobalLockSettings


class GlobalLockConfig:
    """Compatibility wrapper for global lock settings.

    Supports both APIs:
    - New API: GlobalLockConfig(settings=GlobalLockSettings(...))
    - Old API: GlobalLockConfig(lock_directory=path, timeout_seconds=600, ...)
    """

    def _should_build_from_compatibility_params(
        self,
        enabled: bool | None,
        timeout_seconds: float | None,
        stale_lock_hours: float | None,
        lock_directory: Path | None,
        session_heartbeat_interval: float | None,
        max_retry_attempts: int | None,
        retry_delay_seconds: float | None,
        enable_lock_monitoring: bool | None,
    ) -> bool:
        """Check if any backwards compatibility parameters are provided."""
        return any(
            param is not None
            for param in (
                enabled,
                timeout_seconds,
                stale_lock_hours,
                lock_directory,
                session_heartbeat_interval,
                max_retry_attempts,
                retry_delay_seconds,
                enable_lock_monitoring,
            )
        )

    def _build_settings_from_compatibility_params(
        self,
        enabled: bool | None,
        timeout_seconds: float | None,
        stale_lock_hours: float | None,
        lock_directory: Path | None,
        session_heartbeat_interval: float | None,
        max_retry_attempts: int | None,
        retry_delay_seconds: float | None,
        enable_lock_monitoring: bool | None,
    ) -> GlobalLockSettings:
        """Build settings from backwards compatibility parameters."""
        # Get defaults from CrackerjackSettings
        default_settings = load_settings(CrackerjackSettings).global_lock
        # Create a copy with overrides
        settings_dict = {
            "enabled": enabled if enabled is not None else default_settings.enabled,
            "timeout_seconds": (
                timeout_seconds
                if timeout_seconds is not None
                else default_settings.timeout_seconds
            ),
            "stale_lock_hours": (
                stale_lock_hours
                if stale_lock_hours is not None
                else default_settings.stale_lock_hours
            ),
            "lock_directory": (
                lock_directory
                if lock_directory is not None
                else default_settings.lock_directory
            ),
            "session_heartbeat_interval": (
                session_heartbeat_interval
                if session_heartbeat_interval is not None
                else default_settings.session_heartbeat_interval
            ),
            "max_retry_attempts": (
                max_retry_attempts
                if max_retry_attempts is not None
                else default_settings.max_retry_attempts
            ),
            "retry_delay_seconds": (
                retry_delay_seconds
                if retry_delay_seconds is not None
                else default_settings.retry_delay_seconds
            ),
            "enable_lock_monitoring": (
                enable_lock_monitoring
                if enable_lock_monitoring is not None
                else default_settings.enable_lock_monitoring
            ),
        }
        return GlobalLockSettings(**settings_dict)

    def __init__(
        self,
        settings: GlobalLockSettings | None = None,
        # Backwards compatibility parameters
        enabled: bool | None = None,
        timeout_seconds: float | None = None,
        stale_lock_hours: float | None = None,
        lock_directory: Path | None = None,
        session_heartbeat_interval: float | None = None,
        max_retry_attempts: int | None = None,
        retry_delay_seconds: float | None = None,
        enable_lock_monitoring: bool | None = None,
    ) -> None:
        # If any backwards compatibility parameters are provided, build settings from them
        if self._should_build_from_compatibility_params(
            enabled,
            timeout_seconds,
            stale_lock_hours,
            lock_directory,
            session_heartbeat_interval,
            max_retry_attempts,
            retry_delay_seconds,
            enable_lock_monitoring,
        ):
            settings = self._build_settings_from_compatibility_params(
                enabled,
                timeout_seconds,
                stale_lock_hours,
                lock_directory,
                session_heartbeat_interval,
                max_retry_attempts,
                retry_delay_seconds,
                enable_lock_monitoring,
            )

        base_settings = settings or load_settings(CrackerjackSettings).global_lock
        self._settings = base_settings.model_copy()
        self.session_id = (
            getattr(self._settings, "session_id", None) or self._generate_session_id()
        )
        self.hostname = (
            getattr(self._settings, "hostname", None) or socket.gethostname()
        )
        self._ensure_lock_directory()

    @staticmethod
    def _generate_session_id() -> str:
        import uuid

        return uuid.uuid4().hex[:8]

    def _ensure_lock_directory(self) -> None:
        lock_dir = self._settings.lock_directory
        lock_dir.mkdir(parents=True, exist_ok=True)
        # Enforce secure permissions (owner rwx only)
        with suppress(Exception):
            lock_dir.chmod(0o700)

    def __getattr__(self, item: str):
        return getattr(self._settings, item)

    def get_lock_path(self, hook_name: str) -> Path:
        safe_name = hook_name.replace("/", "_")
        return self._settings.lock_directory / f"{safe_name}.lock"

    @classmethod
    def from_options(cls, options: t.Any) -> GlobalLockConfig:
        """Create GlobalLockConfig from CLI options object.

        Supports two formats:
        1. Nested: options.global_lock with GlobalLockSettings-like fields
        2. Flat: options with global_lock_* prefixed fields (from CLI)

        Synchronous method - no async operations needed.
        """
        base_settings = load_settings(CrackerjackSettings).global_lock
        overrides = getattr(options, "global_lock", None)

        # Handle nested global_lock object
        if overrides is not None:
            custom = base_settings.model_copy()
            for field in custom.model_fields:
                if hasattr(overrides, field):
                    setattr(custom, field, getattr(overrides, field))
            return cls(custom)

        # Handle flat CLI options with global_lock_* prefix
        params: dict[str, t.Any] = {}
        if hasattr(options, "disable_global_locks"):
            params["enabled"] = not options.disable_global_locks
        if hasattr(options, "global_lock_timeout"):
            params["timeout_seconds"] = float(options.global_lock_timeout)
        if hasattr(options, "global_lock_dir") and options.global_lock_dir:
            params["lock_directory"] = Path(options.global_lock_dir)
        # Note: global_lock_cleanup is handled at runtime, not in config

        # If any options were provided, create config with them
        if params:
            return cls(**params)

        # Otherwise use defaults
        return cls(base_settings)


def get_global_lock_config() -> GlobalLockConfig:
    return GlobalLockConfig()
