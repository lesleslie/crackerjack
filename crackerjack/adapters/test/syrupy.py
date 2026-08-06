"""SyrupyAdapter — snapshot testing via the pytest-syrupy plugin.

syrupy is a pytest plugin; this adapter invokes pytest with syrupy flags
rather than running a standalone binary.
"""

from __future__ import annotations

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


MODULE_ID = UUID("2c8f5b3a-d7e4-4f91-a0c6-1b3e9d5a7f82")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)

_JSON_EXTENSION = "syrupy.extensions.json.JSONSnapshotExtension"


class SyrupySettings(ToolAdapterSettings):
    tool_name: str = "pytest"
    update_snapshots: bool = False
    extension: str = _JSON_EXTENSION


class SyrupyAdapter(BaseToolAdapter):
    settings: SyrupySettings | None = None

    def __init__(self, settings: SyrupySettings | None = None) -> None:
        super().__init__(settings=settings)

    async def init(self) -> None:
        if not self.settings:
            self.settings = SyrupySettings(timeout_seconds=300, max_workers=4)
        await super().init()

    @property
    def adapter_name(self) -> str:
        return "Syrupy (Snapshot Tests)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "pytest"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        cmd = [
            "pytest",
            f"--snapshot-default-extension={self.settings.extension}",
        ]

        if self.settings.update_snapshots:
            cmd.append("--snapshot-update")

        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if result.exit_code == 0:
            return []

        raw = result.raw_output + result.error_output
        if not raw.strip():
            return [
                ToolIssue(
                    file_path=Path(),
                    line_number=None,
                    column_number=None,
                    message="Syrupy snapshot tests failed (no output captured)",
                    code="syrupy-unknown-failure",
                    severity="error",
                    suggestion="Run `pytest --snapshot-update` to regenerate snapshots.",
                )
            ]

        issues: list[ToolIssue] = []
        for line in raw.splitlines():
            lower = line.lower()
            if "snapshot" in lower and (
                "fail" in lower or "mismatch" in lower or "does not match" in lower
            ):
                issues.append(
                    ToolIssue(
                        file_path=Path(),
                        line_number=None,
                        column_number=None,
                        message=line.strip(),
                        code="syrupy-snapshot-mismatch",
                        severity="error",
                        suggestion=(
                            "Run `crackerjack run --update-snapshots` to accept "
                            "the new output as the expected snapshot."
                        ),
                    )
                )

        if not issues:
            issues.append(
                ToolIssue(
                    file_path=Path(),
                    line_number=None,
                    column_number=None,
                    message="Syrupy snapshot tests failed",
                    code="syrupy-failure",
                    severity="error",
                    suggestion="Run `pytest --snapshot-update` to regenerate snapshots.",
                )
            )

        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.TESTING  # ty: ignore[unresolved-attribute]

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.TESTING,  # ty: ignore[unresolved-attribute]
            enabled=True,
            file_patterns=["tests/**/*.py"],
            exclude_patterns=[
                "**/.git/**",
                "**/.venv/**",
                "**/__pycache__/**",
            ],
            timeout_seconds=300,
            parallel_safe=False,
            stage="comprehensive",
            settings={
                "update_snapshots": False,
                "extension": _JSON_EXTENSION,
            },
        )
