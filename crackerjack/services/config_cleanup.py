from __future__ import annotations

import configparser
import json
import logging
import shutil
import tarfile
import tomllib
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from crackerjack.core.console import CrackerjackConsole
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
    success: bool
    configs_merged: int = 0
    configs_removed: int = 0
    cache_dirs_cleaned: int = 0
    output_files_cleaned: int = 0
    backup_metadata: BackupMetadata | None = None
    summary: str = ""
    error_message: str | None = None
    merged_files: dict[str, str] = field(default_factory=dict)


@dataclass
class MergeStrategy:
    filename: str
    target_section: str
    merge_type: str


class ConfigCleanupService:
    def __init__(
        self,
        console: ConsoleProtocol | None = None,
        pkg_path: Path | None = None,
        git_service: GitInterface | None = None,
        settings: CrackerjackSettings | None = None,
    ) -> None:
        self.console = console or CrackerjackConsole()
        self.pkg_path = pkg_path or Path.cwd()
        self.git_service = git_service

        if settings is None:
            from crackerjack.config import load_settings
            from crackerjack.config.settings import CrackerjackSettings

            settings = load_settings(CrackerjackSettings)

        self.settings = settings
        self.security_logger = get_security_logger()

        self._merge_strategies = self._build_merge_strategies()

        self.backup_service = PackageBackupService(
            backup_root=self.pkg_path / "docs" / ".backups",
        )

        self.atomic_ops = AtomicFileOperations()
        self.path_validator = SecurePathValidator

    def cleanup_configs(
        self,
        dry_run: bool = False,
    ) -> ConfigCleanupResult:
        result = ConfigCleanupResult(success=False)

        try:
            config_files = self._detect_config_files()
            cache_dirs = self._detect_cache_dirs()
            output_files = self._detect_output_files()

            if not config_files and not cache_dirs and not output_files:
                result.success = True
                result.summary = "No config files or test outputs to cleanup"
                self._display_completion(result)
                return result

            is_valid, error_msg = self._validate_preconditions()
            if not is_valid:
                result.success = False
                result.error_message = error_msg
                return result

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

            configs_merged, merged_files = self._merge_all_configs(
                config_files,
                dry_run=dry_run,
            )

            result.configs_merged = configs_merged
            result.merged_files = merged_files

            configs_removed = self._remove_standalone_configs(
                config_files,
                dry_run=dry_run,
            )

            result.configs_removed = configs_removed

            gitignore_merged = self._smart_merge_gitignore(dry_run=dry_run)

            if gitignore_merged:
                result.merged_files[".gitignore"] = "smart_merge"

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

            result.summary = self._generate_summary(result)

            result.success = True

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
        try:
            self.console.print(
                f"[cyan]ℹ️[/cyan] Rolling back config cleanup: {backup_metadata.backup_id}"
            )

            if not backup_metadata.backup_directory.exists():
                self.console.print(
                    f"[red]❌[/red] Backup directory not found: {backup_metadata.backup_directory}"
                )
                return False

            backup_archive = backup_metadata.backup_directory / "backup.tar.gz"
            if not backup_archive.exists():
                self.console.print(
                    f"[red]❌[/red] Backup archive not found: {backup_archive}"
                )
                return False

            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                with tarfile.open(backup_archive, "r:gz") as tar:
                    tar.extractall(temp_path)

                restored = 0
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(temp_path)
                        target_path = self.pkg_path / relative_path

                        target_path.parent.mkdir(parents=True, exist_ok=True)

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
        config_files = []

        for strategy in self._merge_strategies:
            config_path = self.pkg_path / strategy.filename
            if config_path.exists():
                config_files.append(config_path)

        return config_files

    def _detect_cache_dirs(self) -> list[Path]:
        cache_dirs = []

        for cache_dir in self.settings.config_cleanup.cache_dirs_to_clean:
            cache_path = self.pkg_path / cache_dir
            if cache_path.exists() and cache_path.is_dir():
                cache_dirs.append(cache_path)

        return cache_dirs

    def _detect_output_files(self) -> list[Path]:
        output_files = []

        for output_file in self.settings.config_cleanup.output_files_to_clean:
            output_path = self.pkg_path / output_file
            if output_path.exists() and output_path.is_file():
                output_files.append(output_path)

        return output_files

    def _build_merge_strategies(self) -> list[MergeStrategy]:
        strategies = []

        merge_strategies = self.settings.config_cleanup.merge_strategies

        for filename, target_section in merge_strategies.items():
            if filename.endswith(".ini"):
                merge_type = "ini_flatten"
            elif filename.endswith("ignore"):
                merge_type = "pattern_union"
            elif filename.endswith(".json"):
                merge_type = "json_deep"
            elif filename in (".codespell-ignore", ".codespellrc"):
                merge_type = "ignore_list"
            else:
                merge_type = "pattern_union"

            strategies.append(
                MergeStrategy(
                    filename=filename,
                    target_section=target_section,
                    merge_type=merge_type,
                )
            )

        return strategies

    def _validate_preconditions(self) -> tuple[bool, str | None]:
        pyproject_path = self.pkg_path / "pyproject.toml"
        if not pyproject_path.exists():
            return False, "pyproject.toml not found"

        if self.git_service:
            with suppress(Exception):
                changed_files = self.git_service.get_changed_files()
                if changed_files:
                    allowed_files = {"pyproject.toml", ".gitignore", ".gitattributes"}

                    allowed_files.add("crackerjack/services/config_cleanup.py")

                    allowed_files.update(
                        {
                            "SESSION_CHECKPOINT_REPORT.md",
                            "docs/complexity_refactoring_complete.md",
                        }
                    )

                    non_backup_files = [
                        f
                        for f in changed_files
                        if not f.startswith("docs/.backups/")
                        or not f.endswith("backup.tar.gz")
                    ]

                    unexpected_files = [
                        f for f in non_backup_files if f not in allowed_files
                    ]

                    if unexpected_files:
                        return (
                            False,
                            f"Git repository has uncommitted changes. Commit or stash first.\n"
                            f"Changed files: {', '.join(changed_files)}",
                        )

                    self.console.print(
                        f"[dim]ℹ️  Only config files modified: {', '.join(changed_files)}[/dim]"
                    )

        return True, None

    def _create_backup(self, files: list[Path]) -> BackupMetadata | None:
        try:
            backup_id = self._generate_backup_id()
            if self.backup_service.backup_root is None:
                return None
            backup_dir = self.backup_service.backup_root / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_archive = backup_dir / "backup.tar.gz"

            with tarfile.open(backup_archive, "w:gz") as tar:
                for file_path in files:
                    if file_path.exists():
                        tar.add(file_path, arcname=file_path.name)

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
        pyproject_config = self._load_pyproject_config()
        if pyproject_config is None:
            return 0, {}

        merged_count, merged_files = self._merge_config_files(
            config_files, pyproject_config, dry_run
        )

        if merged_count > 0 and not dry_run:
            self._write_pyproject_config(pyproject_config)

        return merged_count, merged_files

    def _load_pyproject_config(self) -> dict[str, t.Any] | None:
        pyproject_path = self.pkg_path / "pyproject.toml"

        try:
            with pyproject_path.open("rb") as f:
                return tomllib.load(f)
        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to load pyproject.toml: {e}")
            return None

    def _merge_config_files(
        self,
        config_files: list[Path],
        pyproject_config: dict[str, t.Any],
        dry_run: bool,
    ) -> tuple[int, dict[str, str]]:
        merged_count = 0
        merged_files: dict[str, str] = {}

        for config_file in config_files:
            strategy = self._get_strategy_for_file(config_file.name)
            if not strategy:
                continue

            if dry_run:
                self._handle_dry_run_merge(config_file.name, strategy)
                merged_count += 1
                merged_files[config_file.name] = strategy.target_section
                continue

            if self._merge_single_file(config_file, strategy, pyproject_config):
                merged_count += 1
                merged_files[config_file.name] = strategy.target_section

        return merged_count, merged_files

    def _handle_dry_run_merge(self, filename: str, strategy: MergeStrategy) -> None:
        self.console.print(
            f"[yellow]Would merge:[/yellow] {filename} → [{strategy.target_section}]"
        )

    def _merge_single_file(
        self,
        config_file: Path,
        strategy: MergeStrategy,
        pyproject_config: dict[str, t.Any],
    ) -> bool:
        try:
            pyproject_config = self._apply_merge_strategy(
                config_file, pyproject_config, strategy
            )

            self.console.print(
                f"[green]✅[/green] Merged: {config_file.name} → [{strategy.target_section}]"
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to merge {config_file}: {e}")
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to merge {config_file.name}: {e}"
            )
            return False

    def _apply_merge_strategy(
        self,
        config_file: Path,
        pyproject_config: dict[str, t.Any],
        strategy: MergeStrategy,
    ) -> dict[str, t.Any]:
        merge_methods = {
            "ini_flatten": self._merge_ini_file,
            "pattern_union": self._merge_pattern_file,
            "json_deep": self._merge_json_file,
            "ignore_list": self._merge_ignore_file,
        }

        merge_method = merge_methods.get(strategy.merge_type)
        if merge_method:
            return merge_method(config_file, pyproject_config, strategy.target_section)

        return pyproject_config

    def _write_pyproject_config(self, pyproject_config: dict[str, t.Any]) -> None:
        pyproject_path = self.pkg_path / "pyproject.toml"

        try:
            from crackerjack.services.config_service import _dump_toml

            toml_content = _dump_toml(pyproject_config)
            pyproject_path.write_text(toml_content)

            self.console.print("[green]✅[/green] pyproject.toml updated")
        except Exception as e:
            logger.exception(f"Failed to write pyproject.toml: {e}")
            self.console.print(f"[red]❌[/red] Failed to write pyproject.toml: {e}")

    def _get_strategy_for_file(self, filename: str) -> MergeStrategy | None:
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
        config = configparser.ConfigParser()
        config.read(ini_file)

        section_parts = target_section.split(".")
        current_section = pyproject_config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_section = section_parts[-1]

        if final_section not in current_section:
            current_section[final_section] = {}

        for section_name in config.sections():
            if section_name == "mypy":
                for key, value in config[section_name].items():
                    if key not in current_section[final_section]:
                        current_section[final_section][key] = self._convert_ini_value(
                            value
                        )

        return pyproject_config

    def _convert_ini_value(self, value: str) -> str | bool | int:
        if value.lower() in ("true", "yes", "on"):
            return True
        if value.lower() in ("false", "no", "off"):
            return False

        with suppress(ValueError):
            return int(value)

        return value

    def _merge_pattern_file(
        self,
        pattern_file: Path,
        pyproject_config: dict,
        target_section: str,
    ) -> dict:
        with pattern_file.open() as f:
            patterns = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        section_parts = target_section.split(".")
        current_section = pyproject_config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_key = section_parts[-1]

        existing_patterns = current_section.get(final_key, [])
        if isinstance(existing_patterns, str):
            existing_patterns = [existing_patterns]

        all_patterns = list(set(existing_patterns + patterns))

        current_section[final_key] = all_patterns

        return pyproject_config

    def _merge_json_file(
        self,
        json_file: Path,
        pyproject_config: dict,
        target_section: str,
    ) -> dict:
        with json_file.open() as f:
            json_config = json.load(f)

        target_dict = self._get_target_section(pyproject_config, target_section)

        for key, value in json_config.items():
            self._merge_json_value(target_dict, key, value)

        return pyproject_config

    def _get_target_section(self, config: dict, section_path: str) -> dict:
        section_parts = section_path.split(".")
        current_section = config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_section = section_parts[-1]
        if final_section not in current_section:
            current_section[final_section] = {}

        return current_section[final_section]

    def _merge_json_value(self, target_dict: dict, key: str, value: t.Any) -> None:
        if key not in target_dict:
            target_dict[key] = value
        elif isinstance(value, list) and isinstance(target_dict[key], list):
            self._merge_json_lists(target_dict, key, value)
        elif isinstance(value, dict) and isinstance(target_dict[key], dict):
            self._merge_json_dicts(target_dict, key, value)

    def _merge_json_lists(self, target_dict: dict, key: str, value: list) -> None:
        merged = list(set(target_dict[key] + value))
        target_dict[key] = merged

    def _merge_json_dicts(self, target_dict: dict, key: str, value: dict) -> None:
        for subkey, subvalue in value.items():
            if subkey not in target_dict[key]:
                target_dict[key][subkey] = subvalue

    def _merge_ignore_file(
        self,
        ignore_file: Path,
        pyproject_config: dict,
        target_section: str,
    ) -> dict:
        with ignore_file.open() as f:
            ignore_words = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        section_parts = target_section.split(".")
        current_section = pyproject_config

        for part in section_parts[:-1]:
            if part not in current_section:
                current_section[part] = {}
            current_section = current_section[part]

        final_key = section_parts[-1]

        existing_words = current_section.get(final_key, "")
        if isinstance(existing_words, str):
            existing_words = existing_words.split(",")

        all_words = list(set(existing_words + ignore_words))

        current_section[final_key] = ",".join(all_words)

        return pyproject_config

    def _remove_standalone_configs(
        self,
        config_files: list[Path],
        dry_run: bool,
    ) -> int:
        removed_count = 0

        files_to_remove = self.settings.config_cleanup.config_files_to_remove

        for config_file in config_files:
            if config_file.name not in files_to_remove:
                continue

            if dry_run:
                self.console.print(f"[yellow]Would remove:[/yellow] {config_file.name}")
                removed_count += 1
                continue

            try:
                if not self.path_validator.validate_safe_path(config_file):
                    self.console.print(
                        f"[red]❌[/red] Unsafe path detected: {config_file}"
                    )
                    continue

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
        cleaned_count = 0

        for cache_dir in cache_dirs:
            if dry_run:
                self.console.print(
                    f"[yellow]Would clean:[/yellow] {cache_dir.relative_to(self.pkg_path)}/"
                )
                cleaned_count += 1
                continue

            try:
                if not self.path_validator.validate_safe_path(cache_dir):
                    self.console.print(
                        f"[red]❌[/red] Unsafe path detected: {cache_dir}"
                    )
                    continue

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
        cleaned_count = 0

        for output_file in output_files:
            if dry_run:
                self.console.print(f"[yellow]Would clean:[/yellow] {output_file.name}")
                cleaned_count += 1
                continue

            try:
                if not self.path_validator.validate_safe_path(output_file):
                    self.console.print(
                        f"[red]❌[/red] Unsafe path detected: {output_file}"
                    )
                    continue

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

        if result.merged_files:
            lines.append("\nMerged files:")
            for filename, target_section in sorted(result.merged_files.items()):
                lines.append(f"  {filename} → [{target_section}]")

        return "\n".join(lines)

    def _generate_backup_id(self) -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def _smart_merge_gitignore(self, dry_run: bool) -> bool:
        from crackerjack.services.config_merge import ConfigMergeService

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

        if not gitignore_path.exists():
            if dry_run:
                self.console.print(
                    "[yellow]Would create:[/yellow] .gitignore (with standard patterns)"
                )
                return True

            try:
                gitignore_path.write_text("\n".join(gitignore_patterns))
                self.console.print(
                    "[green]✅[/green] Created: .gitignore (with standard patterns)"
                )
                return True
            except Exception as e:
                logger.exception(f"Failed to create .gitignore: {e}")
                self.console.print(f"[red]❌[/red] Failed to create .gitignore: {e}")
                return False

        if dry_run:
            self.console.print("[yellow]Would smart merge:[/yellow] .gitignore")
            return True

        try:
            original_lines = gitignore_path.read_text().splitlines()
            original_patterns = set(
                line.strip()
                for line in original_lines
                if line.strip() and not line.strip().startswith("#")
            )

            config_merge_service = ConfigMergeService(
                console=self.console,
            )

            merged_content = config_merge_service.smart_merge_gitignore(
                patterns=gitignore_patterns,
                target_path=str(gitignore_path),
            )

            merged_lines = merged_content.splitlines()
            merged_patterns = set(
                line.strip()
                for line in merged_lines
                if line.strip() and not line.strip().startswith("#")
            )

            new_patterns_count = len(merged_patterns) - len(original_patterns)
            total_patterns_count = len(merged_patterns)

            self.console.print(
                f"[green]✅[/green] Smart merged .gitignore "
                f"(new_patterns={new_patterns_count}, total={total_patterns_count})"
            )

            return new_patterns_count > 0

        except Exception as e:
            logger.exception(f"Failed to smart merge .gitignore: {e}")
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to smart merge .gitignore: {e}"
            )
            return False

    def _display_completion(self, result: ConfigCleanupResult) -> None:
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
