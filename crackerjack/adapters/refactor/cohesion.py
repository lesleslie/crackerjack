"""CohesionAdapter — class cohesion measurement via the cohesion CLI.

cohesion is GPL-3.0. This adapter invokes it as an external subprocess only
(no `import cohesion` in production code), so GPL does not propagate to Crackerjack.

Install: `uv add cohesion`
"""

from __future__ import annotations

import logging
import re
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


MODULE_ID = UUID("7b4e2f91-c5a8-4d63-b0e7-9f3a1d6c8e42")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)

_CLASS_RE = re.compile(r"^\s{2}Class:\s+(\S+)\s+\((\d+):\d+\)")
_TOTAL_RE = re.compile(r"^\s+Total:\s+([\d.]+)%")
_FILE_RE = re.compile(r"^File:\s+(.+)$")


class CohesionSettings(ToolAdapterSettings):
    tool_name: str = "cohesion"
    min_cohesion: float = 0.70  # 70% — emit error below this
    directory: str = "."


class CohesionAdapter(BaseToolAdapter):
    settings: CohesionSettings | None = None

    def __init__(self, settings: CohesionSettings | None = None) -> None:
        super().__init__(settings=settings)

    async def init(self) -> None:
        if not self.settings:
            self.settings = CohesionSettings(timeout_seconds=300, max_workers=4)
        await super().init()

    @property
    def adapter_name(self) -> str:
        return "Cohesion (Class Cohesion)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "cohesion"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        threshold = int(self.settings.min_cohesion * 100)
        return [
            "cohesion",
            "-d",
            self.settings.directory,
            "-b",
            str(threshold),
        ]

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not self.settings:
            return []

        raw = result.raw_output or ""
        if not raw.strip():
            return []

        threshold_pct = self.settings.min_cohesion * 100
        issues: list[ToolIssue] = []

        current_file: str = "."
        current_class: str | None = None
        current_line: int | None = None

        for line in raw.splitlines():
            file_match = _FILE_RE.match(line)
            if file_match:
                current_file = file_match.group(1).strip()
                current_class = None
                current_line = None
                continue

            class_match = _CLASS_RE.match(line)
            if class_match:
                current_class = class_match.group(1)
                current_line = int(class_match.group(2))
                continue

            total_match = _TOTAL_RE.match(line)
            if total_match and current_class is not None:
                pct = float(total_match.group(1))
                if pct < threshold_pct:
                    issues.append(
                        ToolIssue(
                            file_path=Path(current_file),
                            line_number=current_line,
                            column_number=None,
                            message=(
                                f"{current_class} has low cohesion: "
                                f"{pct:.1f}% (threshold: {threshold_pct:.0f}%)"
                            ),
                            code="cohesion-low",
                            severity="error",
                            suggestion=(
                                "Split class into smaller, more focused units "
                                "or extract unrelated methods."
                            ),
                        )
                    )
                current_class = None
                current_line = None

        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.COMPLEXITY

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.COMPLEXITY,
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/.git/**",
                "**/node_modules/**",
                "**/.venv/**",
                "**/venv/**",
                "**/__pycache__/**",
                "**/tests/**",
            ],
            timeout_seconds=300,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "min_cohesion": 0.70,
                "directory": ".",
            },
        )
