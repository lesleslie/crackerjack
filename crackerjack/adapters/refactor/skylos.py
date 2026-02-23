from __future__ import annotations

import json
import logging
import typing as t
from pathlib import Path
from uuid import UUID

from crackerjack.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig
    from crackerjack.services.file_filter import SmartFileFilter


MODULE_ID = UUID("445401b8-b273-47f1-9015-22e721757d46")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class SkylosSettings(ToolAdapterSettings):
    tool_name: str = "skylos"
    use_json_output: bool = True
    confidence_threshold: int = 86
    web_dashboard_port: int = 5090
    use_diff_base: bool = True

    allowed_duplicate_methods: set[str] = {
        "__init__",
        "__new__",
        "__repr__",
        "__str__",
        "__eq__",
        "__hash__",
        "__len__",
        "__iter__",
        "__next__",
        "__enter__",
        "__exit__",
        "__call__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__contains__",
        "__bool__",
        "__aiter__",
        "__anext__",
        "__aenter__",
        "__aexit__",
        "to_searchable_text",
        "to_dict",
        "from_dict",
        "validate",
        "process",
        "handle",
        "run",
        "execute",
        "cleanup",
        "setup",
        "teardown",
        "configure",
        "initialize",
        "start",
        "stop",
        "reset",
        "clear",
        "close",
        "flush",
        "serialize",
        "deserialize",
        "encode",
        "decode",
        "parse",
        "format",
        "render",
        "accept",
        "visit",
    }

    exclude_folders: list[str] = [
        "tests",
        "docs",
        "scripts",
        "examples",
        "archive",
        "assets",
        "templates",
        "tools",
        "worktrees",
        "settings",
        ".venv",
        "venv",
        "build",
        "dist",
        "htmlcov",
        "logs",
        "node_modules",
    ]


