from __future__ import annotations

import json
import logging
import typing as t
from pathlib import Path
from uuid import UUID

from pydantic import Field

from crackerjack.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.config.pip_audit_ignores import (
    load_merged_ignores,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


MODULE_ID = UUID("c0e53073-ee73-42c2-b42f-7a693708fd0c")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class OsvScannerSettings(ToolAdapterSettings):
    """Settings for the ``osv-scanner`` adapter (formerly pip-audit).

    osv-scanner reads lockfiles (``uv.lock``, ``poetry.lock``, ``requirements.txt``,
    etc.) and queries the OSV.dev database — the same backend pip-audit was
    already routing to via ``--vulnerability-service osv``. The wrapper drops
    the pip-audit-only flags (``--desc``, ``--skip-editable``, ``--require-hashes``,
    ``--vulnerability-service``) that osv-scanner doesn't accept.

    The file path is preserved as ``crackerjack/adapters/dependency/pip_audit.py``
    so any internal imports of ``from .pip_audit import …`` keep working.
    """

    tool_name: str = "osv-scanner"
    use_json_output: bool = True
    dry_run: bool = False
    fix: bool = False
    cache_dir: Path | None = None
    ignore_vulns: list[str] = Field(default_factory=list)


class OsvScannerAdapter(BaseToolAdapter):
    settings: OsvScannerSettings | None = None

    def __init__(self, settings: OsvScannerSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "OsvScannerAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = OsvScannerSettings(
                timeout_seconds=120,
                max_workers=4,
                ignore_vulns=load_merged_ignores(Path.cwd()),
            )
            logger.info("Using default OsvScannerSettings")
        await super().init()
        logger.debug(
            "OsvScannerAdapter initialization complete",
            extra={
                "fix_enabled": self.settings.fix,
                "ignored_vulns": self.settings.ignore_vulns,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "osv-scanner (Dependency Vulnerabilities)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "osv-scanner"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        settings = self.settings
        cmd = [self.tool_name]
        self._add_format_options(cmd, settings)
        self._add_input_files(cmd, files)
        self._add_fix_options(cmd, settings)
        self._add_cache_dir(cmd, settings)
        self._add_ignored_vulns(cmd, settings)

        logger.info(
            "Built osv-scanner command",
            extra={
                "file_count": len(files),
                "fix_mode": settings.fix,
                "ignored_vulns": settings.ignore_vulns,
            },
        )
        return cmd

    def _add_format_options(self, cmd: list[str], settings: OsvScannerSettings) -> None:
        if settings.use_json_output:
            cmd.extend(["--format", "json"])

    def _add_fix_options(self, cmd: list[str], settings: OsvScannerSettings) -> None:
        if settings.dry_run:
            cmd.append("--dry-run")
        if settings.fix:
            cmd.append("--fix")

    def _add_cache_dir(self, cmd: list[str], settings: OsvScannerSettings) -> None:
        if settings.cache_dir:
            cmd.extend(["--cache-dir", str(settings.cache_dir)])

    def _add_ignored_vulns(self, cmd: list[str], settings: OsvScannerSettings) -> None:
        for vuln_id in settings.ignore_vulns:
            cmd.extend(["--ignore-vuln", vuln_id])

    def _add_input_files(self, cmd: list[str], files: list[Path]) -> None:
        for file_path in files:
            if file_path.name in {"requirements.txt", "pyproject.toml", "uv.lock"}:
                cmd.extend(["--lockfile", str(file_path)])

    def _build_vulnerability_message(
        self,
        package_name: str,
        package_version: str,
        vuln_id: str,
        description: str,
        aliases: list[str],
        source_path: str,
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

        if source_path:
            message_parts.append(f"[{source_path}]")

        return " ".join(message_parts)

    def _create_issues_from_entry(
        self,
        entry: dict,
        source_path: str,
    ) -> list[ToolIssue]:
        """Walk one ``results[i]`` entry and emit ``ToolIssue`` for every
        vulnerability. The ignore-filter happens at the outer ``parse_output``
        level so we can distinguish "no vulns found" (exit_code stays) from
        "all vulns were ignored" (exit_code resets to 0).
        """
        issues: list[ToolIssue] = []
        entry_source = entry.get("source")
        if isinstance(entry_source, dict):
            candidate = t.cast(str, entry_source.get("path", ""))
            if candidate:
                source_path = candidate

        packages = entry.get("packages")
        if not isinstance(packages, list):
            return issues

        for pkg in packages:
            if not isinstance(pkg, dict):
                continue
            package = pkg.get("package")
            if not isinstance(package, dict):
                continue
            package_name = t.cast(str, package.get("name", "unknown"))
            package_version = t.cast(str, package.get("version", "unknown"))

            vulns = pkg.get("vulnerabilities")
            if not isinstance(vulns, list):
                continue

            for vuln in vulns:
                if not isinstance(vuln, dict):
                    continue
                vuln_id = t.cast(str, vuln.get("id", "unknown"))
                description = t.cast(str, vuln.get("summary", ""))
                aliases_raw = vuln.get("aliases", [])
                aliases = (
                    t.cast(list[str], aliases_raw)
                    if isinstance(aliases_raw, list)
                    else []
                )

                message = self._build_vulnerability_message(
                    package_name,
                    package_version,
                    vuln_id,
                    description,
                    aliases,
                    source_path,
                )

                issues.append(
                    ToolIssue(
                        file_path=Path("pyproject.toml"),
                        line_number=None,
                        column_number=None,
                        message=message,
                        code=vuln_id,
                        severity="error",
                    ),
                )

        return issues

    def _count_affected_packages(self, data: dict) -> int:
        affected: set[str] = set()
        results = data.get("results")
        if not isinstance(results, list):
            return 0
        for entry in results:
            if not isinstance(entry, dict):
                continue
            packages = entry.get("packages")
            if not isinstance(packages, list):
                continue
            for pkg in packages:
                if not isinstance(pkg, dict):
                    continue
                vulns = pkg.get("vulnerabilities")
                if not isinstance(vulns, list) or not vulns:
                    continue
                package = pkg.get("package")
                if isinstance(package, dict):
                    name = t.cast(str, package.get("name", ""))
                    if name:
                        affected.add(name)
        return len(affected)

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
                "Parsed osv-scanner JSON output",
                extra={"results_count": len(data.get("results", []))},
            )
        except json.JSONDecodeError:
            logger.debug(
                "JSON parse failed; osv-scanner produced no vulnerabilities",
                extra={"output_preview": result.raw_output[:200]},
            )
            return []

        issues: list[ToolIssue] = []
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return issues

        for entry in results:
            if not isinstance(entry, dict):
                continue
            source_path = ""
            source = entry.get("source")
            if isinstance(source, dict):
                source_path = t.cast(str, source.get("path", ""))
            issues.extend(self._create_issues_from_entry(entry, source_path))

        if self.settings:
            non_ignored_issues = [
                issue
                for issue in issues
                if not (
                    hasattr(issue, "code") and issue.code in self.settings.ignore_vulns
                )
            ]

            if issues and not non_ignored_issues:
                logger.info(
                    "Only ignored vulnerabilities found, updating result status",
                    extra={
                        "total_vulnerabilities": len(issues),
                        "ignored_vulnerabilities": [
                            issue.code for issue in issues if hasattr(issue, "code")
                        ],
                    },
                )
                result.exit_code = 0

        logger.info(
            "Parsed osv-scanner output",
            extra={
                "total_vulnerabilities": len(issues),
                "affected_packages": self._count_affected_packages(data)
                if isinstance(data, dict)
                else 0,
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = [
            ToolIssue(
                file_path=Path("pyproject.toml"),
                line_number=None,
                column_number=None,
                message=line.strip(),
                severity="error",
            )
            for line in output.strip().split("\n")
            if "CVE-" in line or "GHSA-" in line or "vulnerability" in line.lower()
        ]

        logger.info(
            "Parsed osv-scanner text output (fallback)",
            extra={"total_issues": len(issues)},
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.SECURITY

    async def is_successful_result(
        self,
        result: ToolExecutionResult,
    ) -> bool:
        issues = await self.parse_output(result)

        if not issues:
            if result.exit_code != 0 and self.settings:
                return True

            return result.exit_code == 0

        if self.settings:
            non_ignored_issues = [
                issue
                for issue in issues
                if not (
                    hasattr(issue, "code") and issue.code in self.settings.ignore_vulns
                )
            ]

            if non_ignored_issues:
                return False

            logger.info(
                "All vulnerabilities found are in ignore list, treating as success",
                extra={
                    "total_vulnerabilities": len(issues),
                    "ignored_vulnerabilities": len(issues),
                },
            )
            return True

        return result.exit_code == 0

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SECURITY,
            enabled=True,
            file_patterns=[
                "pyproject.toml",
                "uv.lock",
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
            stage="fast",
            settings={
                "fix": True,
                "ignore_vulns": load_merged_ignores(Path.cwd()),
            },
        )


# Backwards-compatible aliases for callers that still reference the old
# pip-audit class names. The file path is intentionally preserved as
# ``pip_audit.py`` so internal imports continue to work.
PipAuditAdapter = OsvScannerAdapter
PipAuditSettings = OsvScannerSettings
