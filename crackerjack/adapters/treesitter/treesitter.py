from __future__ import annotations

import asyncio
import logging
import typing as t
from pathlib import Path
from uuid import UUID

from pydantic import Field

from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QABaseSettings
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig

logger = logging.getLogger(__name__)


MODULE_ID = UUID("12345678-1234-5678-1234-567812345679")
MODULE_STATUS = AdapterStatus.STABLE


class TreeSitterSettings(QABaseSettings):
    max_complexity: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Maximum cyclomatic complexity",
    )
    max_nesting_depth: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum nesting depth",
    )
    max_parameters: int = Field(
        default=7,
        ge=1,
        le=20,
        description="Maximum function parameters",
    )
    max_returns: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum return statements",
    )
    supported_extensions: list[str] = Field(
        default_factory=lambda: [".py", ".go", ".js", ".ts", ".rs"],
        description="File extensions to analyze",
    )


class TreeSitterAdapter(QAAdapterBase):
    settings: TreeSitterSettings | None = None

    def __init__(self) -> None:
        super().__init__()
        self._parser: t.Any = None

    @property
    def adapter_name(self) -> str:
        return "tree-sitter"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    async def init(self) -> None:
        if not self.settings:
            self.settings = TreeSitterSettings()  # type: ignore

        await super().init()

        try:
            from mcp_common.parsing.tree_sitter import TreeSitterParser

            self._parser = TreeSitterParser()
            logger.info("Tree-sitter quality adapter initialized")
        except ImportError:
            logger.warning(
                "mcp-common[treesitter] not installed, adapter will have limited functionality"
            )
            self._parser = None

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        if not self._initialized:
            await self.init()

        start_time = asyncio.get_event_loop().time()

        if not self._parser:
            return self._create_result(
                status=QAResultStatus.ERROR,
                message="Tree-sitter parser not available",
                start_time=start_time,
            )

        files_to_check = files or []
        if config:
            files_to_check = [
                f for f in files_to_check if self._should_check_file(f, config)
            ]

        assert self.settings is not None
        files_to_check = [
            f for f in files_to_check if f.suffix in self.settings.supported_extensions
        ]

        if not files_to_check:
            return self._create_result(
                status=QAResultStatus.SKIPPED,
                message="No files to check",
                start_time=start_time,
            )

        all_issues: list[dict[str, t.Any]] = []
        metrics = {
            "files_checked": 0,
            "total_symbols": 0,
            "complexity_issues": 0,
            "nesting_issues": 0,
            "parameter_issues": 0,
        }

        for file_path in files_to_check:
            try:
                issues = await self._check_file(file_path)
                all_issues.extend(issues)
                metrics["files_checked"] += 1
                for issue in issues:
                    rule = issue.get("code", "")
                    if "TS001" in rule:
                        metrics["complexity_issues"] += 1
                    if "TS002" in rule:
                        metrics["nesting_issues"] += 1
                    if "TS003" in rule:
                        metrics["parameter_issues"] += 1
            except Exception as e:
                logger.debug(f"Error checking {file_path}: {e}")

        if all_issues:
            error_count = sum(1 for i in all_issues if i.get("severity") == "error")
            status = (
                QAResultStatus.FAILURE if error_count > 0 else QAResultStatus.WARNING
            )
        else:
            status = QAResultStatus.SUCCESS

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        return QAResult(
            check_id=self.module_id,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            status=status,
            message=self._build_message(all_issues, metrics),
            details=self._build_details(all_issues),
            parsed_issues=all_issues,
            files_checked=files_to_check,
            issues_found=len(all_issues),
            execution_time_ms=elapsed_ms,
            metadata=metrics,
        )

    def _create_result(
        self,
        status: QAResultStatus,
        message: str,
        start_time: float,
        files: list[Path] | None = None,
        details: str | None = None,
    ) -> QAResult:
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        return QAResult(
            check_id=self.module_id,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            status=status,
            message=message,
            details=details or "",
            files_checked=files or [],
            execution_time_ms=elapsed_ms,
        )

    def _build_message(
        self,
        issues: list[dict[str, t.Any]],
        metrics: dict[str, t.Any],
    ) -> str:
        if not issues:
            return "No issues found"

        parts = [f"Found {len(issues)} issues"]
        if metrics.get("complexity_issues", 0) > 0:
            parts.append(f"{metrics['complexity_issues']} complexity")
        if metrics.get("nesting_issues", 0) > 0:
            parts.append(f"{metrics['nesting_issues']} nesting")
        if metrics.get("parameter_issues", 0) > 0:
            parts.append(f"{metrics['parameter_issues']} parameter")

        return " | ".join(parts)

    def _build_details(self, issues: list[dict[str, t.Any]]) -> str:
        lines = []
        for issue in issues[:10]:
            loc = str(issue.get("file", ""))
            if issue.get("line"):
                loc += f":{issue['line']}"
            lines.append(f"{loc}: [{issue.get('code', '')}] {issue.get('message', '')}")

        if len(issues) > 10:
            lines.append(f"... and {len(issues) - 10} more issues")

        return "\n".join(lines)

    async def _check_file(self, file_path: Path) -> list[dict[str, t.Any]]:
        issues: list[dict[str, t.Any]] = []

        from mcp_common.parsing.tree_sitter import (
            SupportedLanguage,
            ensure_language_loaded,
        )

        assert self.settings is not None

        lang = self._parser.detect_language(file_path)
        if lang == SupportedLanguage.UNKNOWN:
            return issues

        if not ensure_language_loaded(lang):
            return issues

        result = await self._parser.parse_file(file_path)

        if not result.success:
            return issues

        for name, metrics in result.complexity.items():
            if metrics.cyclomatic > self.settings.max_complexity:
                issues.append(
                    {
                        "file": file_path,
                        "line": None,
                        "column": None,
                        "code": "TS001",
                        "severity": "warning",
                        "message": (
                            f"Cyclomatic complexity {metrics.cyclomatic} exceeds "
                            f"threshold {self.settings.max_complexity} in '{name}'"
                        ),
                        "suggestion": "Consider refactoring to reduce complexity",
                    }
                )

            if metrics.nesting_depth > self.settings.max_nesting_depth:
                issues.append(
                    {
                        "file": file_path,
                        "line": None,
                        "column": None,
                        "code": "TS002",
                        "severity": "warning",
                        "message": (
                            f"Deep nesting ({metrics.nesting_depth} levels) exceeds "
                            f"threshold {self.settings.max_nesting_depth} in '{name}'"
                        ),
                        "suggestion": "Extract nested logic into separate functions",
                    }
                )

            if metrics.num_parameters > self.settings.max_parameters:
                issues.append(
                    {
                        "file": file_path,
                        "line": None,
                        "column": None,
                        "code": "TS003",
                        "severity": "info",
                        "message": (
                            f"Too many parameters ({metrics.num_parameters}) exceeds "
                            f"threshold {self.settings.max_parameters} in '{name}'"
                        ),
                        "suggestion": "Consider using a configuration object or builder pattern",
                    }
                )

        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.COMPLEXITY

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        assert self.settings is not None

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            enabled=True,
            file_patterns=[f"*{ext}" for ext in self.settings.supported_extensions],
            exclude_patterns=["**/tests/**", "**/test_*.py", "**/__pycache__/**"],
            timeout_seconds=300,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "max_complexity": self.settings.max_complexity,
                "max_nesting_depth": self.settings.max_nesting_depth,
                "max_parameters": self.settings.max_parameters,
                "max_returns": self.settings.max_returns,
            },
        )

    async def health_check(self) -> dict[str, t.Any]:
        base_health = await super().health_check()
        base_health["parser_available"] = self._parser is not None
        return base_health

    async def _cleanup(self) -> None:
        if self._parser:
            self._parser.shutdown()
            self._parser = None
        await super()._cleanup()


TreeSitterQualityAdapter = TreeSitterAdapter


__all__ = [
    "TreeSitterAdapter",
    "TreeSitterQualityAdapter",
    "TreeSitterSettings",
    "MODULE_ID",
]
