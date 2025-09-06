import os
import socket
from dataclasses import dataclass, field
from pathlib import Path

from ..models.protocols import OptionsProtocol


@dataclass
class GlobalLockConfig:
    """Configuration for global hook locking system."""

    enabled: bool = True
    timeout_seconds: float = 600.0  # 10 minutes default
    stale_lock_hours: float = 2.0  # Clean locks older than 2 hours
    lock_directory: Path = field(
        default_factory=lambda: Path.home() / ".crackerjack" / "locks"
    )
    session_heartbeat_interval: float = 30.0  # Heartbeat every 30s
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 5.0
    enable_lock_monitoring: bool = True

    @classmethod
    def from_options(cls, options: "OptionsProtocol") -> "GlobalLockConfig":
        """Create GlobalLockConfig from CLI options.

        Args:
            options: Options object containing CLI arguments

        Returns:
            Configured GlobalLockConfig instance
        """
        # Import here to avoid circular import

        # Create config with custom values from options
        enabled = not options.disable_global_locks
        timeout_seconds = float(options.global_lock_timeout)
        # Get default lock directory from field definition
        default_lock_dir = Path.home() / ".crackerjack" / "locks"
        lock_directory = (
            Path(options.global_lock_dir)
            if options.global_lock_dir
            else default_lock_dir
        )

        # Create instance with all parameters so __post_init__ is called
        config = cls(
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            lock_directory=lock_directory,
        )

        return config

    def __post_init__(self) -> None:
        """Ensure lock directory exists and has proper permissions."""
        self.lock_directory.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (owner read/write only)
        self.lock_directory.chmod(0o700)

    @property
    def hostname(self) -> str:
        """Get the current hostname for lock identification."""
        return socket.gethostname()

    @property
    def session_id(self) -> str:
        """Get a unique session identifier."""
        return f"{self.hostname}_{os.getpid()}"

    def get_lock_path(self, hook_name: str) -> Path:
        """Get the lock file path for a specific hook.

        Args:
            hook_name: Name of the hook

        Returns:
            Path to the lock file
        """
        return self.lock_directory / f"{hook_name}.lock"

    def get_heartbeat_path(self, hook_name: str) -> Path:
        """Get the heartbeat file path for a specific hook.

        Args:
            hook_name: Name of the hook

        Returns:
            Path to the heartbeat file
        """
        return self.lock_directory / f"{hook_name}.heartbeat"

    def is_valid_lock_file(self, lock_path: Path) -> bool:
        """Check if a lock file is valid (not stale).

        Args:
            lock_path: Path to the lock file

        Returns:
            True if the lock file is valid and not stale
        """
        if not lock_path.exists():
            return False

        # Check if the lock file is older than stale_lock_hours
        import time

        file_age_hours = (time.time() - lock_path.stat().st_mtime) / 3600
        return file_age_hours < self.stale_lock_hours
