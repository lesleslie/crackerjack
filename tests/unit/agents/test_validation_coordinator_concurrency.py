"""Concurrency-safety test for project-wide ty validation (defect #2).

``ValidationCoordinator.validate_fix_for_type_change`` is a project-global
critical section:

    1. capture a project-wide ``ty`` baseline
    2. write the candidate file to disk
    3. re-run project-wide ``ty``
    4. diff post vs baseline; any *new* signature ``file:line:col:msg`` is a
       regression → roll the file back

``ParallelDispatcher`` runs up to ``min(8, cpu)`` plans concurrently, all
sharing a single cached ValidationCoordinator (via
``FixerCoordinator._get_type_change_validator``). Without serialization, plan
A's baseline→post window overlaps plan B's disk write, so B's freshly-written
error shows up as "new" in A's diff — A is blamed for B's regression and
spuriously rolled back. In the observed run this manifested as ty errors from
one file accumulating into another file's rejection feedback.

The fix serializes the critical section with a shared lock so at most one
type-change validation runs at a time.
"""

import asyncio
from pathlib import Path

import pytest

from crackerjack.agents.validation_coordinator import ValidationCoordinator


class _ConcurrencyRecorder:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def enter(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        # Yield control so a racing coroutine can interleave if unlocked.
        await asyncio.sleep(0.01)

    def exit(self) -> None:
        self.active -= 1


@pytest.mark.asyncio
async def test_type_change_validation_serialized_under_concurrency(
    tmp_path: Path,
) -> None:
    """Concurrent type-change validations on a shared coordinator must be
    serialized: at most one runs its baseline→write→recheck window at a time.
    """
    coordinator = ValidationCoordinator(project_path=tmp_path)
    recorder = _ConcurrencyRecorder()

    async def fake_run_ty_check() -> object:
        # Model the global ty run: record concurrency across the whole
        # baseline→post window by entering on each ty invocation.
        await recorder.enter()
        try:
            return object()
        finally:
            recorder.exit()

    coordinator._run_ty_check = fake_run_ty_check  # type: ignore[method-assign]
    # No new/resolved issues → is_valid, no rollback, keeps the test focused
    # on the concurrency of the critical section.
    coordinator._collect_ty_keys = staticmethod(lambda result: set())  # type: ignore[assignment]
    coordinator._extract_issue_dicts = staticmethod(lambda result: [])  # type: ignore[assignment]

    async def validate_one(index: int) -> tuple[bool, str]:
        target = tmp_path / f"mod_{index}.py"
        target.write_text("x = 1\n", encoding="utf-8")
        return await coordinator.validate_fix_for_type_change(
            code="x = 2\n",
            file_path=str(target),
            original_code="x = 1\n",
        )

    await asyncio.gather(*(validate_one(i) for i in range(4)))

    assert recorder.max_active == 1, (
        "Project-wide ty validation must be serialized. Observed "
        f"max_active={recorder.max_active}: concurrent validations overlapped "
        "their baseline→write→recheck windows, which lets one plan's disk "
        "write pollute another plan's baseline diff (defect #2)."
    )
