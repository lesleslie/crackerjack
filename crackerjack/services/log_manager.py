import logging
import os
import shutil
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from rich.console import Console

console = Console()


class LogManager:
    def __init__(self, app_name: str = "crackerjack") -> None:
        self.app_name = app_name
        self._log_dir = self._get_log_directory()
        self._setup_directories()

    def _get_log_directory(self) -> Path:
        cache_home = os.environ.get("XDG_CACHE_HOME")
        base_dir = Path(cache_home) if cache_home else Path.home() / ".cache"

        return base_dir / self.app_name / "logs"

    def _setup_directories(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)

        (self._log_dir / "debug").mkdir(exist_ok=True)
        (self._log_dir / "error").mkdir(exist_ok=True)
        (self._log_dir / "audit").mkdir(exist_ok=True)

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    @property
    def debug_dir(self) -> Path:
        return self._log_dir / "debug"

    @property
    def error_dir(self) -> Path:
        return self._log_dir / "error"

    @property
    def audit_dir(self) -> Path:
        return self._log_dir / "audit"

    def create_debug_log_file(self, session_id: str | None = None) -> Path:
        timestamp = int(time.time())
        if session_id:
            filename = f"debug -{timestamp}-{session_id}.log"
        else:
            filename = f"debug -{timestamp}.log"

        return self.debug_dir / filename

    def create_error_log_file(self, error_type: str = "general") -> Path:
        timestamp = int(time.time())
        filename = f"error -{error_type}-{timestamp}.log"
        return self.error_dir / filename

    def rotate_logs(
        self,
        log_dir: Path,
        pattern: str,
        max_files: int = 10,
        max_age_days: int = 30,
    ) -> int:
        if not log_dir.exists():
            return 0

        removed_count = 0
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

        log_files = sorted(
            log_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for i, log_file in enumerate(log_files):
            should_remove = False
            reason = ""

            if i >= max_files:
                should_remove = True
                reason = f"exceeds max files ({max_files})"

            elif log_file.stat().st_mtime < cutoff_time:
                should_remove = True
                reason = f"older than {max_age_days} days"

            if should_remove:
                with suppress(OSError, PermissionError):
                    log_file.unlink()
                    removed_count += 1
                    console.print(
                        f"[dim]🗑️ Removed old log: {log_file.name} ({reason})[/ dim]",
                    )

        return removed_count

    def cleanup_all_logs(
        self,
        debug_max_files: int = 10,
        error_max_files: int = 20,
        audit_max_files: int = 50,
        max_age_days: int = 30,
    ) -> dict[str, int]:
        results = {}

        results["debug"] = self.rotate_logs(
            self.debug_dir,
            "debug-*.log",
            debug_max_files,
            max_age_days,
        )

        results["error"] = self.rotate_logs(
            self.error_dir,
            "error-*.log",
            error_max_files,
            max_age_days,
        )

        results["audit"] = self.rotate_logs(
            self.audit_dir,
            "audit-*.log",
            audit_max_files,
            max_age_days,
        )

        return results

    def migrate_legacy_logs(
        self,
        source_dir: Path,
        dry_run: bool = False,
    ) -> dict[str, int]:
        if not source_dir.exists():
            return {"moved": 0, "failed": 0, "found": 0}

        debug_pattern = "crackerjack-debug-*.log"
        legacy_files = list[t.Any](source_dir.glob(debug_pattern))

        results = {"found": len(legacy_files), "moved": 0, "failed": 0}

        if not legacy_files:
            console.print("[green]✅ No legacy log files found to migrate[/ green]")
            return results

        console.print(
            f"[yellow]📦 Found {len(legacy_files)} legacy debug log files to migrate[/ yellow]",
        )

        for legacy_file in legacy_files:
            try:
                parts = legacy_file.stem.split("-")
                if len(parts) >= 3 and parts[-1].isdigit():
                    timestamp = parts[-1]
                else:
                    timestamp = str(int(legacy_file.stat().st_mtime))

                new_filename = f"debug -{timestamp}- migrated.log"
                new_path = self.debug_dir / new_filename

                if dry_run:
                    console.print(
                        f"[cyan]📋 Would move: {legacy_file.name} → {new_filename}[/ cyan]",
                    )
                    results["moved"] += 1
                else:
                    shutil.move(str(legacy_file), str(new_path))
                    results["moved"] += 1
                    console.print(
                        f"[green]✅ Moved: {legacy_file.name} → {new_filename}[/ green]",
                    )

            except (OSError, ValueError) as e:
                results["failed"] += 1
                console.print(
                    f"[red]❌ Failed to migrate {legacy_file.name}: {e}[/ red]",
                )

        return results

    def get_log_stats(self) -> dict[str, dict[str, int | str | float]]:
        stats: dict[str, dict[str, int | str | float]] = {}

        for log_type, log_dir in (
            ("debug", self.debug_dir),
            ("error", self.error_dir),
            ("audit", self.audit_dir),
        ):
            if log_dir.exists():
                files = list[t.Any](log_dir.glob("*.log"))
                total_size = sum(f.stat().st_size for f in files if f.exists())

                stats[log_type] = {
                    "count": len(files),
                    "size_mb": round(total_size / (1024 * 1024), 2),
                    "location": str(log_dir),
                }
            else:
                stats[log_type] = {
                    "count": 0,
                    "size_mb": 0.0,
                    "location": str(log_dir),
                }

        return stats

    def setup_rotating_file_handler(
        self,
        logger: logging.Logger,
        log_type: str = "debug",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> logging.FileHandler:
        from logging.handlers import RotatingFileHandler

        if log_type == "error":
            log_dir = self.error_dir
        elif log_type == "audit":
            log_dir = self.audit_dir
        else:
            log_dir = self.debug_dir

        log_file = log_dir / f"{log_type}.log"

        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s-%(message)s",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        return handler

    def print_log_summary(self) -> None:
        stats = self.get_log_stats()

        console.print("\n[bold]📊 Log File Summary[/ bold]")
        console.print(f"[dim]Location: {self.log_dir}[/ dim]")

        total_files: int = 0
        total_size: float = 0.0

        for log_type, data in stats.items():
            count_raw = data["count"]
            count: int = (
                int(count_raw) if isinstance(count_raw, str) else t.cast(int, count_raw)
            )
            size_raw = data["size_mb"]
            size: float = (
                float(size_raw)
                if isinstance(size_raw, str)
                else t.cast(float, size_raw)
            )

            total_files += count
            total_size += size

            if count > 0:
                console.print(f" {log_type.capitalize()}: {count} files, {size}MB")
            else:
                console.print(f" {log_type.capitalize()}: No files")

        if total_files > 0:
            console.print(
                f"\n[bold]Total: {total_files} files, {total_size: .2f}MB[/ bold]",
            )
        else:
            console.print("\n[dim]No log files found[/ dim]")


log_manager = LogManager()


def get_log_manager() -> LogManager:
    return log_manager
