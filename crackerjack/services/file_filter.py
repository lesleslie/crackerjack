import logging
import typing as t
from fnmatch import fnmatch
from pathlib import Path

from crackerjack.models.protocols import (
    GitServiceProtocol,
    ServiceProtocol,
    SmartFileFilterProtocol,
)

logger = logging.getLogger(__name__)


class SmartFileFilter(SmartFileFilterProtocol, ServiceProtocol):
    def __init__(
        self,
        git_service: GitServiceProtocol,
        project_root: Path | None = None,
        full_scan_threshold: int = 50,
    ) -> None:
        self._git_service = git_service
        self.project_root = project_root or Path.cwd()
        self.full_scan_threshold = full_scan_threshold

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def get_changed_files(self, since: str = "HEAD") -> list[Path]:
        files_str = self._git_service.get_changed_files_since(since, self.project_root)
        return [Path(f) for f in files_str]

    def get_staged_files(self) -> list[Path]:
        files_str = self._git_service.get_staged_files()
        return [Path(f) for f in files_str]

    def get_unstaged_files(self) -> list[Path]:
        files_str = self._git_service.get_unstaged_files()
        return [Path(f) for f in files_str]

    def filter_by_pattern(self, files: list[Path], pattern: str) -> list[Path]:
        return [
            file_path
            for file_path in files
            if fnmatch(file_path, pattern) or fnmatch(file_path.name, pattern)
        ]

    def filter_by_tool(self, files: list[Path], tool: str) -> list[Path]:
        tool_patterns = {
            "ruff-check": ["*.py"],
            "ruff-format": ["*.py"],
            "zuban": ["*.py"],
            "skylos": ["*.py"],
            "bandit": ["*.py"],
            "refurb": ["*.py"],
            "complexipy": ["*.py"],
            "creosote": ["*.py"],
            "mdformat": ["*.md"],
            "check-yaml": ["*.yaml", "*.yml"],
            "check-toml": ["*.toml"],
            "trailing-whitespace": ["*"],
            "end-of-file-fixer": ["*"],
            "codespell": ["*"],
            "validate-regex-patterns": ["*.py"],
            "gitleaks": ["*"],
            "uv-lock": ["pyproject.toml"],
            "check-added-large-files": ["*"],
        }

        patterns = tool_patterns.get(tool, ["*"])

        filtered = []
        for pattern in patterns:
            filtered.extend(self.filter_by_pattern(files, pattern))

        seen = set()
        result = []
        for file_path in filtered:
            if file_path not in seen:
                seen.add(file_path)
                result.append(file_path)

        return result

    def get_all_modified_files(self) -> list[Path]:
        staged = set(self.get_staged_files())
        unstaged = set(self.get_unstaged_files())
        all_modified = staged | unstaged

        return sorted(all_modified)

    def filter_by_extensions(
        self,
        files: list[Path],
        extensions: list[str],
    ) -> list[Path]:
        normalized = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

        return [file_path for file_path in files if file_path.suffix in normalized]

    def get_python_files(self, files: list[Path]) -> list[Path]:
        return self.filter_by_extensions(files, [".py"])

    def get_markdown_files(self, files: list[Path]) -> list[Path]:
        return self.filter_by_extensions(files, [".md"])

    def get_changed_python_files_incremental(
        self,
        base_branch: str = "main",
        since: str = "HEAD",
    ) -> list[Path]:
        try:
            if since == "HEAD":
                changed = self.get_changed_files(since=base_branch)
            else:
                changed = self.get_changed_files(since=since)

            python_files = [f for f in changed if f.suffix == ".py"]

            logger.debug(
                f"Incremental scan detected {len(python_files)} changed Python files "
                f"(threshold: {self.full_scan_threshold})"
            )

            if len(python_files) > self.full_scan_threshold:
                logger.info(
                    f"Too many files changed ({len(python_files)} > {self.full_scan_threshold}), "
                    "falling back to full package scan"
                )
                return []

            return python_files

        except Exception as e:
            logger.warning(
                f"Failed to detect changed files: {e}, falling back to full scan"
            )
            return []

    def get_all_python_files_in_package(
        self,
        package_dir: Path | None = None,
    ) -> list[Path]:
        package_dir = package_dir or self.project_root

        try:
            python_files = list(package_dir.rglob("*.py"))

            non_test_files = [
                f
                for f in python_files
                if not any(
                    part.startswith("test_") or part == "tests" for part in f.parts
                )
            ]

            logger.debug(f"Full scan found {len(non_test_files)} Python files")

            return non_test_files

        except Exception as e:
            logger.error(f"Failed to collect Python files: {e}")
            return []

    def should_include(self, file_path: Path) -> bool:

        if any(part.startswith("test_") or part == "tests" for part in file_path.parts):
            return False

        if any(part.startswith(".") for part in file_path.parts):
            return False

        return file_path.suffix == ".py"

    def filter_files(self, files: list[Path]) -> list[Path]:
        return [f for f in files if self.should_include(f)]

    def should_use_incremental_scan(
        self,
        base_branch: str = "main",
    ) -> bool:
        changed_files = self.get_changed_python_files_incremental(base_branch)

        if not changed_files:
            try:
                all_changed = self.get_changed_files(since=base_branch)
                return len(all_changed) <= self.full_scan_threshold
            except Exception:
                return False

        return True

    def get_files_for_qa_scan(
        self,
        package_dir: Path | None = None,
        base_branch: str = "main",
        force_incremental: bool = False,
        force_full: bool = False,
    ) -> list[Path]:
        package_dir = package_dir or self.project_root

        if force_full:
            logger.info("Forced full scan requested")
            return self.get_all_python_files_in_package(package_dir)

        if force_incremental:
            logger.info("Forced incremental scan requested")
            return self.get_changed_python_files_incremental(base_branch)

        if self.should_use_incremental_scan(base_branch):
            changed_files = self.get_changed_python_files_incremental(base_branch)

            if not changed_files:
                logger.info("No Python files changed, skipping QA scan")
                return []

            total_files = len(self.get_all_python_files_in_package(package_dir))

            logger.info(
                f"Using incremental QA scan: {len(changed_files)} changed files "
                f"(vs {total_files} total files) - {100 * len(changed_files) / total_files:.1f}% reduction"
            )

            return changed_files

        logger.info("Auto-detection: using full package scan")
        return self.get_all_python_files_in_package(package_dir)
