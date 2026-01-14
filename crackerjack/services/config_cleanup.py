"""Config file cleanup service with smart merge into pyproject.toml.

This service provides intelligent cleanup of standalone configuration files by:
1. Smart merging config files into pyproject.toml tool sections
2. Removing redundant standalone config files
3. Cleaning up test cache directories and output files
4. Full backup and rollback support
"""

from __future__ import annotations

import configparser
import json
import logging
import shutil
import tarfile
import tomllib
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich.console import Console

from crackerjack.services.backup_service import BackupMetadata, PackageBackupService
from crackerjack.services.secure_path_utils import (
    AtomicFileOperations,
    SecurePathValidator,
)
from crackerjack.services.security_logger import (
    SecurityEventLevel,
    SecurityEventType,
    get_security_logger,
)

if t.TYPE_CHECKING:
    from crackerjack.config.settings import CrackerjackSettings
    from crackerjack.models.protocols import (
        ConsoleInterface as ConsoleProtocol,
    )
    from crackerjack.models.protocols import (
        GitInterface,
    )

logger = logging.getLogger(__name__)


@dataclass
class ConfigCleanupResult:
    """Result of config cleanup operation."""

    success: bool
    configs_merged: int = 0
    configs_removed: int = 0
    cache_dirs_cleaned: int = 0
    output_files_cleaned: int = 0
    backup_metadata: BackupMetadata | None = None
    summary: str = ""
    error_message: str | None = None
    merged_files: dict[str, str] = field(
        default_factory=dict
    )  # filename -> target section


@dataclass
class MergeStrategy:
    """Defines how to merge a specific config file."""

    filename: str
    target_section: str  # TOML section path like "tool.mypy"
    merge_type: str  # "ini_flatten", "pattern_union", "json_deep", "ignore_list"


