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
    def __init__(
        self,
        sandbox: FixSandbox,
        in_process_fallback: Callable[[list[Any]], list[FixResult]] | None = None,
        fixer_registry: Any | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._in_process_fallback = in_process_fallback
        self._fixer_registry = fixer_registry

    def _serialize_plans(
        self, plans: list[Any], project_root: Path
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for plan in plans:
            payload = fix_runner.PlanPayload(
                fixer_id=_resolve_fixer_id(plan, registry=self._fixer_registry),
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
        if not plans:
            return []

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

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as plans_file:
            json.dump(payloads, plans_file)
            plans_path = Path(plans_file.name)

        output_path = project_root / "out.json"

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
            "crackerjack.ai_fix.fix_runner",
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

        try:
            plans_path.unlink()
        except OSError:
            pass

        if not sandbox_result.passed:
            is_validation_failure = sandbox_result.is_validation_failure
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

            return [
                FixResult(
                    success=False,
                    remaining_issues=[sandbox_result.reason or "sandbox failed"],
                )
                for _ in plans
            ]

        if not output_path.exists():
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

        try:
            output_path.unlink()
        except OSError:
            pass

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

        while len(fix_results) < len(plans):
            fix_results.append(
                FixResult(
                    success=False,
                    remaining_issues=["runner returned fewer results than plans"],
                )
            )

        return fix_results[: len(plans)]


def _resolve_fixer_id(
    plan: Any,
    registry: Any | None = None,
) -> str:
    """Resolve the fixer module:class string for a plan.

    Looks up the registered fixer by ``plan.issue_type`` in the optional
    ``FixerCoordinator.fixers`` registry. Falls back to
    ``crackerjack.agents.architect_agent:ArchitectAgent`` when the
    registry is missing, the issue type is not registered, or the
    resolver cannot derive a module:class string from the registered
    instance. This fallback preserves the prior default behavior so
    unregistered issue types still produce a runnable (if optimistic)
    fixer_id.
    """
    fallback = "crackerjack.agents.architect_agent:ArchitectAgent"
    if registry is None:
        return fallback
    issue_type = getattr(plan, "issue_type", None)
    if not isinstance(issue_type, str) or not issue_type:
        return fallback
    try:
        present = issue_type in registry
    except Exception:
        return fallback
    if not present:
        return fallback
    fixer = registry.get(issue_type)
    if fixer is None:
        return fallback
    cls = type(fixer)
    module = getattr(cls, "__module__", "")
    qualname = getattr(cls, "__qualname__", "") or getattr(cls, "__name__", "")
    if not module or not qualname:
        return fallback
    return f"{module}:{qualname}"


__all__ = ["SandboxedFixerDispatcher"]
