from __future__ import annotations

import json
import logging
import typing as t
from contextlib import suppress
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


MODULE_ID = UUID("3a7c9f21-e54b-4d82-b601-8f2e0d1c5a9e")
MODULE_STATUS = AdapterStatus.BETA


logger = logging.getLogger(__name__)


class BetterleaksSettings(ToolAdapterSettings):
    tool_name: str = "betterleaks"
    scan_mode: str = "git"
    report_path: Path | None = None
    config_file: Path | None = None
    redact: bool = True


class BetterleaksAdapter(BaseToolAdapter):
    settings: BetterleaksSettings | None = None

    def __init__(self, settings: BetterleaksSettings | None = None) -> None:
        super().__init__(settings=settings)

    async def init(self) -> None:
        if not self.settings:
            self.settings = BetterleaksSettings(
                timeout_seconds=120,
                max_workers=4,
            )
        await super().init()

    @property
    def adapter_name(self) -> str:
        return "Betterleaks (Secrets)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "betterleaks"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        report_path = self.settings.report_path or Path(
            ".cache/betterleaks-report.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.tool_name,
            self.settings.scan_mode,
            ".",
            "--report-path",
            str(report_path),
            "--report-format",
            "json",
        ]

        if self.settings.redact:
            cmd.append("--redact")

        if self.settings.config_file:
            cfg = Path(self.settings.config_file)
            if cfg.exists() and cfg.is_file():
                cmd.extend(["--config", str(cfg)])

        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not self.settings:
            return []

        report_path = self.settings.report_path or Path(
            ".cache/betterleaks-report.json"
        )

        if not report_path.exists():
            if result.exit_code != 0:
                return [
                    ToolIssue(
                        file_path=Path(),
                        line_number=None,
                        column_number=None,
                        message=(
                            "betterleaks report not generated — "
                            "check binary installation or run 'betterleaks --version'"
                        ),
                        code="betterleaks-gate-failure",
                        severity="error",
                        suggestion="Install betterleaks from https://github.com/betterleaks/betterleaks",
                    )
                ]

            return []

        json_text = ""
        with suppress(OSError):
            json_text = report_path.read_text(encoding="utf-8")

        if not json_text.strip():
            return []

        try:
            data = json.loads(json_text)
            findings = data if isinstance(data, list) else [data]
        except json.JSONDecodeError as exc:
            logger.warning("betterleaks JSON parse failed: %s", exc)
            return []

        issues: list[ToolIssue] = []
        for finding in findings:
            issue = self._build_finding_issue(finding)
            if issue is not None:
                issues.append(issue)
        return issues

    def _build_finding_issue(self, finding: dict[str, t.Any]) -> ToolIssue | None:
        description = finding.get("Description", "Secret detected")
        rule_id = finding.get("RuleID", "")
        tags = finding.get("Tags", [])

        parts = [description]
        if rule_id:
            parts.append(f"(Rule: {rule_id})")
        if tags:
            parts.append(f"[{', '.join(tags)}]")

        entropy = finding.get("Entropy", 0.0)
        severity = "error" if float(entropy) > 4.0 else "warning"

        return ToolIssue(
            file_path=Path(finding.get("File", ".")),
            line_number=finding.get("StartLine"),
            column_number=finding.get("StartColumn"),
            message=" ".join(parts),
            code=rule_id,
            severity=severity,
            suggestion=f"Review and remove secret. Entropy: {float(entropy):.2f}",
        )

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
            stage="comprehensive",
            settings={
                "scan_mode": "git",
                "redact": True,
            },
        )
