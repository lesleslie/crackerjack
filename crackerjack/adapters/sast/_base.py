from __future__ import annotations

import typing as t
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from crackerjack.adapters._tool_adapter_base import (
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig
    from crackerjack.models.qa_results import QACheckType


@runtime_checkable
class SASTAdapterProtocol(Protocol):
    settings: ToolAdapterSettings | None

    @property
    def adapter_name(self) -> str: ...

    @property
    def module_id(self) -> UUID: ...

    @property
    def tool_name(self) -> str: ...

    async def init(self) -> None: ...

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]: ...

    async def check(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> ToolExecutionResult: ...

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]: ...

    def _get_check_type(self) -> QACheckType: ...

    def get_default_config(self) -> QACheckConfig: ...


SASTAdapter = SASTAdapterProtocol

__all__ = [
    "SASTAdapterProtocol",
    "SASTAdapter",
]
