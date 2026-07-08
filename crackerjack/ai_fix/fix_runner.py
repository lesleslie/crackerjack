"""Subprocess driver for the fix-runner CLI.

This module is invoked as ``python -m crackerjack fix-runner`` by the
:mod:`crackerjack.ai_fix.sandboxed_dispatcher` subprocess. It is NOT
registered as a top-level crackerjack subcommand; it exists only as
the receiving end of the sandbox subprocess.

The runner:
1. Reads a list of plans from a JSON file.
2. For each plan, copies the target file into the working directory
   as ``out_N.py`` (the first plan is ``out.py`` to satisfy the
   sandbox's contract — see ``crackerjack/ai_fix/fix_sandbox.py:164``).
3. Dispatches each plan to the fixer class identified by
   ``plan.fixer_id`` (format ``"module.path:ClassName"``).
4. Validates each output file via
   :class:`crackerjack.ai_fix.output_validator.OutputValidator`.
5. Writes a JSON result file with per-plan outcomes.
6. Exits 0 if all plans succeeded, 1 if any failed, 2 on setup error.

The fixer's execution method follows the same ``hasattr`` dispatch as
``crackerjack.agents.fixer_coordinator.FixerCoordinator._execute_single_plan``
(lines 206-222): ``execute_fix_plan`` first, then ``analyze_and_fix``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Exit codes
EXIT_OK = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_SETUP_ERROR = 2


class PlanPayload(BaseModel):
    """The JSON contract for a single plan passed to the runner.

    Mirrors the relevant fields of ``crackerjack.models.fix_plan.FixPlan``
    without the model dependency (so the runner is decoupled from
    the production plan model).
    """

    fixer_id: str
    file_path: str
    issue_type: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    risk_level: str
    issue_message: str
    issue_stage: str


class PlanResult(BaseModel):
    """The JSON contract for a single plan's result."""

    plan_idx: int
    success: bool
    modified_content: str | None = None
    files_modified: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    reason: str = ""


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crackerjack fix-runner",
        description="Subprocess driver for sandboxed fixer invocations.",
    )
    parser.add_argument(
        "--plans-json",
        type=Path,
        required=True,
        help="Path to the input JSON file containing the plans.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Path to write the per-plan results JSON.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="The crackerjack project root; used to resolve file_path.",
    )
    return parser.parse_args(argv)


def _load_fixer(fixer_id: str) -> Any:
    """Load a fixer class from ``module.path:ClassName``.

    Returns the class, not an instance. The caller instantiates.
    Raises ``ValueError`` on parse or import failure.
    """
    if ":" not in fixer_id:
        raise ValueError(f"invalid fixer_id (no ':'): {fixer_id!r}")
    module_path, class_name = fixer_id.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ValueError(f"unknown fixer module {module_path!r}: {exc}") from exc
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(
            f"unknown fixer class {class_name!r} in {module_path!r}"
        ) from exc


def _dispatch_fixer(fixer_instance: Any, plan: PlanPayload) -> tuple[bool, str]:
    """Dispatch a plan to a fixer instance, returning ``(success, reason)``.

    Follows the same ``hasattr`` dispatch as
    ``FixerCoordinator._execute_single_plan``: try ``execute_fix_plan``
    first, then ``analyze_and_fix``.
    """
    if hasattr(fixer_instance, "execute_fix_plan"):
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    fixer_instance.execute_fix_plan(plan.model_dump())
                )
            finally:
                loop.close()
        except Exception as exc:
            return False, f"fixer raised: {exc}"
        return bool(result), ""
    if hasattr(fixer_instance, "analyze_and_fix"):
        return False, (
            f"fixer {type(fixer_instance).__name__} exposes analyze_and_fix "
            "(requires Issue reconstruction; not supported in fix-runner)"
        )
    return False, (
        f"fixer {type(fixer_instance).__name__} lacks execute_fix_plan "
        "or analyze_and_fix"
    )


