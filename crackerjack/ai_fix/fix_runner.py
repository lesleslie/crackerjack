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


EXIT_OK = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_SETUP_ERROR = 2


class PlanPayload(BaseModel):
    fixer_id: str
    file_path: str
    issue_type: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    risk_level: str
    issue_message: str
    issue_stage: str


class PlanResult(BaseModel):
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


def _payload_to_fix_plan(plan: PlanPayload) -> Any:
    from crackerjack.models.fix_plan import ChangeSpec, FixPlan

    plan_dict = plan.model_dump()
    changes_raw = plan_dict.get("changes", []) or []
    changes: list[ChangeSpec] = []
    for c in changes_raw:
        if not isinstance(c, dict):
            continue
        line_range_value = c.get("line_range") or (0, 0)
        if not isinstance(line_range_value, (list, tuple)) or len(line_range_value) < 2:
            line_range_value = (0, 0)
        else:
            line_range_value = (
                int(line_range_value[0]),
                int(line_range_value[1]),
            )
        changes.append(
            ChangeSpec(
                line_range=line_range_value,
                old_code=str(c.get("old_code", "")),
                new_code=str(c.get("new_code", "")),
                reason=str(c.get("reason", "")),
            )
        )

    file_path = str(plan_dict.get("file_path", ""))
    issue_type = str(plan_dict.get("issue_type", ""))
    risk_level = str(plan_dict.get("risk_level", "low"))
    if risk_level not in ("low", "medium", "high"):
        risk_level = "low"
    issue_message = str(plan_dict.get("issue_message", ""))
    issue_stage = str(plan_dict.get("issue_stage", "ruff-check"))

    return FixPlan(
        file_path=file_path,
        issue_type=issue_type,
        risk_level=risk_level,
        validated_by=str(plan_dict.get("fixer_id", "fix-runner")),
        rationale=issue_message,
        changes=changes,
        issue_message=issue_message,
        issue_stage=issue_stage,
        issue_details=[],
    )


def _instantiate_fixer(fixer_cls: Any, project_root: Path) -> Any | None:
    from crackerjack.agents.base import AgentContext

    context = AgentContext(project_path=project_root, config={})

    for bind in (
        fixer_cls(context=context),
        fixer_cls(project_path=str(project_root)),
        fixer_cls,
    ):
        try:
            return bind()
        except Exception:
            continue
    return None


def _dispatch_fixer(fixer_instance: Any, plan: PlanPayload) -> tuple[bool, str]:
    if hasattr(fixer_instance, "execute_fix_plan"):
        import asyncio

        fix_plan = _payload_to_fix_plan(plan)
        try:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    fixer_instance.execute_fix_plan(fix_plan)
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
    out_name = "out.py" if plan_idx == 0 else f"out_{plan_idx}.py"
    out_path = workdir / out_name

    src = project_root / plan.file_path
    if not src.is_file():
        raise ValueError(f"source file does not exist: {src}")

    try:
        shutil.copy2(src, out_path)
    except OSError as exc:
        raise ValueError(f"could not copy source: {exc}") from exc

    try:
        fixer_cls = _load_fixer(plan.fixer_id)
    except ValueError:
        raise

    fixer_instance = _instantiate_fixer(fixer_cls, project_root)
    if fixer_instance is None:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=[
                f"could not instantiate fixer {fixer_cls.__name__} "
                "(tried context=, project_path=, and no-arg)"
            ],
        )

    success, reason = _dispatch_fixer(fixer_instance, plan)
    if not success:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=[reason or "fixer reported failure"],
        )

    modified = _read_output(out_path)
    if modified is None:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=["fixer did not produce output file"],
        )

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
