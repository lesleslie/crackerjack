from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_CONCISE_DIAGNOSTIC_PREFIX = re.compile(r"^[\w./-]+:\d+:\d+:\s+(?:error|warning)\[")
_FOUND_DIAGNOSTICS_RE = re.compile(r"Found\s+(\d+)\s+diagnostics?")


def _read_max_errors(pyproject: Path) -> int:
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
    summary = _FOUND_DIAGNOSTICS_RE.search(output)
    if summary:
        return int(summary.group(1))
    return sum(
        1 for line in output.splitlines() if _CONCISE_DIAGNOSTIC_PREFIX.match(line)
    )


def run_ty(target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ty", "check", "--output-format", "concise", "--no-progress", target],
        capture_output=True,
        text=True,
        check=False,
    )


def _zero_result() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="",
        stderr="",
    )


def _run_split(args: argparse.Namespace) -> int:
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

    prod_exists = Path(args.prod_dir).is_dir()
    test_exists = Path(args.test_dir).is_dir()

    if not prod_exists:
        print(
            f"⚠️ ty_ratchet: prod dir {args.prod_dir!r} does not exist; "
            f"treating prod gate as 0/0 (vacuously passing).",
            file=sys.stderr,
        )
    if not test_exists:
        print(
            f"⚠️ ty_ratchet: test dir {args.test_dir!r} does not exist; "
            f"treating test gate as 0/0 (vacuously passing, advisory only).",
            file=sys.stderr,
        )

    prod_result = run_ty(args.prod_dir) if prod_exists else _zero_result()
    test_result = run_ty(args.test_dir) if test_exists else _zero_result()
    prod_count = _count_diagnostics(prod_result.stdout + prod_result.stderr)
    test_count = _count_diagnostics(test_result.stdout + test_result.stderr)

    prod_gate = 0 <= prod_count <= prod_max and prod_result.returncode == 0
    test_gate = 0 <= test_count <= test_max and test_result.returncode == 0

    overall_exit = prod_gate

    summary = {
        "mode": "split",
        "target": "crackerjack",
        "prod_dir": args.prod_dir,
        "test_dir": args.test_dir,
        "prod_dir_exists": prod_exists,
        "test_dir_exists": test_exists,
        "gate_passes": prod_gate and test_gate,
        "prod_gate_passes": prod_gate,
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
        if not test_gate:
            test_combined = (test_result.stdout + test_result.stderr).splitlines()
            if not args.verbose:
                test_combined = test_combined[-20:]
            print(
                f"⚠️ ty: test ratchet FAIL ({test_count}/{test_max}) — "
                f"advisory only; prod gate {'PASS' if prod_gate else 'FAIL'} "
                f"({prod_count}/{prod_max}) controls the exit code.",
                file=sys.stderr,
            )
            print("\n".join(test_combined), file=sys.stderr)
        if not prod_gate:
            prod_combined = (prod_result.stdout + prod_result.stderr).splitlines()
            if not args.verbose:
                prod_combined = prod_combined[-20:]
            print("\n".join(prod_combined), file=sys.stderr)

    if args.dry_run:
        return 0

    return 0 if overall_exit else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "Type-check ratchet").split("\n\n")[0]
    )
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
    parser.add_argument(
        "--prod-dir",
        default="crackerjack",
        help="Path to type-check as the prod gate (default: crackerjack). "
        "Used only with --split.",
    )
    parser.add_argument(
        "--test-dir",
        default="tests",
        help="Path to type-check as the test gate (default: tests). "
        "Used only with --split.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Do not truncate diagnostic-tail output to the last 20 lines "
        "per failing dir. Use when the consumer (crackerjack) needs to "
        "inspect every diagnostic in stderr; the wrapper still emits "
        "the authoritative 'Found N diagnostics' summary either way.",
    )
    args = parser.parse_args(argv)

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
            tail_lines = (result.stdout + result.stderr).splitlines()
            if not args.verbose:
                tail_lines = tail_lines[-20:]
            print("\n".join(tail_lines), file=sys.stderr)

    if args.dry_run:
        return 0

    if not summary["gate_passes"] or result.returncode != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
