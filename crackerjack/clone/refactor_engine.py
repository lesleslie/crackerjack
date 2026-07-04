from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from oneiric.core.logging import get_logger

from crackerjack.clone.grouper import CloneGroup, CloneType

logger = get_logger(__name__)


class CloneDecision(StrEnum):
    AUTO_APPLY = "auto_apply"
    PROPOSE_APPROVE = "propose_approve"
    REPORT_ONLY = "report_only"


@dataclass
class RefactorProposal:
    group_id: str
    decision: CloneDecision
    diff: str
    extraction_target: str
    proposed_module: str
    rationale: str


class CloneRefactorEngine:
    AUTO_APPLY_THRESHOLD = 0.95
    PROPOSE_APPROVE_MIN = 0.70

    def confidence_gate(
        self, group: CloneGroup, cross_repo: bool = False
    ) -> CloneDecision:
        if cross_repo:
            return CloneDecision.PROPOSE_APPROVE

        if group.similarity < self.PROPOSE_APPROVE_MIN:
            return CloneDecision.REPORT_ONLY

        if group.clone_type in (CloneType.EXACT, CloneType.RENAMED):
            if group.similarity >= self.AUTO_APPLY_THRESHOLD:
                return CloneDecision.AUTO_APPLY

        return CloneDecision.PROPOSE_APPROVE

    async def auto_apply(self, group: CloneGroup, diff: str) -> dict[str, Any]:
        await self._apply_diff(diff)
        passed = await self._run_test_gate()

        if not passed:
            await self._revert_diff(diff)
            logger.warning(
                "CloneRefactorEngine: test gate failed for group %s — reverted",
                group.group_id,
            )
            return {"committed": False, "reverted": True, "group_id": group.group_id}

        await self._git_commit(group.group_id)
        logger.info(
            "CloneRefactorEngine: committed refactor for group %s", group.group_id
        )
        return {"committed": True, "reverted": False, "group_id": group.group_id}

    async def propose(self, group: CloneGroup) -> RefactorProposal:
        if self._is_pycharm_available():
            diff = await self._pycharm_refactor_symbol(group)
        else:
            diff = await self._treesitter_splice(group)

        return RefactorProposal(
            group_id=group.group_id,
            decision=CloneDecision.PROPOSE_APPROVE,
            diff=diff,
            extraction_target="",
            proposed_module="",
            rationale=f"PROPOSE_APPROVE: {group.pattern_description}",
        )

    def _is_pycharm_available(self) -> bool:
        try:
            result = subprocess.run(
                ["pycharm", "--version"],
                capture_output=True,
                timeout=2,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def _pycharm_refactor_symbol(self, group: CloneGroup) -> str:
        logger.info("Using PyCharm refactor_symbol for group %s", group.group_id)
        return ""

    async def _treesitter_splice(self, group: CloneGroup) -> str:
        logger.info("Using treesitter splice for group %s", group.group_id)
        return ""

    async def _apply_diff(self, diff: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "apply",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=diff.encode())

    async def _run_test_gate(self) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "crackerjack",
            "run",
            "--fast",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    async def _revert_diff(self, diff: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "checkout",
            "--",
            ".",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    async def _git_commit(self, group_id: str) -> None:
        msg = f"refactor: extract clone group {group_id}"
        proc = await asyncio.create_subprocess_exec(
            "git",
            "commit",
            "-am",
            msg,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
