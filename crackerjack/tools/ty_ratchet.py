"""ty diagnostic-count ratchet gate.

Runs ``ty check`` and exits non-zero if the diagnostic count exceeds the
``[tool.crackerjack] ty_max_errors`` budget declared in ``pyproject.toml``.
Used as the primary type-check hook in the crackerjack comprehensive suite.

Why a separate script?
    ty itself (as of 0.0.42) has no ``--max-errors`` flag, and its
    config schema (environment/src/rules/terminal/analysis/overrides)
    doesn't accept a custom ``max_errors`` field. The ratchet is
    project policy, not a ty feature, so it lives at the crackerjack
    tooling layer. Keeping it as a standalone CLI means the same
    enforcement works in pre-commit, CI, and the crackerjack hook —
    three contexts, one ratchet.

Usage::

    python -m crackerjack.tools.ty_ratchet crackerjack
    python -m crackerjack.tools.ty_ratchet --max-errors 100 crackerjack
    python -m crackerjack.tools.ty_ratchet --dry-run --json crackerjack
    python -m crackerjack.tools.ty_ratchet --split --json --dry-run

Exit codes:
    0 - diagnostic count <= max_errors (gate passes)
    1 - diagnostic count > max_errors (gate fails) OR ty itself errored
    2 - config missing or malformed (operator error, not a quality failure)

Split mode:
    --split runs ty on ``crackerjack/`` and ``tests/`` separately and gates
    each against its own budget (``ty_max_errors_prod`` /
    ``ty_max_errors_test``). ``--max-errors`` is incompatible with ``--split``
    and exits 2 if both are passed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ty concise output format (one diagnostic per line):
#   <file>:<line>:<col>: error[<code>] <message>
#   <file>:<line>:<col>: warning[<code>] <message>
#
# Examples:
#   crackerjack/foo.py:10:5: error[invalid-argument-type] Argument to ...
#   crackerjack/foo.py:42:9: warning[unused-type-ignore-comment] ...
#
# ty emits a trailing summary line in concise mode:
#   "Found 252 diagnostics"
# Prefer that — it matches what ty itself reports. Fall back to
# counting diagnostic-prefixed lines if the summary is absent
# (e.g., older ty versions, or output format changes).
_CONCISE_DIAGNOSTIC_PREFIX = re.compile(r"^[\w./-]+:\d+:\d+:\s+(?:error|warning)\[")
_FOUND_DIAGNOSTICS_RE = re.compile(r"Found\s+(\d+)\s+diagnostics?")


def _read_max_errors(pyproject: Path) -> int:
    """Extract ``[tool.crackerjack] ty_max_errors`` from pyproject.toml.

    Lives in [tool.crackerjack] rather than [tool.ty] because ty
    v0.0.42's config schema is environment/src/rules/terminal/analysis/
    overrides only — no arbitrary ``max_errors`` slot. The ratchet
    budget is crackerjack policy, not ty config.

    Uses a hand-rolled parser rather than tomli because we only need
    one value from one section — pulling in a toml dep just for this
    is overkill, and the project already avoids tomli at runtime.

    Returns 250 (the Phase C baseline +1) if the field is absent so
    that operators without the ratchet configured don't suddenly see
    gate failures after upgrading.
    """
    try:
        text = pyproject.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 250

    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[tool.crackerjack]":
            in_section = True
            continue
        if in_section and stripped.startswith("[") and stripped.endswith("]"):
            break
        if in_section and stripped.startswith("ty_max_errors"):
            _, _, value = stripped.partition("=")
            try:
                return int(value.strip())
            except ValueError:
                print(
                    f"crackerjack/tools/ty_ratchet.py: malformed "
                    f"ty_max_errors value: {value!r}",
                    file=sys.stderr,
                )
                sys.exit(2)
    return 250


def _read_split_budget(pyproject: Path, key: str, default: int) -> int:
    """Extract ``ty_max_errors_prod`` or ``ty_max_errors_test`` from pyproject.toml.

    Same hand-rolled TOML parser pattern as ``_read_max_errors``. The
    budget is per-sub-package in split mode (``crackerjack/`` vs
    ``tests/``), so each has its own ``[tool.crackerjack]`` key with a
    distinct default. Exit 2 with a stderr message if the value is
    malformed so the operator sees a clear actionable cause.

    Returns ``default`` when the file or field is absent so operators
    who haven't yet configured the split budgets don't see gate
    failures after upgrading.
    """
    try:
        text = pyproject.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default

    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[tool.crackerjack]":
            in_section = True
            continue
        if in_section and stripped.startswith("[") and stripped.endswith("]"):
            break
        if in_section and stripped.startswith(key):
            _, _, value = stripped.partition("=")
            try:
                return int(value.strip())
            except ValueError:
                print(
                    f"crackerjack/tools/ty_ratchet.py: malformed "
                    f"{key} value: {value!r}",
                    file=sys.stderr,
                )
                sys.exit(2)
    return default


def _count_diagnostics(output: str) -> int:
    """Count diagnostics in ty concise output.

    Prefers the explicit ``Found N diagnostics`` summary line (matches
    what ty itself reports) and falls back to counting diagnostic-
    prefixed lines if the summary is absent.

    Returns -1 if no diagnostics were emitted at all (e.g. ty
    reported a configuration / startup error). Callers should
    treat -1 as a gate failure with operator-actionable cause.
    """
    summary = _FOUND_DIAGNOSTICS_RE.search(output)
    if summary:
        return int(summary.group(1))
    return sum(
        1 for line in output.splitlines() if _CONCISE_DIAGNOSTIC_PREFIX.match(line)
    )


def run_ty(target: str) -> subprocess.CompletedProcess[str]:
    """Invoke ty on ``target`` with concise, line-oriented output."""
    return subprocess.run(
        ["ty", "check", "--output-format", "concise", "--no-progress", target],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_split(args: argparse.Namespace) -> int:
    """Run ty on ``crackerjack/`` and ``tests/`` separately; gate each.

    Reads per-package budgets from ``[tool.crackerjack]`` and emits an
    additive JSON schema (legacy keys preserved + a ``mode`` discriminator
    and ``prod`` / ``test`` sub-objects). Returns 0 on full pass, 1 on
    any gate failure, 2 on config error. ``--dry-run`` short-circuits
    to 0 even if the gate would have failed (matches legacy semantics).
    """
    prod_max = _read_split_budget(
        args.pyproject,
        "ty_max_errors_prod",
        default=50,
    )
    test_max = _read_split_budget(
        args.pyproject,
        "ty_max_errors_test",
        default=30,
    )

    prod_result = run_ty("crackerjack")
    test_result = run_ty("tests")
    prod_count = _count_diagnostics(prod_result.stdout + prod_result.stderr)
    test_count = _count_diagnostics(test_result.stdout + test_result.stderr)

    prod_gate = 0 <= prod_count <= prod_max and prod_result.returncode == 0
    test_gate = 0 <= test_count <= test_max and test_result.returncode == 0
    overall = prod_gate and test_gate

    summary = {
        "mode": "split",
        "target": "crackerjack",
        "gate_passes": overall,
        "ty_exit_code": max(prod_result.returncode, test_result.returncode),
        "prod": {
            "diagnostic_count": prod_count,
            "max_errors": prod_max,
            "gate_passes": prod_gate,
        },
        "test": {
            "diagnostic_count": test_count,
            "max_errors": test_max,
            "gate_passes": test_gate,
        },
    }

    if args.as_json:
        print(json.dumps(summary, indent=2))
    else:
        prod_status = "PASS" if prod_gate else "FAIL"
        test_status = "PASS" if test_gate else "FAIL"
        print(f"ty ratchet [split] prod: {prod_status} ({prod_count}/{prod_max})")
        print(f"ty ratchet [split] test: {test_status} ({test_count}/{test_max})")
        if not overall:
            prod_tail = (prod_result.stdout + prod_result.stderr).splitlines()[-20:]
            test_tail = (test_result.stdout + test_result.stderr).splitlines()[-20:]
            print("\n".join(prod_tail), file=sys.stderr)
            print("\n".join(test_tail), file=sys.stderr)

    if args.dry_run:
        return 0

    return 0 if overall else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])  # ty: ignore[unresolved-attribute]
    parser.add_argument(
        "target",
        nargs="?",
        default="crackerjack",
        help="Path or package to type-check (default: crackerjack/)",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=None,
        help="Override the [tool.crackerjack] ty_max_errors budget.",
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml (default: ./pyproject.toml).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run ty and report the count without enforcing the gate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit a JSON summary on stdout (machine-readable for CI).",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="Run ty on crackerjack/ and tests/ separately; gate each independently.",
    )
    args = parser.parse_args(argv)

    # Q.1.B design: --max-errors errors out in split mode. The split
    # mode reads both budgets from pyproject.toml; a CLI override of
    # one of them would silently drop the other.
    if args.split and args.max_errors is not None:
        print(
            "Cannot use --max-errors with --split; use --pyproject to "
            "set ty_max_errors_prod and ty_max_errors_test.",
            file=sys.stderr,
        )
        return 2

    if args.split:
        return _run_split(args)

    max_errors = args.max_errors
    if max_errors is None:
        max_errors = _read_max_errors(args.pyproject)

    result = run_ty(args.target)
    count = _count_diagnostics(result.stdout + result.stderr)

    summary = {
        "target": args.target,
        "diagnostic_count": count,
        "max_errors": max_errors,
        "gate_passes": 0 <= count <= max_errors,
        "ty_exit_code": result.returncode,
    }

    if args.as_json:
        print(json.dumps(summary, indent=2))
    else:
        status = "PASS" if summary["gate_passes"] else "FAIL"
        print(
            f"ty ratchet [{status}]: {count} diagnostics, "
            f"max_errors={max_errors} "
            f"(over budget by {max(0, count - max_errors)})",
        )
        if not summary["gate_passes"]:
            tail = (result.stdout + result.stderr).splitlines()[-20:]
            print("\n".join(tail), file=sys.stderr)

    if args.dry_run:
        return 0

    if not summary["gate_passes"] or result.returncode != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
