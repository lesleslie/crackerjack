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


MODULE_ID = UUID("6deed37d-f943-44f5-a188-f2b287f7a17d")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class GitleaksSettings(ToolAdapterSettings):
    tool_name: str = "gitleaks"
    use_json_output: bool = True
    scan_mode: str = "detect"
    config_file: Path | None = None
    baseline_file: Path | None = None
    no_git: bool = False
    redact: bool = True
    verbose: bool = False


class GitleaksAdapter(BaseToolAdapter):
    settings: GitleaksSettings | None = None

    def __init__(self, settings: GitleaksSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "GitleaksAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = GitleaksSettings(
                timeout_seconds=120,
                max_workers=4,
            )
            logger.info("Using default GitleaksSettings")
        await super().init()
        logger.debug(
            "GitleaksAdapter initialization complete",
            extra={
                "scan_mode": self.settings.scan_mode,
                "redact": self.settings.redact,
                "no_git": self.settings.no_git,
                "has_config": self.settings.config_file is not None,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Gitleaks (Secrets)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "gitleaks"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        cmd.append(self.settings.scan_mode)

        if files:
            if self.settings.scan_mode == "protect":
                cmd.extend(["--source", str(files[0].parent if files else Path.cwd())])
            else:
                cmd.extend(["--source", str(Path.cwd())])

        if self.settings.use_json_output:
            cmd.extend(["--report-format", "json"])

            cmd.extend(["--report-path", "/dev/stdout"])

        if self.settings.config_file and self.settings.config_file.exists():
            cmd.extend(["--config", str(self.settings.config_file)])

        if self.settings.baseline_file and self.settings.baseline_file.exists():
            cmd.extend(["--baseline-path", str(self.settings.baseline_file)])

        if self.settings.no_git:
            cmd.append("--no-git")

        if self.settings.redact:
            cmd.append("--redact")

        if self.settings.verbose:
            cmd.append("--verbose")

        logger.info(
            "Built Gitleaks command",
            extra={
                "file_count": len(files),
                "scan_mode": self.settings.scan_mode,
                "redact": self.settings.redact,
                "no_git": self.settings.no_git,
                "has_config": self.settings.config_file is not None,
                "has_baseline": self.settings.baseline_file is not None,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            findings = data if isinstance(data, list) else [data]
            logger.debug(
                "Parsed Gitleaks JSON output", extra={"findings_count": len(findings)}
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse failed",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return []

        issues = []

        for finding in findings:
            file_path = Path(finding.get("File", ""))

            description = finding.get("Description", "Secret detected")
            rule_id = finding.get("RuleID", "")
            tags = finding.get("Tags", [])

            message_parts = [description]
            if rule_id:
                message_parts.append(f"(Rule: {rule_id})")
            if tags:
                message_parts.append(f"[{', '.join(tags)}]")

            message = " ".join(message_parts)

            entropy = finding.get("Entropy", 0.0)
            severity = "error" if entropy > 4.0 else "warning"

            issue = ToolIssue(
                file_path=file_path,
                line_number=finding.get("StartLine"),
                column_number=finding.get("StartColumn"),
                message=message,
                code=rule_id,
                severity=severity,
                suggestion=f"Review and remove secret. Entropy: {entropy:.2f}",
            )
            issues.append(issue)

        logger.info(
            "Parsed Gitleaks output",
            extra={
                "total_issues": len(issues),
                "high_entropy": sum(1 for i in issues if i.severity == "error"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.SECURITY

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SECURITY,
            enabled=True,
            file_patterns=["**/*"],
            exclude_patterns=[
                "**/.git/**",
                "**/node_modules/**",
                "**/.venv/**",
                "**/venv/**",
                "**/__pycache__/**",
            ],
            timeout_seconds=120,
            parallel_safe=True,
            stage="fast",
            settings={
                "scan_mode": "protect",
                "redact": True,
                "no_git": False,
            },
        )