class SkylosAdapter(BaseToolAdapter):
    settings: SkylosSettings | None = None

    def __init__(
        self,
        settings: SkylosSettings | None = None,
        file_filter: SmartFileFilter | None = None,
    ) -> None:
        super().__init__(settings=settings)
        self.file_filter = file_filter
        logger.debug(
            "SkylosAdapter initialized",
            extra={
                "has_settings": settings is not None,
                "has_file_filter": file_filter is not None,
            },
        )

    async def init(self) -> None:
        if not self.settings:
            timeout_seconds = self._get_timeout_from_settings()

            self.settings = SkylosSettings(
                timeout_seconds=timeout_seconds,
                max_workers=4,
            )
            logger.info("Using default SkylosSettings")
        await super().init()
        logger.debug(
            "SkylosAdapter initialization complete",
            extra={
                "confidence_threshold": self.settings.confidence_threshold,
                "timeout_seconds": self.settings.timeout_seconds,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Skylos (Dead Code)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "skylos"

    def build_command(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        venv_skylos = Path.cwd() / ".venv" / "bin" / "skylos"
        if venv_skylos.exists():
            cmd = [str(venv_skylos)]
        else:
            cmd = ["uv", "run", "skylos"]

        cmd.extend(["--confidence", str(self.settings.confidence_threshold)])

        if self.settings.use_json_output:
            cmd.append("--json")

        for folder in self.settings.exclude_folders:
            cmd.extend(["--exclude-folder", folder])

        if self.settings.use_diff_base and self._is_git_repo():
            default_branch = self._get_default_branch()
            if default_branch:
                cmd.extend(["--diff-base", default_branch])

        if files is None and self.file_filter:
            files = self.file_filter.get_files_for_qa_scan(
                package_dir=Path.cwd(),
                force_incremental=getattr(self.settings, "incremental_mode", False),
            )

        if files:
            cmd.extend([str(f) for f in files])
            target = " ".join(str(f) for f in files)
        else:
            target = self._determine_scan_target(files or [])
            cmd.append(target)

        logger.info(
            "Built Skylos command",
            extra={
                "file_count": len(files) if files else 1,
                "confidence_threshold": self.settings.confidence_threshold,
                "target_directory": target,
                "exclude_folders": self.settings.exclude_folders,
                "incremental_mode": self.file_filter is not None,
                "using_venv_path": venv_skylos.exists(),
                "using_diff_base": self.settings.use_diff_base and self._is_git_repo(),
            },
        )
        return cmd

    def _is_git_repo(self) -> bool:
        return (Path.cwd() / ".git").exists()

    def _get_default_branch(self) -> str | None:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("/")[-1]
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        for branch in ["main", "master", "develop"]:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return f"origin/{branch}"

        return None

    def _determine_scan_target(self, files: list[Path]) -> str:
        if files:
            return " ".join(str(f) for f in files)

        package_name = self._detect_package_name()
        return f"./{package_name}"

    def _detect_package_name(self) -> str:
        cwd = Path.cwd()

        package_name = self._read_package_from_toml(cwd)
        if package_name:
            return package_name

        package_name = self._find_package_directory(cwd)
        if package_name:
            return package_name

        return "crackerjack"

    def _detect_package_directory(self, cwd: Path) -> str | None:
        return self._find_package_directory(cwd)

    def _read_package_from_toml(self, cwd: Path) -> str | None:
        import tomllib
        from contextlib import suppress

        pyproject_path = cwd / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        with suppress(Exception), pyproject_path.open("rb") as f:
            data = tomllib.load(f)
            project_name = data.get("project", {}).get("name")
            if project_name:
                return project_name.replace("-", "_")

        return None

    def _find_package_directory(self, cwd: Path) -> str | None:
        excluded = {
            "tests",
            "docs",
            "scripts",
            "examples",
            "archive",
            "assets",
            "templates",
            "tools",
            "worktrees",
            "settings",
            ".venv",
            "venv",
            "build",
            "dist",
            "htmlcov",
            "logs",
        }

        for item in cwd.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                if item.name not in excluded:
                    return item.name

        return None

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            issues = self._parse_json_output(result.raw_output)
        except json.JSONDecodeError:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"output_preview": result.raw_output[:200]},
            )
            issues = self._parse_text_output(result.raw_output)

        issues = self._filter_false_positive_duplicates(issues)

        logger.info(
            "Parsed Skylos output",
            extra={
                "total_issues": len(issues),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _filter_false_positive_duplicates(
        self, issues: list[ToolIssue]
    ) -> list[ToolIssue]:
        if not self.settings:
            return issues

        allowed = self.settings.allowed_duplicate_methods
        filtered = []

        for issue in issues:
            if "Duplicate definition" in issue.message:
                import re

                match = re.search(r"Duplicate definition '(\w+)'", issue.message)
                if match:
                    method_name = match.group(1)
                    if method_name in allowed:
                        logger.debug(
                            f"Filtering false positive duplicate: {method_name} in {issue.file_path}"
                        )
                        continue

            filtered.append(issue)

        return filtered

    def _parse_json_output(self, output: str) -> list[ToolIssue]:
        data = json.loads(output)
        logger.debug(
            "Parsed Skylos JSON output",
            extra={"results_count": len(data.get("dead_code", []))},
        )

        issues = []
        for item in data.get("dead_code", []):
            issue = self._create_issue_from_json(item)
            issues.append(issue)

        return issues

    def _create_issue_from_json(self, item: dict) -> ToolIssue:
        file_path = Path(item.get("file", ""))
        code_type = item.get("type", "code")
        code_name = item.get("name", "")
        confidence = item.get("confidence", "unknown")

        return ToolIssue(
            file_path=file_path,
            line_number=item.get("line"),
            message=f"Dead {code_type}: {code_name}",
            code=code_type,
            severity="warning",
            suggestion=f"Confidence: {confidence}%",
        )

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or ":" not in line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Skylos text output (fallback)",
            extra={"total_issues": len(issues)},
        )
        return issues

    def _parse_text_line(self, line: str) -> ToolIssue | None:
        try:
            parts = line.split(":", 2)
            if len(parts) < 3:
                return None

            file_path = Path(parts[0].strip())
            line_number = self._parse_line_number(parts[1])
            message_part = parts[2].strip()

            confidence = self._extract_confidence_from_message(message_part)

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                message=message_part,
                severity="warning",
                suggestion=f"Confidence: {confidence}",
            )

        except (ValueError, IndexError):
            return None

    def _parse_line_number(self, line_part: str) -> int | None:
        try:
            return int(line_part.strip())
        except ValueError:
            return None

    def _extract_confidence_from_message(self, message_part: str) -> str:
        if "(confidence:" not in message_part:
            return "unknown"

        conf_start = message_part.find("(confidence:") + len("(confidence:")
        conf_end = message_part.find(")", conf_start)
        if conf_end != -1:
            return message_part[conf_start:conf_end].strip()

        return "unknown"

    def _get_check_type(self) -> QACheckType:
        return QACheckType.REFACTOR

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        package_dir = self._detect_package_directory(Path.cwd())

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.REFACTOR,
            enabled=True,
            file_patterns=[f"{package_dir}/**/*.py"],
            exclude_patterns=[
                "**/test_*.py",
                "**/tests/**",
                "**/scripts/**",
                "**/examples/**",
                "**/archive/**",
                "**/assets/**",
                "**/templates/**",
                "**/tools/**",
                "**/worktrees/**",
                "**/settings/**",
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
                "**/__pycache__/**",
                "**/.git/**",
                "**/node_modules/**",
                "**/.tox/**",
                "**/.pytest_cache/**",
                "**/htmlcov/**",
                "**/logs/**",
                "**/.coverage*",
            ],
            timeout_seconds=300,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "confidence_threshold": 86,
                "web_dashboard_port": 5090,
            },
        )