class ConfigCleanupService:
    """Service for intelligent config file cleanup with safety mechanisms.

    This service implements smart merging of standalone config files into
    pyproject.toml, comprehensive test output cleanup, and backup/rollback support.

    Examples:
        >>> from rich.console import Console
        >>> from pathlib import Path
        >>>
        >>> console = Console()
        >>> service = ConfigCleanupService(console=console, pkg_path=Path.cwd())
        >>> result = service.cleanup_configs(dry_run=True)
        >>> print(f"Would merge {result.configs_merged} configs")
    """

    def __init__(
        self,
        console: ConsoleProtocol | None = None,
        pkg_path: Path | None = None,
        git_service: GitInterface | None = None,
        settings: CrackerjackSettings | None = None,
    ) -> None:
        """Initialize config cleanup service.

        Args:
            console: Rich console for output (constructor injection)
            pkg_path: Package root path
            git_service: Git service for git operations (optional)
            settings: Crackerjack configuration (optional, loads if not provided)
        """
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()
        self.git_service = git_service

        # Load settings if not provided
        if settings is None:
            from crackerjack.config import load_settings
            from crackerjack.config.settings import CrackerjackSettings

            settings = load_settings(CrackerjackSettings)

        self.settings = settings
        self.security_logger = get_security_logger()

        # Pre-compute merge strategies from settings
        self._merge_strategies = self._build_merge_strategies()

        # Backup service
        self.backup_service = PackageBackupService(
            backup_root=self.pkg_path / "docs" / ".backups",
        )

        # Atomic file operations and path validation
        self.atomic_ops = AtomicFileOperations()
        self.path_validator = SecurePathValidator

    def cleanup_configs(
        self,
        dry_run: bool = False,
    ) -> ConfigCleanupResult:
        """Execute comprehensive config cleanup with full safety mechanisms.

        This method orchestrates the entire cleanup process:
        1. Detect config files to merge
        2. Validate preconditions
        3. Create backup
        4. Smart merge configs into pyproject.toml
        5. Remove standalone files
        6. Clean up test outputs
        7. Generate report

        Args:
            dry_run: Preview changes without executing (default: False)

        Returns:
            ConfigCleanupResult with operation details

        Examples:
            >>> service = ConfigCleanupService(pkg_path=Path("/tmp/project"))
            >>> result = service.cleanup_configs(dry_run=True)
            >>> assert result.configs_merged >= 0
        """
        result = ConfigCleanupResult(success=False)

        try:
            # Phase 1: Detect config files
            config_files = self._detect_config_files()
            cache_dirs = self._detect_cache_dirs()
            output_files = self._detect_output_files()

            if not config_files and not cache_dirs and not output_files:
                result.success = True
                result.summary = "No config files or test outputs to cleanup"
                self._display_completion(result)
                return result

            # Phase 2: Validate preconditions
            is_valid, error_msg = self._validate_preconditions()
            if not is_valid:
                result.success = False
                result.error_message = error_msg
                return result

            # Phase 3: Create backup
            if dry_run:
                self.console.print(
                    "[yellow]Dry run: Would create backup before cleanup[/yellow]"
                )
                backup_metadata = None
            else:
                backup_metadata = self._create_backup(config_files)
                if backup_metadata is None:
                    result.success = False
                    result.error_message = "Backup creation failed"
                    return result

            result.backup_metadata = backup_metadata

            # Phase 4: Merge configs into pyproject.toml
            configs_merged, merged_files = self._merge_all_configs(
                config_files,
                dry_run=dry_run,
            )

            result.configs_merged = configs_merged
            result.merged_files = merged_files

            # Phase 5: Remove standalone config files
            configs_removed = self._remove_standalone_configs(
                config_files,
                dry_run=dry_run,
            )

            result.configs_removed = configs_removed

            # Phase 6: Smart merge .gitignore with standard patterns
            gitignore_merged = self._smart_merge_gitignore(dry_run=dry_run)

            # Track gitignore merge in result
            if gitignore_merged:
                result.merged_files[".gitignore"] = "smart_merge"

            # Phase 7: Clean up test outputs
            cache_dirs_cleaned = self._cleanup_cache_dirs(
                cache_dirs,
                dry_run=dry_run,
            )

            result.cache_dirs_cleaned = cache_dirs_cleaned

            output_files_cleaned = self._cleanup_output_files(
                output_files,
                dry_run=dry_run,
            )

            result.output_files_cleaned = output_files_cleaned

            # Phase 7: Generate summary
            result.summary = self._generate_summary(result)

            result.success = True

            # Log security event
            self.security_logger.log_security_event(
                SecurityEventType.FILE_CLEANED,
                SecurityEventLevel.INFO,
                f"Config cleanup completed: {configs_merged} configs merged, "
                f"{configs_removed} configs removed, "
                f"{cache_dirs_cleaned} cache dirs cleaned, "
                f"{output_files_cleaned} output files cleaned",
                configs_merged=configs_merged,
                configs_removed=configs_removed,
                cache_dirs_cleaned=cache_dirs_cleaned,
                output_files_cleaned=output_files_cleaned,
                dry_run=dry_run,
            )

        except Exception as e:
            logger.exception("Config cleanup failed")
            result.success = False
            result.error_message = str(e)

            self.security_logger.log_security_event(
                SecurityEventType.FILE_CLEANED,
                SecurityEventLevel.ERROR,
                f"Config cleanup failed: {e}",
            )

        self._display_completion(result)
        return result

    def rollback_cleanup(self, backup_metadata: BackupMetadata) -> bool:
        """Rollback config cleanup from backup.

        Args:
            backup_metadata: Backup metadata from previous cleanup operation

        Returns:
            True if rollback succeeded, False otherwise

        Examples:
            >>> service = ConfigCleanupService(pkg_path=Path("/tmp/project"))
            >>> result = service.cleanup_configs()
            >>> if not result.success:
            ...     service.rollback_cleanup(result.backup_metadata)
        """
        try:
            self.console.print(
                f"[cyan]ℹ️[/cyan] Rolling back config cleanup: {backup_metadata.backup_id}"
            )

            # Extract files from backup
            if not backup_metadata.backup_directory.exists():
                self.console.print(
                    f"[red]❌[/red] Backup directory not found: {backup_metadata.backup_directory}"
                )
                return False

            # Restore from backup archive
            backup_archive = backup_metadata.backup_directory / "backup.tar.gz"
            if not backup_archive.exists():
                self.console.print(
                    f"[red]❌[/red] Backup archive not found: {backup_archive}"
                )
                return False

            # Extract to temp location first
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                with tarfile.open(backup_archive, "r:gz") as tar:
                    tar.extractall(temp_path)

                # Move files back to original locations
                restored = 0
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(temp_path)
                        target_path = self.pkg_path / relative_path

                        # Create parent directories
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Atomic move
                        shutil.move(str(file_path), str(target_path))
                        restored += 1

            self.console.print(
                f"[green]✅[/green] Restored {restored} files from backup"
            )

            self.security_logger.log_security_event(
                SecurityEventType.BACKUP_RESTORED,
                SecurityEventLevel.INFO,
                f"Config cleanup rollback completed: {restored} files restored",
                backup_id=backup_metadata.backup_id,
            )

            return True

        except Exception as e:
            logger.exception("Rollback failed")
            self.console.print(f"[red]❌[/red] Rollback failed: {e}")
            return False

    def _detect_config_files(self) -> list[Path]:
        """Detect standalone config files that should be merged.

        Returns:
            List of config file paths to process

        Examples:
            >>> service = ConfigCleanupService()
            >>> files = service._detect_config_files()
            >>> assert all(f.suffix in [".ini", ".json", ".yml", ".yaml"] for f in files)
        """
        config_files = []

        # Check for files based on merge strategies
        for strategy in self._merge_strategies:
            config_path = self.pkg_path / strategy.filename
            if config_path.exists():
                config_files.append(config_path)

        return config_files

    def _detect_cache_dirs(self) -> list[Path]:
        """Detect cache directories to clean.

        Returns:
            List of cache directory paths
        """
        cache_dirs = []

        for cache_dir in self.settings.config_cleanup.cache_dirs_to_clean:
            cache_path = self.pkg_path / cache_dir
            if cache_path.exists() and cache_path.is_dir():
                cache_dirs.append(cache_path)

        return cache_dirs

    def _detect_output_files(self) -> list[Path]:
        """Detect output files to clean.

        Returns:
            List of output file paths
        """
        output_files = []

        for output_file in self.settings.config_cleanup.output_files_to_clean:
            output_path = self.pkg_path / output_file
            if output_path.exists() and output_path.is_file():
                output_files.append(output_path)

        return output_files

    def _build_merge_strategies(self) -> list[MergeStrategy]:
        """Build merge strategies from settings.

        Returns:
            List of MergeStrategy objects

        Examples:
            >>> service = ConfigCleanupService()
            >>> strategies = service._build_merge_strategies()
            >>> mypy_strategy = [s for s in strategies if "mypy.ini" in s.filename][0]
            >>> assert mypy_strategy.target_section == "tool.mypy"
        """
        strategies = []

        merge_strategies = self.settings.config_cleanup.merge_strategies

        for filename, target_section in merge_strategies.items():
            # Determine merge type based on file extension
            if filename.endswith(".ini"):
                merge_type = "ini_flatten"
            elif filename.endswith("ignore"):
                merge_type = "pattern_union"
            elif filename.endswith(".json"):
                merge_type = "json_deep"
            elif filename in [".codespell-ignore", ".codespellrc"]:
                merge_type = "ignore_list"
            else:
                merge_type = "pattern_union"  # Default

            strategies.append(
                MergeStrategy(
                    filename=filename,
                    target_section=target_section,
                    merge_type=merge_type,
                )
            )

        return strategies

    def _validate_preconditions(self) -> tuple[bool, str | None]:
        """Validate preconditions before cleanup.

        Returns:
            Tuple of (is_valid, error_message)

        Examples:
            >>> service = ConfigCleanupService()
            >>> is_valid, error = service._validate_preconditions()
            >>> assert is_valid or error is not None
        """
        # Check if pyproject.toml exists
        pyproject_path = self.pkg_path / "pyproject.toml"
        if not pyproject_path.exists():
            return False, "pyproject.toml not found"

        # Check git repo status (if git service available)
        if self.git_service:
            try:
                changed_files = self.git_service.get_changed_files()
                if changed_files:
                    return (
                        False,
                        "Git repository has uncommitted changes. Commit or stash first.",
                    )
            except Exception:
                # Git check failed, but don't block cleanup
                pass

        return True, None

    def _create_backup(self, files: list[Path]) -> BackupMetadata | None:
        """Create backup before file operations.

        Args:
            files: List of files to backup

        Returns:
            BackupMetadata if successful, None otherwise

        Examples:
            >>> service = ConfigCleanupService()
            >>> files = [Path("mypy.ini")]
            >>> metadata = service._create_backup(files)
            >>> assert metadata is not None
        """
        try:
            backup_id = self._generate_backup_id()
            backup_dir = self.backup_service.backup_root / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create backup archive
            backup_archive = backup_dir / "backup.tar.gz"

            with tarfile.open(backup_archive, "w:gz") as tar:
                for file_path in files:
                    if file_path.exists():
                        tar.add(file_path, arcname=file_path.name)

            # Create metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.now(),
                package_directory=self.pkg_path,
                backup_directory=backup_dir,
                total_files=len(files),
                total_size=sum(f.stat().st_size for f in files if f.exists()),
                checksum="",  # TODO: Generate proper checksum
                file_checksums={},  # TODO: Generate file checksums
            )

            self.console.print(
                f"[green]✅[/green] Backup created: {backup_archive.relative_to(self.pkg_path)}"
            )

            self.security_logger.log_security_event(
                SecurityEventType.BACKUP_CREATED,
                SecurityEventLevel.INFO,
                f"Config backup created: {backup_id}",
                backup_id=backup_id,
                files_backed=len(files),
            )

            return metadata

        except Exception as e:
            logger.exception(f"Backup creation failed: {e}")
            self.console.print(f"[red]❌[/red] Backup creation failed: {e}")
            return None

    def _merge_all_configs(
        self,
        config_files: list[Path],
        dry_run: bool,
    ) -> tuple[int, dict[str, str]]:
        """Merge all config files into pyproject.toml.

        Args:
            config_files: List of config files to merge
            dry_run: Preview without executing

        Returns:
            Tuple of (configs_merged_count, merged_files_dict)
        """
        merged_count = 0
        merged_files: dict[str, str] = {}

        # Load current pyproject.toml
        pyproject_path = self.pkg_path / "pyproject.toml"

        try:
            with open(pyproject_path, "rb") as f:
                pyproject_config = tomllib.load(f)
        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to load pyproject.toml: {e}")
            return 0, {}

        # Merge each config file
        for config_file in config_files:
            strategy = self._get_strategy_for_file(config_file.name)
            if not strategy:
                continue

            if dry_run:
                self.console.print(
                    f"[yellow]Would merge:[/yellow] {config_file.name} → [{strategy.target_section}]"
                )
                merged_count += 1
                merged_files[config_file.name] = strategy.target_section
                continue

            try:
                # Merge based on strategy type
                if strategy.merge_type == "ini_flatten":
                    pyproject_config = self._merge_ini_file(
                        config_file,
                        pyproject_config,
                        strategy.target_section,
                    )
                elif strategy.merge_type == "pattern_union":
                    pyproject_config = self._merge_pattern_file(
                        config_file,
                        pyproject_config,
                        strategy.target_section,
                    )
                elif strategy.merge_type == "json_deep":
                    pyproject_config = self._merge_json_file(
                        config_file,
                        pyproject_config,
                        strategy.target_section,
                    )
                elif strategy.merge_type == "ignore_list":
                    pyproject_config = self._merge_ignore_file(
                        config_file,
                        pyproject_config,
                        strategy.target_section,
                    )

                merged_count += 1
                merged_files[config_file.name] = strategy.target_section

                self.console.print(
                    f"[green]✅[/green] Merged: {config_file.name} → [{strategy.target_section}]"
                )

            except Exception as e:
                logger.exception(f"Failed to merge {config_file}: {e}")
                self.console.print(
                    f"[yellow]⚠️[/yellow] Failed to merge {config_file.name}: {e}"
                )

        # Write updated pyproject.toml
        if merged_count > 0 and not dry_run:
            try:
                from crackerjack.services.config_service import _dump_toml

                toml_content = _dump_toml(pyproject_config)
                with open(pyproject_path, "w") as f:
                    f.write(toml_content)

                self.console.print("[green]✅[/green] pyproject.toml updated")

            except Exception as e:
                logger.exception(f"Failed to write pyproject.toml: {e}")
                self.console.print(f"[red]❌[/red] Failed to write pyproject.toml: {e}")

        return merged_count, merged_files

    def _get_strategy_for_file(self, filename: str) -> MergeStrategy | None:
        """Get merge strategy for a specific file.

        Args:
            filename: Name of the config file

        Returns:
            MergeStrategy or None if no strategy found
        """
        for strategy in self._merge_strategies:
            if strategy.filename == filename:
                return strategy
        return None

    def _merge_ini_file(
        self,
        ini_file: Path,
        pyproject_config: dict,
        target_section: str,
    ) -> dict:
        """Merge INI file (e.g., mypy.ini) into pyproject.toml.

        Args:
            ini_file: Path to INI file
            pyproject_config: Current pyproject.toml config
            target_section: Target TOML section (e.g., "tool.mypy")

        Returns:
            Updated pyproject_config
        """
        # Parse INI file
        config = configparser.ConfigParser()
        config.read(ini_file)

        # Navigate to target section
        section_parts = target_section.split(".")
        current_section = pyproject_config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_section = section_parts[-1]

        # Create section if it doesn't exist
        if final_section not in current_section:
            current_section[final_section] = {}

        # Merge settings from INI file
        for section_name in config.sections():
            if section_name == "mypy":
                for key, value in config[section_name].items():
                    # Only add if not already present (existing wins)
                    if key not in current_section[final_section]:
                        # Convert value to appropriate type
                        current_section[final_section][key] = self._convert_ini_value(
                            value
                        )

        return pyproject_config

    def _convert_ini_value(self, value: str) -> str | bool | int:
        """Convert INI value string to appropriate type.

        Args:
            value: String value from INI file

        Returns:
            Converted value (str, bool, or int)
        """
        # Boolean conversion
        if value.lower() in ["true", "yes", "on"]:
            return True
        if value.lower() in ["false", "no", "off"]:
            return False

        # Integer conversion
        try:
            return int(value)
        except ValueError:
            pass

        return value

    def _merge_pattern_file(
        self,
        pattern_file: Path,
        pyproject_config: dict,
        target_section: str,
    ) -> dict:
        """Merge pattern file (e.g., .ruffignore) into pyproject.toml.

        Args:
            pattern_file: Path to pattern file
            pyproject_config: Current pyproject.toml config
            target_section: Target TOML section (e.g., "tool.ruff.extend-exclude")

        Returns:
            Updated pyproject_config
        """
        # Read patterns from file
        with open(pattern_file) as f:
            patterns = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        # Navigate to target section
        section_parts = target_section.split(".")
        current_section = pyproject_config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_key = section_parts[-1]

        # Get existing patterns
        existing_patterns = current_section.get(final_key, [])
        if isinstance(existing_patterns, str):
            existing_patterns = [existing_patterns]

        # Merge patterns with deduplication
        all_patterns = list(set(existing_patterns + patterns))

        # Update config
        current_section[final_key] = all_patterns

        return pyproject_config

    def _merge_json_file(
        self,
        json_file: Path,
        pyproject_config: dict,
        target_section: str,
    ) -> dict:
        """Deep merge JSON file (e.g., pyrightconfig.json) into pyproject.toml.

        Args:
            json_file: Path to JSON file
            pyproject_config: Current pyproject.toml config
            target_section: Target TOML section (e.g., "tool.pyright")

        Returns:
            Updated pyproject_config
        """
        # Read JSON config
        with open(json_file) as f:
            json_config = json.load(f)

        # Navigate to target section
        section_parts = target_section.split(".")
        current_section = pyproject_config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_section = section_parts[-1]

        # Create section if it doesn't exist
        if final_section not in current_section:
            current_section[final_section] = {}

        # Deep merge (existing values win)
        for key, value in json_config.items():
            if key not in current_section[final_section]:
                current_section[final_section][key] = value
            elif isinstance(value, list) and isinstance(
                current_section[final_section][key], list
            ):
                # Merge lists with deduplication
                merged = list(set(current_section[final_section][key] + value))
                current_section[final_section][key] = merged
            elif isinstance(value, dict) and isinstance(
                current_section[final_section][key], dict
            ):
                # Recursively merge dicts
                for subkey, subvalue in value.items():
                    if subkey not in current_section[final_section][key]:
                        current_section[final_section][key][subkey] = subvalue

        return pyproject_config

    def _merge_ignore_file(
        self,
        ignore_file: Path,
        pyproject_config: dict,
        target_section: str,
    ) -> dict:
        """Merge ignore file (e.g., .codespell-ignore) into pyproject.toml.

        Args:
            ignore_file: Path to ignore file
            pyproject_config: Current pyproject.toml config
            target_section: Target TOML section

        Returns:
            Updated pyproject_config
        """
        # Read ignore words
        with open(ignore_file) as f:
            ignore_words = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        # Navigate to target section
        section_parts = target_section.split(".")
        current_section = pyproject_config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_key = section_parts[-1]

        # Get existing words
        existing_words = current_section.get(final_key, "")
        if isinstance(existing_words, str):
            existing_words = existing_words.split(",")

        # Merge words with deduplication
        all_words = list(set(existing_words + ignore_words))

        # Update config
        current_section[final_key] = ",".join(all_words)

        return pyproject_config

    def _remove_standalone_configs(
        self,
        config_files: list[Path],
        dry_run: bool,
    ) -> int:
        """Remove standalone config files after successful merge.

        Args:
            config_files: List of config files to remove
            dry_run: Preview without executing

        Returns:
            Number of files removed
        """
        removed_count = 0

        # Files that should be removed (not just merged)
        files_to_remove = self.settings.config_cleanup.config_files_to_remove

        for config_file in config_files:
            # Check if file should be removed (vs just merged)
            if config_file.name not in files_to_remove:
                continue

            if dry_run:
                self.console.print(f"[yellow]Would remove:[/yellow] {config_file.name}")
                removed_count += 1
                continue

            try:
                # Validate path is safe
                if not self.path_validator.validate_safe_path(config_file):
                    self.console.print(
                        f"[red]❌[/red] Unsafe path detected: {config_file}"
                    )
                    continue

                # Atomic delete
                config_file.unlink()
                removed_count += 1

                self.console.print(f"[green]✅[/green] Removed: {config_file.name}")

            except Exception as e:
                logger.exception(f"Failed to remove {config_file}: {e}")
                self.console.print(
                    f"[yellow]⚠️[/yellow] Failed to remove {config_file.name}: {e}"
                )

        return removed_count

    def _cleanup_cache_dirs(
        self,
        cache_dirs: list[Path],
        dry_run: bool,
    ) -> int:
        """Remove cache directories.

        Args:
            cache_dirs: List of cache directories to clean
            dry_run: Preview without executing

        Returns:
            Number of directories cleaned
        """
        cleaned_count = 0

        for cache_dir in cache_dirs:
            if dry_run:
                self.console.print(
                    f"[yellow]Would clean:[/yellow] {cache_dir.relative_to(self.pkg_path)}/"
                )
                cleaned_count += 1
                continue

            try:
                # Validate path is safe
                if not self.path_validator.validate_safe_path(cache_dir):
                    self.console.print(
                        f"[red]❌[/red] Unsafe path detected: {cache_dir}"
                    )
                    continue

                # Remove directory tree
                shutil.rmtree(cache_dir)
                cleaned_count += 1

                self.console.print(
                    f"[green]✅[/green] Cleaned: {cache_dir.relative_to(self.pkg_path)}/"
                )

            except Exception as e:
                logger.exception(f"Failed to clean {cache_dir}: {e}")
                self.console.print(
                    f"[yellow]⚠️[/yellow] Failed to clean {cache_dir.name}: {e}"
                )

        return cleaned_count

    def _cleanup_output_files(
        self,
        output_files: list[Path],
        dry_run: bool,
    ) -> int:
        """Remove output files.

        Args:
            output_files: List of output files to clean
            dry_run: Preview without executing

        Returns:
            Number of files cleaned
        """
        cleaned_count = 0

        for output_file in output_files:
            if dry_run:
                self.console.print(f"[yellow]Would clean:[/yellow] {output_file.name}")
                cleaned_count += 1
                continue

            try:
                # Validate path is safe
                if not self.path_validator.validate_safe_path(output_file):
                    self.console.print(
                        f"[red]❌[/red] Unsafe path detected: {output_file}"
                    )
                    continue

                # Remove file
                output_file.unlink()
                cleaned_count += 1

                self.console.print(f"[green]✅[/green] Cleaned: {output_file.name}")

            except Exception as e:
                logger.exception(f"Failed to clean {output_file}: {e}")
                self.console.print(
                    f"[yellow]⚠️[/yellow] Failed to clean {output_file.name}: {e}"
                )

        return cleaned_count

    def _generate_summary(self, result: ConfigCleanupResult) -> str:
        """Generate human-readable summary of cleanup operation.

        Args:
            result: Cleanup operation result

        Returns:
            Formatted summary string

        Examples:
            >>> service = ConfigCleanupService()
            >>> result = ConfigCleanupResult(success=True, configs_merged=5)
            >>> summary = service._generate_summary(result)
            >>> assert "5 configs" in summary
        """
        lines = [
            f"Configs merged: {result.configs_merged}",
            f"Configs removed: {result.configs_removed}",
            f"Cache dirs cleaned: {result.cache_dirs_cleaned}",
            f"Output files cleaned: {result.output_files_cleaned}",
        ]

        if result.backup_metadata:
            lines.append(
                f"Backup location: {result.backup_metadata.backup_directory.relative_to(self.pkg_path)}"
            )

        # Add merged files breakdown
        if result.merged_files:
            lines.append("\nMerged files:")
            for filename, target_section in sorted(result.merged_files.items()):
                lines.append(f"  {filename} → [{target_section}]")

        return "\n".join(lines)

    def _generate_backup_id(self) -> str:
        """Generate unique backup ID from timestamp.

        Returns:
            Backup ID string (format: YYYYMMDD-HHMMSS)

        Examples:
            >>> service = ConfigCleanupService()
            >>> backup_id = service._generate_backup_id()
            >>> assert len(backup_id) == 17  # YYYYMMDD-HHMMSS format
        """
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def _smart_merge_gitignore(self, dry_run: bool) -> bool:
        """Smart merge .gitignore with standard Crackerjack patterns.

        This method uses ConfigMergeService.smart_merge_gitignore() to:
        1. Preserve existing user patterns
        2. Add standard Crackerjack patterns
        3. Remove duplicates
        4. Maintain Crackerjack section markers

        Args:
            dry_run: Preview changes without executing

        Returns:
            True if .gitignore was modified, False otherwise

        Examples:
            >>> service = ConfigCleanupService()
            >>> modified = service._smart_merge_gitignore(dry_run=True)
            >>> assert isinstance(modified, bool)
        """
        from crackerjack.services.config_merge import ConfigMergeService

        # Standard Crackerjack .gitignore patterns
        gitignore_patterns = [
            "# Build/Distribution",
            "/build/",
            "/dist/",
            "*.egg-info/",
            "",
            "# Caches",
            "__pycache__/",
            ".mypy_cache/",
            ".ruff_cache/",
            ".pytest_cache/",
            "",
            "# Coverage",
            ".coverage*",
            "htmlcov/",
            "",
            "# Development",
            ".venv/",
            ".DS_STORE",
            "*.pyc",
            "",
            "# Crackerjack specific",
            "crackerjack-debug-*.log",
            "crackerjack-ai-debug-*.log",
            ".crackerjack-*",
        ]

        gitignore_path = self.pkg_path / ".gitignore"

        # Check if .gitignore exists
        if not gitignore_path.exists():
            if dry_run:
                self.console.print(
                    "[yellow]Would create:[/yellow] .gitignore (with standard patterns)"
                )
                return True

            # Create new .gitignore
            try:
                gitignore_path.write_text("\n".join(gitignore_patterns))
                self.console.print("[green]✅[/green] Created: .gitignore (with standard patterns)")
                return True
            except Exception as e:
                logger.exception(f"Failed to create .gitignore: {e}")
                self.console.print(f"[red]❌[/red] Failed to create .gitignore: {e}")
                return False

        # Smart merge existing .gitignore
        if dry_run:
            self.console.print("[yellow]Would smart merge:[/yellow] .gitignore")
            return True

        try:
            # Capture original patterns BEFORE merge (for comparison)
            original_lines = gitignore_path.read_text().splitlines()
            original_patterns = set(
                l.strip()
                for l in original_lines
                if l.strip() and not l.strip().startswith("#")
            )

            # Use ConfigMergeService for smart merge
            config_merge_service = ConfigMergeService(
                console=self.console,
            )

            merged_content = config_merge_service.smart_merge_gitignore(
                patterns=gitignore_patterns,
                target_path=str(gitignore_path),
            )

            # Count new patterns
            merged_lines = merged_content.splitlines()
            merged_patterns = set(l.strip() for l in merged_lines if l.strip() and not l.strip().startswith("#"))

            new_patterns_count = len(merged_patterns) - len(original_patterns)
            total_patterns_count = len(merged_patterns)

            self.console.print(
                f"[green]✅[/green] Smart merged .gitignore "
                f"(new_patterns={new_patterns_count}, total={total_patterns_count})"
            )

            return new_patterns_count > 0

        except Exception as e:
            logger.exception(f"Failed to smart merge .gitignore: {e}")
            self.console.print(f"[yellow]⚠️[/yellow] Failed to smart merge .gitignore: {e}")
            return False

    def _display_completion(self, result: ConfigCleanupResult) -> None:
        """Display completion message to user.

        Args:
            result: Cleanup operation result
        """
        sep = "━" * 60

        if result.success:
            self.console.print(f"\n{sep}")
            if (
                result.configs_merged > 0
                or result.configs_removed > 0
                or result.cache_dirs_cleaned > 0
                or result.output_files_cleaned > 0
            ):
                self.console.print("[green]✅ Config cleanup completed[/green]")
                self.console.print(f"\n{result.summary}")
            else:
                self.console.print("[cyan]ℹ️ Config cleanup: No files to clean[/cyan]")
            self.console.print(f"{sep}\n")
        else:
            self.console.print(f"\n{sep}")
            self.console.print("[red]❌ Config cleanup failed[/red]")
            if result.error_message:
                self.console.print(f"Error: {result.error_message}")
            self.console.print(f"{sep}\n")
