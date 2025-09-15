import os
import socket
from dataclasses import dataclass, field
from pathlib import Path

from ..models.protocols import OptionsProtocol


@dataclass
class GlobalLockConfig:
    enabled: bool = True
    timeout_seconds: float = 600.0
    stale_lock_hours: float = 2.0
    lock_directory: Path = field(
        default_factory=lambda: Path.home() / ".crackerjack" / "locks"
    )
    session_heartbeat_interval: float = 30.0
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 5.0
    enable_lock_monitoring: bool = True

    @classmethod
    def from_options(
        cls: type["GlobalLockConfig"], options: "OptionsProtocol"
    ) -> "GlobalLockConfig":
        enabled = not options.disable_global_locks
        timeout_seconds = float(options.global_lock_timeout)

        default_lock_dir = Path.home() / ".crackerjack" / "locks"
        lock_directory = (
            Path(options.global_lock_dir)
            if options.global_lock_dir
            else default_lock_dir
        )

        config = cls(
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            lock_directory=lock_directory,
        )

        return config

    def __post_init__(self) -> None:
        self.lock_directory.mkdir(parents=True, exist_ok=True)

        self.lock_directory.chmod(0o700)

    @property
    def hostname(self) -> str:
        return socket.gethostname()

    @property
    def session_id(self) -> str:
        return f"{self.hostname}_{os.getpid()}"

    def get_lock_path(self, hook_name: str) -> Path:
        return self.lock_directory / f"{hook_name}.lock"

    def get_heartbeat_path(self, hook_name: str) -> Path:
        return self.lock_directory / f"{hook_name}.heartbeat"

    def is_valid_lock_file(self, lock_path: Path) -> bool:
        if not lock_path.exists():
            return False

        import time

        file_age_hours = (time.time() - lock_path.stat().st_mtime) / 3600
        return file_age_hours < self.stale_lock_hours
