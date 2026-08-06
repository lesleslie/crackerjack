from __future__ import annotations

import asyncio
import os
import re
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from crackerjack.config.settings import HookSettings
from crackerjack.services.git_cleanup_service import DirtyWorkingTreeError
from crackerjack.services.git_cleanup_service import (
    validate_working_tree_clean,
)

from .ai_fix_event_bus import AIFixEventBus
from .ai_fix_events import PreflightFinished, PreflightStarted


class PreflightConfig(BaseModel):
    ruff_check: bool = True
    ruff_format: bool = True
    ruff_unsafe_fixes: bool = False
    ruff_select_extra: list[str] = []
    autoflake_unused: bool = True
    refurb_safe_policies: bool = True
    docformatter: bool = False
    timeout_s: float = 60.0
    force_prepass: bool = False

    model_config = {"frozen": True}


@dataclass
class PreflightStepResult:
    tool: str
    files_changed: int
    issues_fixed: int
    duration_s: float
    success: bool


@dataclass
class PreflightReport:
    steps: list[PreflightStepResult] = field(default_factory=list)
    total_files_changed: int = 0
    total_issues_fixed: int = 0
    duration_s: float = 0.0


class PreflightFixer:
    def __init__(
        self,
        config: PreflightConfig,
        bus: AIFixEventBus,
        pkg_path: Path,
        settings: HookSettings | None = None,
    ) -> None:
        self._config = config
        self._bus = bus
        self._pkg_path = pkg_path
        # Stage 3: prefer the project-wide HookSettings for the ruff-unsafe
        # knob so CLI / config consistency matches Stages 1 and 2. The legacy
        # ``PreflightConfig.ruff_unsafe_fixes`` field is still respected as a
        # fallback when no HookSettings are provided — that field is on the
        # way out but kept read-compatible during the rollout.
        self._settings: HookSettings = settings or HookSettings()

    async def run(self, run_id: str, iteration: int) -> PreflightReport:
        tools = self._enabled_tools()
        t0 = time.time()

        await self._bus.emit(
            PreflightStarted(
                run_id=run_id,
                iteration=iteration,
                tools=tuple(tools),
            )
        )

        baseline = self._snapshot_mtimes()

        loop = asyncio.get_running_loop()
        steps = await asyncio.gather(
            *(
                loop.run_in_executor(None, self._run_step_sync, tool, baseline)
                for tool in tools
            )
        )

        duration = time.time() - t0
        total_files = sum(s.files_changed for s in steps)
        total_issues = sum(s.issues_fixed for s in steps)

        await self._bus.emit(
            PreflightFinished(
                run_id=run_id,
                iteration=iteration,
                issues_saved=total_issues,
                duration_s=duration,
            )
        )

        return PreflightReport(
            steps=steps,
            total_files_changed=total_files,
            total_issues_fixed=total_issues,
            duration_s=duration,
        )

    def _enabled_tools(self) -> list[str]:
        tools: list[str] = []
        if self._config.ruff_check:
            tools.append("ruff_check")
        if self._config.ruff_format:
            tools.append("ruff_format")
        if self._config.autoflake_unused:
            tools.append("ruff_f401")
        if self._config.ruff_select_extra:
            tools.append("ruff_extra")
        if self._config.refurb_safe_policies:
            tools.append("refurb")
        return tools

    def _run_step_sync(
        self,
        tool: str,
        baseline: dict[Path, float] | None = None,
    ) -> PreflightStepResult:
        t0 = time.time()
        mtimes_before = baseline if baseline is not None else self._snapshot_mtimes()
        cmd = self._build_cmd(tool)

        if not cmd:
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=0.0,
                success=False,
            )

        # Stage 3 Round 1 fix: gate ruff --fix invocations by working-tree
        # state. The earlier Stage 3 commit only wired the guard into a
        # separable test seam (``run_ruff_check``), which meant the actual
        # production ruff path bypassed the safety check. ruff_format does
        # not mutate the working tree so we skip the guard for it.
        self._guard_ruff_fix_invocation(tool, cmd)

        try:
            result = subprocess.run(
                cmd,
                cwd=self._pkg_path,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=self._config.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=time.time() - t0,
                success=False,
            )
        except Exception:
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=time.time() - t0,
                success=False,
            )

        duration = time.time() - t0
        files_changed = self._count_changed_files(mtimes_before)
        issues_fixed = self._parse_issues_fixed(result.stdout + result.stderr)

        success = result.returncode in (0, 1)

        return PreflightStepResult(
            tool=tool,
            files_changed=files_changed,
            issues_fixed=issues_fixed,
            duration_s=duration,
            success=success,
        )

    def _build_cmd(self, tool: str) -> list[str]:
        if tool == "ruff_check":
            cmd = ["uv", "run", "ruff", "check", "--fix", "."]
            # Stage 3: read unsafe-fix knob from HookSettings so CLI flags
            # (``--allow-unsafe-fixes``) and project config flow through the
            # same channel the rest of the hook system uses. The legacy
            # PreflightConfig.ruff_unsafe_fixes field is still honored when
            # no HookSettings were injected.
            if self._settings.ruff_unsafe_fixes or self._config.ruff_unsafe_fixes:
                cmd.insert(-1, "--unsafe-fixes")
            return cmd
        if tool == "ruff_format":
            return ["uv", "run", "ruff", "format", "."]
        if tool == "ruff_f401":
            return ["uv", "run", "ruff", "check", "--select", "F401", "--fix", "."]
        if tool == "ruff_extra":
            selects = ",".join(self._config.ruff_select_extra)
            return ["uv", "run", "ruff", "check", "--select", selects, "--fix", "."]
        if tool == "refurb":
            return ["uv", "run", "refurb", "."]
        return []

    def _guard_ruff_fix_invocation(
        self,
        tool: str,
        cmd: list[str],
    ) -> None:
        """Refuse to run a ruff --fix command on a dirty working tree.

        Stage 3 working-tree guard (production path). Called from
        ``_run_step_sync`` right before ``subprocess.run`` so the actual
        ruff invocation is gated by the working-tree state. ``ruff_format``
        does not mutate the tree, so it skips the guard by virtue of not
        having ``--fix`` in its command.

        The unsafe-fix knob doubles as the override flag: when
        ``ruff_unsafe_fixes=True`` the user has explicitly opted in to
        dangerous rewrites, so the guard is bypassed (matching
        ``--allow-dirty`` semantics).
        """
        if not (tool.startswith("ruff_") and "--fix" in cmd):
            return
        allow_dirty = bool(
            self._settings.ruff_unsafe_fixes or self._config.ruff_unsafe_fixes
        )
        try:
            validate_working_tree_clean(allow_dirty=allow_dirty)
        except DirtyWorkingTreeError:
            raise
        except Exception as e:
            raise DirtyWorkingTreeError(str(e)) from e

    def run_ruff_check(self) -> None:
        """Synchronous test seam for the working-tree guard.

        Stage 3 Round 1 retained this helper as a thin documentation seam so
        callers and tests can assert the guard contract directly without
        driving ``run()`` through ``asyncio.gather``. The actual production
        guard lives in ``_guard_ruff_fix_invocation`` and is invoked from
        ``_run_step_sync`` immediately before ``subprocess.run``.
        """
        self._guard_ruff_fix_invocation("ruff_check", ["ruff", "check", "--fix"])

    def _snapshot_mtimes(self) -> dict[Path, float]:
        mtimes: dict[Path, float] = {}
        for path in self._pkg_path.rglob("*.py"):
            with suppress(OSError):
                mtimes[path] = path.stat().st_mtime
        return mtimes

    def _count_changed_files(self, before: dict[Path, float]) -> int:
        changed = 0
        for path, mtime_before in before.items():
            with suppress(OSError):
                if path.stat().st_mtime != mtime_before:
                    changed += 1
        return changed

    def _parse_issues_fixed(self, output: str) -> int:
        m = re.search(r"Fixed (\d+) error", output)
        return int(m.group(1)) if m else 0
