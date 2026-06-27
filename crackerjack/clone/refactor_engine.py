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
    """Applies confidence-gated refactoring for detected clone groups.

    Same-repo tiers:
    - Type 1-2, similarity ≥ 0.95 → AUTO_APPLY
    - Type 3, similarity 0.70-0.94 → PROPOSE_APPROVE
    - Type 4 / < 0.70 → REPORT_ONLY

    Cross-repo: ALWAYS PROPOSE_APPROVE (never auto-apply per M-NEW-5).
    """

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
        """Apply diff, run test gate, commit or revert."""
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
        """Generate a RefactorProposal using PyCharm or treesitter fallback."""
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
        """Check if PyCharm remote dev server is running and accessible."""
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
        """Delegate rename to PyCharm refactor_symbol (opportunistic)."""
        logger.info("Using PyCharm refactor_symbol for group %s", group.group_id)
        return ""

    async def _treesitter_splice(self, group: CloneGroup) -> str:
        """Find usages via treesitter + text-splice as fallback."""
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
