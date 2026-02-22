"""Tree-sitter adapter for Crackerjack quality checks.

This adapter provides multi-language code quality checks using tree-sitter,
complementing the existing Python-specific ast module with:
- Multi-language support (Python, Go, JavaScript, TypeScript, Rust)
- Error-tolerant parsing
- Structural pattern detection
- Complexity metrics across languages
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QABaseSettings

if TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig
    from crackerjack.models.qa_results import QAResult

logger = logging.getLogger(__name__)

# Module ID for this adapter
MODULE_ID = uuid.UUID("12345678-1234-5678-1234-567812345679")


class TreeSitterSettings(QABaseSettings):
    """Settings for tree-sitter quality adapter."""

    max_complexity: int = Field(15, ge=1, le=100, description="Maximum cyclomatic complexity")
    max_nesting_depth: int = Field(4, ge=1, le=10, description="Maximum nesting depth")
    max_parameters: int = Field(7, ge=1, le=20, description="Maximum function parameters")
    max_returns: int = Field(5, ge=1, le=20, description="Maximum return statements")
    supported_extensions: list[str] = Field(
        default_factory=lambda: [".py", ".go", ".js", ".ts", ".rs"],
        description="File extensions to analyze",
    )


class TreeSitterQualityAdapter(QAAdapterBase):
    """Multi-language quality checks using tree-sitter.

    Complements existing Python ast module with:
    - Multi-language support (Go, JavaScript, TypeScript, Rust)
    - Error-tolerant parsing
    - Structural pattern detection
    """

    settings: TreeSitterSettings | None = None

    def __init__(self) -> None:
        super().__init__()
        self._parser: Any = None

    @property
    def module_id(self) -> uuid.UUID:
        return MODULE_ID

    async def init(self) -> None:
        if not self.settings:
            self.settings = TreeSitterSettings()

        await super().init()

        # Initialize parser
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
        """Run quality checks on files using tree-sitter.

        Args:
            files: List of files to check (None = all matching files)
            config: Check configuration

        Returns:
            QAResult with findings
        """
        from crackerjack.models.qa_results import QAResult

        if not self._initialized:
            await self.init()

        if not self._parser:
            return QAResult(
                adapter_name=self.adapter_name,
                success=True,
                findings=[],
                metrics={"error": "Tree-sitter parser not available"},
                duration_ms=0,
            )

        # Get files to check
        files_to_check = files or []
        if config:
            files_to_check = [f for f in files_to_check if self._should_check_file(f, config)]

        # Filter by supported extensions
        files_to_check = [
            f
            for f in files_to_check
            if f.suffix in self.settings.supported_extensions  # type: ignore
        ]

        if not files_to_check:
            return QAResult(
                adapter_name=self.adapter_name,
                success=True,
                findings=[],
                metrics={"files_checked": 0},
                duration_ms=0,
            )

        # Run checks
        start_time = asyncio.get_event_loop().time()
        all_findings: list[dict[str, Any]] = []
        metrics = {
            "files_checked": 0,
            "total_symbols": 0,
            "complexity_issues": 0,
            "nesting_issues": 0,
            "parameter_issues": 0,
        }

        for file_path in files_to_check:
            try:
                findings = await self._check_file(file_path)
                all_findings.extend(findings)
                metrics["files_checked"] += 1
                for f in findings:
                    if "complexity" in f.get("rule", "").lower():
                        metrics["complexity_issues"] += 1
                    if "nesting" in f.get("rule", "").lower():
                        metrics["nesting_issues"] += 1
                    if "parameter" in f.get("rule", "").lower():
                        metrics["parameter_issues"] += 1
            except Exception as e:
                logger.debug(f"Error checking {file_path}: {e}")

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        return QAResult(
            adapter_name=self.adapter_name,
            success=len(all_findings) == 0,
            findings=all_findings,
            metrics=metrics,
            duration_ms=duration_ms,
        )

    async def _check_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Check a single file for quality issues.

        Args:
            file_path: Path to file

        Returns:
            List of findings
        """
        findings: list[dict[str, Any]] = []

        # Load grammar
        from mcp_common.parsing.tree_sitter import SupportedLanguage, ensure_language_loaded

        lang = self._parser.detect_language(file_path)
        if lang == SupportedLanguage.UNKNOWN:
            return findings

        if not ensure_language_loaded(lang):
            return findings

        # Parse file
        result = await self._parser.parse_file(file_path)

        if not result.success:
            return findings

        # Check complexity metrics
        for name, metrics in result.complexity.items():
            if metrics.cyclomatic > self.settings.max_complexity:  # type: ignore
                findings.append(
                    {
                        "rule": "TS001",
                        "severity": "warning",
                        "file": str(file_path),
                        "symbol": name,
                        "message": f"Cyclomatic complexity {metrics.cyclomatic} exceeds threshold {self.settings.max_complexity}",  # type: ignore
                        "line": None,
                    }
                )

            if metrics.nesting_depth > self.settings.max_nesting_depth:  # type: ignore
                findings.append(
                    {
                        "rule": "TS002",
                        "severity": "warning",
                        "file": str(file_path),
                        "symbol": name,
                        "message": f"Deep nesting ({metrics.nesting_depth} levels) exceeds threshold {self.settings.max_nesting_depth}",  # type: ignore
                        "line": None,
                    }
                )

            if metrics.num_parameters > self.settings.max_parameters:  # type: ignore
                findings.append(
                    {
                        "rule": "TS003",
                        "severity": "info",
                        "file": str(file_path),
                        "symbol": name,
                        "message": f"Too many parameters ({metrics.num_parameters}) exceeds threshold {self.settings.max_parameters}",  # type: ignore
                        "line": None,
                    }
                )

        return findings

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for this adapter."""
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            adapter_name=self.adapter_name,
            file_patterns=[f"*{ext}" for ext in self.settings.supported_extensions] if self.settings else ["*.py"],  # type: ignore
            exclude_patterns=["**/tests/**", "**/test_*.py", "**/__pycache__/**"],
            fail_on_error=False,
            timeout_seconds=300,
        )

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        base_health = await super().health_check()
        base_health["parser_available"] = self._parser is not None
        return base_health

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        if self._parser:
            self._parser.shutdown()
            self._parser = None
        await super()._cleanup()


__all__ = ["TreeSitterQualityAdapter", "TreeSitterSettings", "MODULE_ID"]
