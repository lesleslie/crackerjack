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

        # Clean slate: delete any stale report so a panic'd or crashed
        # betterleaks invocation can never leave a previous run's findings
        # behind to be parsed as if they were from the current run.
        # See test_betterleaks_panic_with_stale_report_does_not_invent_issues.
        with suppress(OSError):
            if report_path.exists():
                report_path.unlink()

        # Resolve scan root to the git toplevel so betterleaks can locate
        # a project-level ``.betterleaks.toml`` (precedence #4 per the
        # betterleaks CLI). Falling back to the cwd preserves existing
        # behaviour for non-git directories (tests, sandboxes).
        scan_root = self._find_git_root() or Path.cwd()

        cmd = [
            self.tool_name,
            self.settings.scan_mode,
            str(scan_root),
            "--report-path",
            str(report_path),
            "--report-format",
            "json",
        ]

        if self.settings.redact:
            cmd.append("--redact")

        # Config precedence per the betterleaks CLI: an explicit
        # ``config_file`` setting wins over auto-discovery, which wins
        # over BETTERLEAKS_CONFIG env var. We only auto-discover a
        # project-local ``.betterleaks.toml`` when no explicit setting
        # is provided so operators can still pin a global config.
        if self.settings.config_file:
            cfg = Path(self.settings.config_file)
            if cfg.exists() and cfg.is_file():
                cmd.extend(["--config", str(cfg)])
        else:
            for candidate in (".betterleaks.toml", ".gitleaks.toml"):
                auto = scan_root / candidate
                if auto.exists() and auto.is_file():
                    cmd.extend(["--config", str(auto)])
                    break

        return cmd

    @staticmethod
    def _find_git_root(start: Path | None = None) -> Path | None:
        """Walk up from ``start`` (default cwd) to find the git toplevel.

        Returns ``None`` if no git repo is found, or if the lookup fails
        for any reason (missing ``git`` binary, permission errors, etc.).
        Tests rely on the silent-failure contract: a non-git working
        directory must not break command construction.
        """
        import subprocess

        cwd = start or Path.cwd()
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except OSError, subprocess.TimeoutExpired:
            return None
        if result.returncode != 0:
            return None
        toplevel = result.stdout.strip()
        if not toplevel:
            return None
        return Path(toplevel)

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not self.settings:
            return []

        report_path = self.settings.report_path or Path(
            ".cache/betterleaks-report.json"
        )

        # Gitleaks/betterleaks convention:
        #   exit 0  = tool ran cleanly, no secrets
        #   exit 1  = tool ran cleanly, secrets found (NORMAL success path)
        #   exit 2+ = panic, crash, signal kill, or other anomaly
        # On any non-{0,1} exit, do NOT trust the report file — it may be
        # stale from a previous run, partial/garbage from a mid-write panic,
        # or simply never produced. Surface as a gate failure and discard the
        # report so the next run starts from a known-empty file.
        # See test_betterleaks_panic_with_stale_report_does_not_invent_issues.
        if result.exit_code not in (0, 1):
            with suppress(OSError):
                if report_path.exists():
                    report_path.unlink()
            return [
                ToolIssue(
                    file_path=Path(),
                    line_number=None,
                    column_number=None,
                    message=(
                        f"betterleaks exited with code {result.exit_code} — "
                        "report discarded (panic or crash). See stderr for "
                        "details."
                    ),
                    code="betterleaks-gate-failure",
                    severity="error",
                    suggestion=(
                        "Check the betterleaks binary version and any malformed "
                        "files in the scan root. If this persists, file an issue "
                        "at https://github.com/betterleaks/betterleaks."
                    ),
                )
            ]

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
                # VCS / package managers
                "**/.git/**",
                "**/node_modules/**",
                # Python environments
                "**/.venv/**",
                "**/venv/**",
                "**/__pycache__/**",
                "**/*.pyc",
                # Build artifacts (Python wheels/sdists + extracted sources)
                "**/build/**",
                "**/dist/**",
                "**/*.egg-info/**",
                # Tool caches (crackerjack, uv, ruff, mypy, pytest)
                "**/.crackerjack/**",
                "**/.ruff_cache/**",
                "**/.mypy_cache/**",
                "**/.pytest_cache/**",
                "**/.cache/**",
                "**/htmlcov/**",
            ],
            timeout_seconds=120,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "scan_mode": "git",
                "redact": True,
            },
        )
