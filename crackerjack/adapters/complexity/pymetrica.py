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


MODULE_ID = UUID("9e1c4a7d-f2b8-4e56-a3d0-7f8b2c9e5d31")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)

_CC_KEYWORDS = {"cyclomatic complexity", "cc per lloc", "cc_number"}
_EXCEEDS_PHRASE = "exceeds the fail threshold"
_AGGREGATE_CODE = "pymetrica-aggregate"
_AGGREGATE_FILE_HINT = Path("pymetrica") / "aggregate"


_FILE_PATH_PREFIX = re.compile(r"^(?P<path>[^\s:]+\.py):\s*(?P<rest>.+)$")


class PymetricaSettings(ToolAdapterSettings):
    tool_name: str = "pymetrica"
    cc_fail_threshold: int = 0
    directory: str = "."


class PymetricaAdapter(BaseToolAdapter):
    settings: PymetricaSettings | None = None

    def __init__(self, settings: PymetricaSettings | None = None) -> None:
        super().__init__(settings=settings)

    async def init(self) -> None:
        if not self.settings:
            self.settings = PymetricaSettings(timeout_seconds=300, max_workers=4)
        await super().init()

    @property
    def adapter_name(self) -> str:
        return "Pymetrica (HV/PO/LI/MC)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "pymetrica"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        return [
            "pymetrica",
            "run-all",
            self.settings.directory,
            "-a",
        ]

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not self.settings:
            return []

        raw = result.raw_output
        if not raw.strip():
            return []

        grouped: dict[tuple[Path, str], list[str]] = {}
        current_metric: str = ""

        for line in raw.splitlines():
            stripped = line.strip()

            if stripped.startswith("Metric:"):
                current_metric = stripped[len("Metric:") :].strip()
                continue

            if _EXCEEDS_PHRASE not in stripped:
                continue

            if any(kw in current_metric.lower() for kw in _CC_KEYWORDS):
                continue
            if any(kw in stripped.lower() for kw in _CC_KEYWORDS):
                continue

            file_path, message_line = self._split_file_prefix(stripped)
            grouped.setdefault((file_path, current_metric), []).append(message_line)

        issues: list[ToolIssue] = []
        for (file_path, metric), msg_lines in grouped.items():
            combined_message = "\n".join(
                f"[{metric}] {msg_line}" for msg_line in msg_lines
            )
            issues.append(
                ToolIssue(
                    file_path=file_path,
                    line_number=None,
                    column_number=None,
                    message=combined_message,
                    code=_AGGREGATE_CODE,
                    severity="error",
                    suggestion=(
                        "Check pymetrica documentation or run "
                        "`pymetrica run-all . -a` for top findings."
                    ),
                )
            )

        return issues

    @staticmethod
    def _split_file_prefix(line: str) -> tuple[Path, str]:
        match = _FILE_PATH_PREFIX.match(line)
        if match:
            return Path(match.group("path")), match.group("rest")
        return _AGGREGATE_FILE_HINT, line

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
                "**/.venv/**",
                "**/venv/**",
                "**/__pycache__/**",
                "**/tests/**",
            ],
            timeout_seconds=300,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "cc_fail_threshold": 0,
                "directory": ".",
            },
        )
