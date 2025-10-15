from __future__ import annotations

import socket
import typing as t
from pathlib import Path

from acb.depends import depends

from crackerjack.config.settings import CrackerjackSettings, GlobalLockSettings


class GlobalLockConfig:
    """Compatibility wrapper for global lock settings."""

    def __init__(self, settings: GlobalLockSettings | None = None) -> None:
        base_settings = settings or depends.get_sync(CrackerjackSettings).global_lock
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
        self._settings.lock_directory.mkdir(parents=True, exist_ok=True)

    def __getattr__(self, item: str):
        return getattr(self._settings, item)

    def get_lock_path(self, hook_name: str) -> Path:
        safe_name = hook_name.replace("/", "_")
        return self._settings.lock_directory / f"{safe_name}.lock"

    @classmethod
    async def from_options(cls, options: t.Any) -> GlobalLockConfig:
        base_settings = depends.get_sync(CrackerjackSettings).global_lock
        overrides = getattr(options, "global_lock", None)

        if overrides is None:
            return cls(base_settings)

        custom = base_settings.model_copy()
        for field in custom.model_fields:
            if hasattr(overrides, field):
                setattr(custom, field, getattr(overrides, field))

        return cls(custom)


def get_global_lock_config() -> GlobalLockConfig:
    return GlobalLockConfig()
