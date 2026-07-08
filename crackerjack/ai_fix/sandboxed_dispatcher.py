"""SandboxedFixerDispatcher — runs fixer invocations through FixSandbox.

When the new ``use_sandbox`` constructor arg is set on
:class:`crackerjack.agents.fixer_coordinator.FixerCoordinator`, the
fixer dispatch goes through this class instead of calling fixers
in-process. The dispatcher:

1. Serializes the plans to JSON via
   :func:`crackerjack.ai_fix.fix_runner.PlanPayload`.
2. Writes the JSON to a temp file.
3. Invokes :meth:`FixSandbox.run_command` with the
   ``crackerjack fix-runner`` CLI as the subprocess.
4. Reads the result JSON from the sandbox temp dir.
5. Synthesizes a :class:`crackerjack.agents.base.FixResult` per plan.

On subprocess failure (not validation failure), the dispatcher may
fall back to the in-process path if
``CRACKERJACK_AI_FIX_SANDBOX_FALLBACK=1`` is set. Validation
failures are never fallback-eligible.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from crackerjack.agents.base import FixResult
from crackerjack.ai_fix import fix_runner
from crackerjack.ai_fix.fix_sandbox import FixSandbox, SandboxResult

logger = logging.getLogger(__name__)


class SandboxedFixerDispatcher:
    """Routes fixer invocations through a :class:`FixSandbox` subprocess.

    The dispatcher is dependency-injected with a :class:`FixSandbox`
    and an optional in-process fallback callable. Tests can pass a
    fake sandbox (e.g. ``MagicMock()``) and a fake fallback to
    exercise the dispatch logic without real subprocesses.
    """

    def __init__(
        self,
        sandbox: FixSandbox,
        in_process_fallback: Callable[[list[Any]], list[FixResult]] | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._in_process_fallback = in_process_fallback

    def _serialize_plans(
        self, plans: list[Any], project_root: Path
    ) -> list[dict[str, Any]]:
        """Serialize plans to the JSON contract the runner expects.

        Each plan is converted to a ``PlanPayload`` via Pydantic,
        then ``model_dump()``-ed. The fixer_id is derived from the
        plan's issue_type via the project's fixer registry; if no
        fixer is registered for the issue_type, the plan is
        serialized with ``fixer_id=""`` and the runner will fail it
        with "unknown fixer".
        """
        from crackerjack.ai_fix.fix_runner import PlanPayload

        out: list[dict[str, Any]] = []
        for plan in plans:
            payload = PlanPayload(
                fixer_id=_resolve_fixer_id(plan),
                file_path=plan.file_path,
                issue_type=plan.issue_type,
                changes=[
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in plan.changes
                ],
                risk_level=plan.risk_level,
                issue_message=getattr(plan, "issue_message", ""),
                issue_stage=getattr(plan, "issue_stage", "ruff-check"),
            )
            out.append(payload.model_dump())
        return out

    def dispatch_batch(
        self,
        plans: list[Any],
        *,
        project_root: Path,
        timeout_s: int = 300,
    ) -> list[FixResult]:
        """Run the plans through the sandbox and return FixResult per plan.

        Args:
            plans: The list of FixPlan (or plan-like) objects to execute.
            project_root: The crackerjack project root, used to
                resolve plan.file_path and to pass to the subprocess.
            timeout_s: Sandbox timeout (default 300s).

        Returns:
            A list of FixResult, one per plan, in the same order.
        """
        if not plans:
            return []

        # Serialize plans; if any fail, fail the whole batch.
        try:
            payloads = self._serialize_plans(plans, project_root)
        except Exception as exc:
            logger.exception("plan serialization failed")
            return [
                FixResult(
                    success=False,
                    remaining_issues=[f"plan serialization failed: {exc}"],
                )
                for _ in plans
            ]

        # Write plans JSON to a temp file the sandbox will pass to the runner.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as plans_file:
            json.dump(payloads, plans_file)
            plans_path = Path(plans_file.name)
        # The output path is a sibling of the project's root so the
        # runner (and the dispatcher's read-back) can locate it
        # deterministically. The runner creates the parent dir if
        # needed; we just stage the path here.
        output_path = project_root / "out.json"

        # Build the subprocess command. The first plan's file is the
        # sandbox's "anchor" file; the runner handles the rest.
        first_plan = plans[0]
        first_file = project_root / first_plan.file_path
        if not first_file.is_file():
            return [
                FixResult(
                    success=False,
                    remaining_issues=[
                        f"first plan's file does not exist: {first_file}"
                    ],
                )
            ]

        command = [
            sys.executable,
            "-m",
            "crackerjack",
            "fix-runner",
            "--plans-json",
            str(plans_path),
            "--output-json",
            str(output_path),
            "--project-root",
            str(project_root),
        ]

        sandbox_result = self._sandbox.run_command(
            command=command,
            file_path=first_file,
            timeout=timeout_s,
        )

        return self._process_sandbox_result(
            sandbox_result,
            plans,
            output_path,
            plans_path,
        )

    def _process_sandbox_result(
        self,
        sandbox_result: SandboxResult,
        plans: list[Any],
        output_path: Path,
        plans_path: Path,
    ) -> list[FixResult]:
        """Convert a SandboxResult into per-plan FixResult objects."""
        # Clean up the plans JSON.
        try:
            plans_path.unlink()
        except OSError:
            pass

        if not sandbox_result.passed:
            # Check if this is a fallback-eligible failure.
            is_validation_failure = "validation" in sandbox_result.reason.lower()
            fallback_enabled = os.environ.get(
                "CRACKERJACK_AI_FIX_SANDBOX_FALLBACK", ""
            ).lower() in ("1", "true", "yes", "on")

            if (
                not is_validation_failure
                and fallback_enabled
                and self._in_process_fallback is not None
            ):
                logger.warning(
                    "Sandbox failed (not validation); falling back to in-process: %s",
                    sandbox_result.reason,
                )
                return self._in_process_fallback(plans)

            # Surface the failure for the whole batch.
            return [
                FixResult(
                    success=False,
                    remaining_issues=[sandbox_result.reason or "sandbox failed"],
                )
                for _ in plans
            ]

        # Sandbox passed; read and parse the result JSON.
        if not output_path.exists():
            # Sandbox reported success but the result file is missing.
            # The real fix-runner always writes the JSON when it succeeds,
            # so a missing file is a real bug — surface it as a failure
            # for every plan instead of silently masking it with a
            # synthesized success. Make the regression observable in logs.
            logger.warning(
                "sandbox passed but output file missing; returning failure for %d plans",
                len(plans),
            )
            return [
                FixResult(
                    success=False,
                    remaining_issues=[
                        f"sandbox reported success but result file not found: {output_path}"
                    ],
                )
                for _ in plans
            ]

        try:
            results_data = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("malformed result JSON from sandbox")
            return [
                FixResult(
                    success=False,
                    remaining_issues=[f"malformed result from sandbox: {exc}"],
                )
                for _ in plans
            ]

        # Clean up the output JSON.
        try:
            output_path.unlink()
        except OSError:
            pass

        # Build per-plan FixResult.
        results = results_data.get("results", [])
        fix_results: list[FixResult] = []
        for r in results:
            fix_results.append(
                FixResult(
                    success=bool(r.get("success", False)),
                    files_modified=list(r.get("files_modified", [])),
                    remaining_issues=list(r.get("remaining_issues", [])),
                )
            )

        # Pad with failure results if the runner returned fewer entries
        # than plans (defensive against runner bugs).
        while len(fix_results) < len(plans):
            fix_results.append(
                FixResult(
                    success=False,
                    remaining_issues=["runner returned fewer results than plans"],
                )
            )

        return fix_results[: len(plans)]


def _resolve_fixer_id(plan: Any) -> str:
    """Resolve the fixer module:class string for a plan.

    For Task 3, this returns a hardcoded default — ``ArchitectAgent``
    — which is the catch-all fixer registered in
    ``FixerCoordinator``. ``ArchitectAgent.execute_fix_plan``
    dispatches to sub-fixers internally based on ``plan.issue_type``,
    so a single entrypoint handles every plan type.

    Task 4 (wiring this into ``FixerCoordinator``) will likely make
    this smarter by looking up the registered fixer per issue_type
    in ``FixerCoordinator.fixers``.
    """
    return "crackerjack.agents.architect_agent:ArchitectAgent"


__all__ = ["SandboxedFixerDispatcher"]