def _read_output(out_path: Path) -> str | None:
    """Read the fixer's output file, returning ``None`` if absent."""
    if not out_path.exists():
        return None
    try:
        return out_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _process_plan(
    plan_idx: int,
    plan: PlanPayload,
    workdir: Path,
    project_root: Path,
    original_validator: Any,
) -> PlanResult:
    """Process a single plan within the workdir."""
    out_name = "out.py" if plan_idx == 0 else f"out_{plan_idx}.py"
    out_path = workdir / out_name

    # Resolve the source file relative to project root.
    src = project_root / plan.file_path
    if not src.is_file():
        # Prep failure: we cannot even start work on this plan.
        raise ValueError(f"source file does not exist: {src}")

    try:
        shutil.copy2(src, out_path)
    except OSError as exc:
        raise ValueError(f"could not copy source: {exc}") from exc

    # Load + instantiate the fixer. A load failure is a setup error
    # (we cannot dispatch any work), so propagate it for the caller
    # to map to EXIT_SETUP_ERROR.
    try:
        fixer_cls = _load_fixer(plan.fixer_id)
    except ValueError:
        raise

    try:
        fixer_instance = fixer_cls(project_path=str(project_root))
    except Exception:
        # Some fixers don't take a project_path; try no-arg.
        try:
            fixer_instance = fixer_cls()
        except Exception as exc:
            return PlanResult(
                plan_idx=plan_idx,
                success=False,
                remaining_issues=[f"could not instantiate fixer: {exc}"],
            )

    success, reason = _dispatch_fixer(fixer_instance, plan)
    if not success:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=[reason or "fixer reported failure"],
        )

    # Read the modified output and validate.
    modified = _read_output(out_path)
    if modified is None:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=["fixer did not produce output file"],
        )

    # Only validate Python files (matches FixSandbox's behavior).
    if out_path.suffix == ".py":
        validation = original_validator.validate(out_path)
        if not validation.passed:
            return PlanResult(
                plan_idx=plan_idx,
                success=False,
                remaining_issues=[f"output validation failed: {validation.reason}"],
            )

    return PlanResult(
        plan_idx=plan_idx,
        success=True,
        modified_content=modified,
        files_modified=[str(src)],
    )


def run(argv: list[str] | None = None) -> int:
    """Main entry point. Returns the process exit code."""
    from crackerjack.ai_fix.output_validator import OutputValidator

    args = _parse_args(argv)
    validator = OutputValidator()

    if not args.plans_json.is_file():
        logger.exception("plans-json not found: %s", args.plans_json)
        return EXIT_SETUP_ERROR

    try:
        plans_data = json.loads(args.plans_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("could not read plans JSON")
        return EXIT_SETUP_ERROR

    workdir = Path.cwd()
    results: list[PlanResult] = []

    for idx, raw in enumerate(plans_data):
        try:
            plan = PlanPayload.model_validate(raw)
        except Exception as exc:
            results.append(
                PlanResult(
                    plan_idx=idx,
                    success=False,
                    remaining_issues=[f"plan validation failed: {exc}"],
                )
            )
            continue
        try:
            result = _process_plan(idx, plan, workdir, args.project_root, validator)
        except ValueError:
            logger.exception("fixer load failed for plan %d", idx)
            return EXIT_SETUP_ERROR
        results.append(result)

    # Write the output JSON.
    try:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps({"results": [r.model_dump() for r in results]}),
            encoding="utf-8",
        )
    except OSError:
        logger.exception("could not write output JSON to %s", args.output_json)
        return EXIT_SETUP_ERROR

    return EXIT_OK if all(r.success for r in results) else EXIT_PARTIAL_FAILURE


def main() -> int:
    """Entry point for ``python -m crackerjack fix-runner``."""
    return run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "EXIT_OK",
    "EXIT_PARTIAL_FAILURE",
    "EXIT_SETUP_ERROR",
    "PlanPayload",
    "PlanResult",
    "run",
]
