from __future__ import annotations

import json
import logging
import shutil
import typing as t
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from crackerjack.adapters._output_paths import AdapterOutputPaths
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


MODULE_ID = UUID("33a3f9ff-5fd2-43f5-a6c9-a43917618a17")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class ComplexipySettings(ToolAdapterSettings):
    tool_name: str = "complexipy"
    use_json_output: bool = True
    max_complexity: int = 15
    include_cognitive: bool = True
    include_maintainability: bool = True
    sort_by: str = "desc"


class ComplexipyAdapter(BaseToolAdapter):
    settings: ComplexipySettings | None = None

    def __init__(self, settings: ComplexipySettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "ComplexipyAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        if not self.settings:
            config_data = self._load_config_from_pyproject()
            max_complexity = config_data.get("max_complexity", 15)
            self.settings = ComplexipySettings(
                max_complexity=max_complexity,
                timeout_seconds=90,
                max_workers=4,
            )
            logger.info(
                "Using default ComplexipySettings",
                extra={"max_complexity": max_complexity},
            )
        await super().init()
        logger.debug(
            "ComplexipyAdapter initialization complete",
            extra={
                "max_complexity": self.settings.max_complexity,
                "include_cognitive": self.settings.include_cognitive,
                "include_maintainability": self.settings.include_maintainability,
                "sort_by": self.settings.sort_by,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Complexipy (Complexity)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "complexipy"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if self.settings.use_json_output:
            cmd.append("--output-json")

        config_data = self._load_config_from_pyproject()
        max_complexity = config_data.get("max_complexity", self.settings.max_complexity)
        cmd.extend(["--max-complexity-allowed", str(max_complexity)])

        cmd.extend(["--sort", self.settings.sort_by])

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Complexipy command",
            extra={
                "file_count": len(files),
                "max_complexity": max_complexity,
                "include_cognitive": self.settings.include_cognitive,
                "include_maintainability": self.settings.include_maintainability,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        json_file = self._move_complexipy_results_to_output_dir()

        if (
            self.settings
            and self.settings.use_json_output
            and json_file
            and json_file.exists()
        ):
            try:
                with json_file.open() as f:
                    data = json.load(f)
                logger.debug(
                    "Read Complexipy JSON file",
                    extra={
                        "file": str(json_file),
                        "entries": len(data) if isinstance(data, list) else "N/A",
                    },
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(
                    "Failed to read JSON file, falling back to stdout parsing",
                    extra={"error": str(e), "file": str(json_file)},
                )
                return self._parse_text_output(result.raw_output)
        else:
            if not result.raw_output:
                logger.debug("No output to parse")
                return []

            try:
                data = json.loads(result.raw_output)
                logger.debug(
                    "Parsed Complexipy JSON from stdout",
                    extra={"entries": len(data) if isinstance(data, list) else "N/A"},
                )
            except json.JSONDecodeError as e:
                logger.debug(
                    "JSON parse failed, falling back to text parsing",
                    extra={"error": str(e), "output_preview": result.raw_output[:200]},
                )
                return self._parse_text_output(result.raw_output)

        issues = self._process_complexipy_data(data)

        logger.info(
            "Parsed Complexipy output",
            extra={
                "total_issues": len(issues),
                "high_complexity": sum(1 for i in issues if i.severity == "error"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _process_complexipy_data(self, data: list | dict) -> list[ToolIssue]:
        issues: list[ToolIssue] = []

        if not self.settings:
            logger.warning("Settings not initialized, cannot parse JSON")
            return issues

        if isinstance(data, list):
            for func in data:
                complexity = func.get("complexity", 0)
                if complexity <= self.settings.max_complexity:
                    continue

                file_path = Path(func.get("path", ""))
                function_name = func.get("function_name", "unknown")
                severity = (
                    "error"
                    if complexity > self.settings.max_complexity * 2
                    else "warning"
                )

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=None,
                    message=f"Function '{function_name}' - Complexity: {complexity}",
                    code="COMPLEXITY",
                    severity=severity,
                    suggestion=f"Consider refactoring to reduce complexity below {self.settings.max_complexity}",
                )
                issues.append(issue)
            return issues

        for file_data in data.get("files", []):
            file_path = Path(file_data.get("path", ""))
            issues.extend(
                self._process_file_data(file_path, file_data.get("functions", []))
            )
        return issues

    def _process_file_data(
        self, file_path: Path, functions: list[dict]
    ) -> list[ToolIssue]:
        issues = []
        for func in functions:
            issue = self._create_issue_if_needed(file_path, func)
            if issue:
                issues.append(issue)
        return issues

    def _create_issue_if_needed(self, file_path: Path, func: dict) -> ToolIssue | None:
        if not self.settings:
            return None

        complexity = func.get("complexity", 0)

        if complexity <= self.settings.max_complexity:
            return None

        message = self._build_issue_message(func, complexity)
        severity = self._determine_issue_severity(complexity)

        return ToolIssue(
            file_path=file_path,
            line_number=func.get("line"),
            message=message,
            code="COMPLEXITY",
            severity=severity,
            suggestion=f"Consider refactoring to reduce complexity below {self.settings.max_complexity}",
        )

    def _build_issue_message(self, func: dict, complexity: int) -> str:
        message_parts = [f"Complexity: {complexity}"]

        if self.settings and self.settings.include_cognitive:
            cognitive = func.get("cognitive_complexity", 0)
            message_parts.append(f"Cognitive: {cognitive}")

        if self.settings and self.settings.include_maintainability:
            maintainability = func.get("maintainability", 100)
            message_parts.append(f"Maintainability: {maintainability:.1f}")

        return f"Function '{func.get('name', 'unknown')}' - " + ", ".join(message_parts)

    def _determine_issue_severity(self, complexity: int) -> str:
        if not self.settings:
            return "warning"

        if complexity > self.settings.max_complexity * 2:
            return "error"
        return "warning"

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")
        current_file: Path | None = None

        for line in lines:
            current_file = self._update_current_file(line, current_file)
            if "complexity" in line.lower() and current_file:
                issue = self._parse_complexity_line(line, current_file)
                if issue:
                    issues.append(issue)

        logger.info(
            "Parsed Complexipy text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _update_current_file(self, line: str, current_file: Path | None) -> Path | None:
        if line.strip().startswith("File:"):
            file_str = line.strip().replace("File:", "").strip()
            return Path(file_str)
        return current_file

    def _parse_complexity_line(self, line: str, current_file: Path) -> ToolIssue | None:
        if not self.settings:
            return None

        with suppress(ValueError, IndexError):
            func_data = self._extract_function_data(line)
            if func_data:
                func_name, line_number, complexity = func_data
                if complexity > self.settings.max_complexity:
                    severity = (
                        "error"
                        if complexity > self.settings.max_complexity * 2
                        else "warning"
                    )
                    return ToolIssue(
                        file_path=current_file,
                        line_number=line_number,
                        message=f"Function '{func_name}' has complexity {complexity}",
                        code="COMPLEXITY",
                        severity=severity,
                    )

        return None

    def _extract_function_data(self, line: str) -> tuple[str, int, int] | None:
        line = line.strip()
        if "(" in line and ")" in line and "complexity" in line.lower():
            func_name = line.split("(")[0].strip()
            line_part = line.split("(")[1].split(")")[0]
            line_number = int(line_part.replace("line", "").strip())
            complexity_part = line.split("complexity")[1].strip()
            complexity = int(complexity_part.split()[0])
            return func_name, line_number, complexity

        return None

    def _get_check_type(self) -> QACheckType:
        return QACheckType.COMPLEXITY

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        config_data = self._load_config_from_pyproject()
        exclude_patterns = config_data.get(
            "exclude_patterns", ["**/.venv/**", "**/venv/**", "**/tests/**"]
        )
        max_complexity = config_data.get("max_complexity", 15)

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.COMPLEXITY,
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=exclude_patterns,
            timeout_seconds=90,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "max_complexity": max_complexity,
                "include_cognitive": True,
                "include_maintainability": True,
                "sort_by": "complexity",
            },
        )

    def _load_config_from_pyproject(self) -> dict:
        import tomllib
        from pathlib import Path

        pyproject_path = Path.cwd() / "pyproject.toml"
        config = {
            "exclude_patterns": ["**/.venv/**", "**/venv/**", "**/tests/**"],
            "max_complexity": 15,
        }

        if pyproject_path.exists():
            try:
                with pyproject_path.open("rb") as f:
                    toml_config = tomllib.load(f)
                complexipy_config = toml_config.get("tool", {}).get("complexipy", {})

                exclude_patterns = complexipy_config.get("exclude_patterns")
                if exclude_patterns:
                    config["exclude_patterns"] = exclude_patterns
                    logger.info(
                        "Loaded exclude patterns from pyproject.toml",
                        extra={"exclude_patterns": exclude_patterns},
                    )

                max_complexity = complexipy_config.get("max_complexity")
                if max_complexity is not None:
                    config["max_complexity"] = max_complexity
                    logger.info(
                        "Loaded max_complexity from pyproject.toml",
                        extra={"max_complexity": max_complexity},
                    )
            except (tomllib.TOMLDecodeError, OSError) as e:
                logger.warning(
                    "Failed to load complexipy config from pyproject.toml, using defaults",
                    extra={"error": str(e)},
                )

        return config

    def _load_exclude_patterns_from_config(self) -> list[str]:
        config = self._load_config_from_pyproject()
        return config.get(
            "exclude_patterns", ["**/.venv/**", "**/venv/**", "**/tests/**"]
        )

    def _move_complexipy_results_to_output_dir(self) -> Path | None:
        project_root = Path.cwd()
        result_files = sorted(
            project_root.glob("complexipy_results_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not result_files:
            logger.debug("No complexipy result files found in project root")
            return None

        source_file = result_files[0]

        output_dir = AdapterOutputPaths.get_output_dir("complexipy")
        dest_file = output_dir / source_file.name

        try:
            shutil.move(str(source_file), str(dest_file))
            logger.info(
                "Moved complexipy results to centralized location",
                extra={
                    "source": str(source_file),
                    "destination": str(dest_file),
                },
            )

            AdapterOutputPaths.cleanup_old_outputs(
                "complexipy", "complexipy_results_*.json", keep_latest=5
            )

            return dest_file
        except (OSError, shutil.Error) as e:
            logger.warning(
                "Failed to move complexipy results file",
                extra={
                    "error": str(e),
                    "source": str(source_file),
                    "destination": str(dest_file),
                },
            )

            return source_file
