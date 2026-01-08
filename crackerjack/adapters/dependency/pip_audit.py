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


MODULE_ID = UUID("c0e53073-ee73-42c2-b42f-7a693708fd0c")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class PipAuditSettings(ToolAdapterSettings):
    tool_name: str = "pip-audit"
    use_json_output: bool = True
    require_hashes: bool = False
    vulnerability_service: str = "osv"
    skip_editable: bool = True
    dry_run: bool = False
    fix: bool = False
    output_desc: bool = True
    cache_dir: Path | None = None


class PipAuditAdapter(BaseToolAdapter):
    settings: PipAuditSettings | None = None

    def __init__(self, settings: PipAuditSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "PipAuditAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = PipAuditSettings(
                timeout_seconds=120,
                max_workers=4,
            )
            logger.info("Using default PipAuditSettings")
        await super().init()
        logger.debug(
            "PipAuditAdapter initialization complete",
            extra={
                "vulnerability_service": self.settings.vulnerability_service,
                "skip_editable": self.settings.skip_editable,
                "fix_enabled": self.settings.fix,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "pip-audit (Dependency Vulnerabilities)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "pip-audit"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if self.settings.use_json_output:
            cmd.extend(["--format", "json"])

        cmd.extend(["--vulnerability-service", self.settings.vulnerability_service])

        if self.settings.output_desc:
            cmd.append("--desc")

        if self.settings.skip_editable:
            cmd.append("--skip-editable")

        if self.settings.require_hashes:
            cmd.append("--require-hashes")

        if self.settings.dry_run:
            cmd.append("--dry-run")

        if self.settings.fix:
            cmd.append("--fix")

        if self.settings.cache_dir:
            cmd.extend(["--cache-dir", str(self.settings.cache_dir)])

        for file_path in files:
            if file_path.name in ("requirements.txt", "pyproject.toml"):
                cmd.extend(["-r", str(file_path)])
            elif file_path.is_dir():
                pass

        logger.info(
            "Built pip-audit command",
            extra={
                "file_count": len(files),
                "vulnerability_service": self.settings.vulnerability_service,
                "fix_mode": self.settings.fix,
                "skip_editable": self.settings.skip_editable,
            },
        )
        return cmd

    def _build_vulnerability_message(
        self,
        package_name: str,
        package_version: str,
        vuln_id: str,
        description: str,
        fix_versions: list[str],
        aliases: list[str],
    ) -> str:
        message_parts = [
            f"{package_name}=={package_version}",
            f"vulnerability {vuln_id}",
        ]

        cve_aliases = [a for a in aliases if a.startswith("CVE-")]
        if cve_aliases:
            message_parts.append(f"({', '.join(cve_aliases)})")

        if description:
            desc_preview = (
                description[:100] + "..." if len(description) > 100 else description
            )
            message_parts.append(f"- {desc_preview}")

        if fix_versions:
            message_parts.append(f"Fix available: {', '.join(fix_versions[:3])}")

        return " ".join(message_parts)

    def _create_issues_from_dependencies(self, data: dict) -> list[ToolIssue]:
        issues = []

        for dependency in data.get("dependencies", []):
            package_name = dependency.get("name", "unknown")
            package_version = dependency.get("version", "unknown")

            for vuln in dependency.get("vulns", []):
                vuln_id = vuln.get("id", "unknown")
                description = vuln.get("description", "")
                fix_versions = vuln.get("fix_versions", [])
                aliases = vuln.get("aliases", [])

                message = self._build_vulnerability_message(
                    package_name,
                    package_version,
                    vuln_id,
                    description,
                    fix_versions,
                    aliases,
                )

                issue = ToolIssue(
                    file_path=Path("pyproject.toml"),
                    line_number=None,
                    column_number=None,
                    message=message,
                    code=vuln_id,
                    severity="error",
                )
                issues.append(issue)

        return issues

    def _count_affected_packages(self, data: dict) -> int:
        return len(
            {
                dep.get("name")
                for dep in data.get("dependencies", [])
                if dep.get("vulns")
            }
        )

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed pip-audit JSON output",
                extra={"dependencies_count": len(data.get("dependencies", []))},
            )
        except json.JSONDecodeError as e:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = self._create_issues_from_dependencies(data)

        logger.info(
            "Parsed pip-audit output",
            extra={
                "total_vulnerabilities": len(issues),
                "affected_packages": self._count_affected_packages(data),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            if "PYSEC-" in line or "CVE-" in line or "vulnerability" in line.lower():
                issue = self._parse_text_line(line)
                if issue:
                    issues.append(issue)

        logger.info(
            "Parsed pip-audit text output (fallback)",
            extra={
                "total_issues": len(issues),
            },
        )
        return issues

    def _parse_text_line(self, line: str) -> ToolIssue | None:
        try:
            return ToolIssue(
                file_path=Path("pyproject.toml"),
                line_number=None,
                column_number=None,
                message=line.strip(),
                severity="error",
            )
        except Exception:
            return None

    def _get_check_type(self) -> QACheckType:
        return QACheckType.SECURITY

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SECURITY,
            enabled=True,
            file_patterns=[
                "pyproject.toml",
                "requirements.txt",
                "requirements-*.txt",
            ],
            exclude_patterns=[
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=120,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "vulnerability_service": "osv",
                "skip_editable": True,
                "output_desc": True,
                "fix": False,
            },
        )
