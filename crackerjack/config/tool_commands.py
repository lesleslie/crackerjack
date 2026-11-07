from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from functools import lru_cache, partial
from pathlib import Path

from crackerjack.config.per_file_ignores import build_inline_per_file_ignores
from crackerjack.config.refurb_args import build_refurb_mypy_args
from crackerjack.config.settings import HookSettings


@lru_cache(maxsize=8)
def _detect_package_name_cached(pkg_path_str: str) -> str:
    pkg_path = Path(pkg_path_str)
    pyproject_path = pkg_path / "pyproject.toml"
    if pyproject_path.exists():
        from contextlib import suppress

        with suppress(Exception):
            import tomllib

            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
                project_name = data.get("project", {}).get("name")
                if project_name:
                    return project_name.replace("-", "_")

    from contextlib import suppress as _suppress

    for item in pkg_path.iterdir():
        if item.name.startswith("."):
            continue
        if not item.is_dir():
            continue
        with _suppress(OSError):
            if (item / "__init__.py").exists():
                if item.name not in {"tests", "docs", ".venv", "venv", "build", "dist"}:
                    return item.name

    return pkg_path.name.replace("-", "_")


def _python_module_command(module: str, *args: str) -> list[str]:
    return [sys.executable, "-m", module, *args]


def _build_targets(package_name: str) -> list[str]:
    """Canonical target list for tools that walk multiple directories.

    Used by ruff-check, ruff-format, codespell, tc-refs, and any future
    tool that should cover both the package and the scripts/examples dirs.

    Targets are filtered to existing directories. The `scripts/` and
    `examples/` subdirectories are optional — consumer repos that lack
    them (e.g., a library that ships only the package) won't fail tool
    invocations with "directory not found".
    """
    candidates = [f"./{package_name}", "./scripts", "./examples"]
    return [p for p in candidates if Path(p).is_dir()]


def preferred_binary_command(tool_name: str, *args: str) -> list[str]:
    venv_tool = Path.cwd() / ".venv" / "bin" / tool_name
    if venv_tool.exists():
        return [str(venv_tool), *args]

    resolved = shutil.which(tool_name)
    if resolved:
        return [resolved, *args]

    return [tool_name, *args]


_VERSION_RE = re.compile(r"\b(\d+(?:\.\d+)*)\b")


def _parse_version(raw: str) -> tuple[int, ...] | None:
    """Extract the first dotted-number version from a ``--version`` output."""
    match = _VERSION_RE.search(raw)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


@lru_cache(maxsize=64)
def _probe_tool_version(binary: str) -> tuple[int, ...] | None:
    """Return the version a binary reports, or ``None`` if it cannot be probed.

    Cached because resolution happens on every hook invocation and a
    subprocess per invocation is not affordable.
    """
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return _parse_version(f"{result.stdout}\n{result.stderr}")


def _version_at_least(found: tuple[int, ...], minimum: tuple[int, ...]) -> bool:
    width = max(len(found), len(minimum))
    padded_found = found + (0,) * (width - len(found))
    padded_minimum = minimum + (0,) * (width - len(minimum))
    return padded_found >= padded_minimum


def _binary_candidates(tool_name: str) -> list[str]:
    """Every executable named ``tool_name`` visible to this process, in order.

    ``shutil.which`` returns only the FIRST match. That is not enough when
    the first match is too old to use: an unrelated project's venv on PATH
    can shadow the binary the caller actually wants. The project venv is
    preferred, then PATH is walked in order.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        resolved = str(path)
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    venv_tool = Path.cwd() / ".venv" / "bin" / tool_name
    if venv_tool.exists():
        _add(venv_tool)

    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / tool_name
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                _add(candidate)
        except OSError:
            continue

    return candidates


def preferred_binary_command_with_min_version(
    tool_name: str, min_version: str, *args: str
) -> list[str]:
    """Resolve ``tool_name`` to a binary reporting at least ``min_version``.

    Candidates are tried in priority order (the project venv first, then
    ``PATH``) and the first one whose reported version satisfies the floor
    wins. A binary that is too old is *skipped*, not used: crackerjack's
    pyscn report schema changed at 1.30, so an older binary produces output
    the parser cannot read.

    Raises ``RuntimeError`` when no candidate qualifies, naming every
    candidate that was inspected and the version it reported.
    """
    minimum = _parse_version(min_version)
    if minimum is None:
        msg = f"Invalid minimum version {min_version!r} for {tool_name!r}"
        raise ValueError(msg)

    inspected: list[str] = []
    for candidate in _binary_candidates(tool_name):
        found = _probe_tool_version(candidate)
        if found is None:
            inspected.append(f"{candidate} (version unknown)")
            continue
        if _version_at_least(found, minimum):
            return [candidate, *args]
        rendered = ".".join(str(part) for part in found)
        inspected.append(f"{candidate} (version {rendered})")

    detail = ", ".join(inspected) if inspected else "no candidates found"
    msg = (
        f"{tool_name} >= {min_version} is required, but no installed "
        f"{tool_name} satisfies that floor. Inspected: {detail}. "
        f"Install a current {tool_name} (for pyscn: `brew install pyscn`) "
        f"or remove the outdated binary from PATH."
    )
    raise RuntimeError(msg)


def preferred_binary_command_with_report(
    tool_name: str, report_path: str, *args: str
) -> list[str]:
    """Build a command and ensure the report path's parent directory exists.

    Betterleaks and gitleaks open ``--report-path`` for writing. If the parent
    directory (typically ``.cache/``) is missing, the binary fails with
    "Report path is not writable" instead of producing the JSON report. This
    helper creates the parent directory idempotently before returning the
    command, so the binary can write the report without a separate bootstrap.
    """
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    return preferred_binary_command(tool_name, *args)


def _build_tool_commands(
    package_name: str,
) -> dict[str, list[str] | Callable[[], list[str]]]:
    return {
        "plan-index-sync": _python_module_command(
            "crackerjack.tools.plan_index_sync",
            "--repo-root",
            ".",
            "--out",
            "docs/plans/PLAN_INDEX.md",
        ),
        "validate-regex-patterns": _python_module_command(
            "crackerjack.tools.validate_regex_patterns"
        ),
        "ty-ignore-syntax": _python_module_command(
            "crackerjack.tools.ty_ignore_syntax",
            "--exclude",
            "tools",
        ),
        "ty": preferred_binary_command(
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.ty_ratchet",
            "--split",
            "--prod-dir",
            f"./{package_name}",
            "--test-dir",
            "tests",
        ),
        "pyrefly": preferred_binary_command(
            "pyrefly",
            "check",
            "--output-format",
            "json",
            "--summary",
            "none",
            "--no-progress-bar",
            f"./{package_name}",
        ),
        "trailing-whitespace": _python_module_command(
            "crackerjack.tools.trailing_whitespace"
        ),
        "end-of-file-fixer": _python_module_command(
            "crackerjack.tools.end_of_file_fixer"
        ),
        "check-yaml": _python_module_command("crackerjack.tools.check_yaml"),
        "check-toml": _python_module_command("crackerjack.tools.check_toml"),
        "check-json": _python_module_command("crackerjack.tools.check_json"),
        "format-json": _python_module_command("crackerjack.tools.format_json"),
        "check-jsonschema": _python_module_command(
            "crackerjack.tools.check_jsonschema",
            "-o",
            "json",
        ),
        "check-ast": _python_module_command("crackerjack.tools.check_ast"),
        "check-added-large-files": _python_module_command(
            "crackerjack.tools.check_added_large_files",
            "--maxkb",
            "1000",
            "--suggest-gitignore",
        ),
        "uv-lock": ["uv", "lock"],
        "betterleaks": preferred_binary_command_with_report(
            "betterleaks",
            ".cache/betterleaks-report.json",
            "dir",
            ".",
            "--report-format",
            "json",
            "--report-path",
            ".cache/betterleaks-report.json",
        ),
        "gitleaks": preferred_binary_command_with_report(
            "gitleaks",
            ".cache/gitleaks-report.json",
            "protect",
            "--report-format",
            "json",
            "--report-path",
            ".cache/gitleaks-report.json",
            "-v",
        ),
        "bandit": _python_module_command(
            "bandit",
            "-r",
            "--format",
            "json",
            "--severity-level",
            "low",
            "--confidence-level",
            "low",
            "-x",
            "tests",
            f"./{package_name}",
        ),
        "semgrep": preferred_binary_command(
            "semgrep",
            "scan",
            "--quiet",
            "--error",
            "--json",
            "--config",
            "p/security-audit",
            "--exclude",
            ".pytest_cache",
            "--exclude",
            ".ruff_cache",
            "--exclude",
            "__pycache__",
            "--exclude",
            "tests",
            f"./{package_name}",
        ),
        "codespell": _python_module_command(
            "crackerjack.tools.codespell_wrapper",
            *_build_targets(package_name),
        ),
        "ruff-check": _python_module_command(
            "ruff",
            "check",
            "--output-format",
            "json",
            "--fix",
            "--config",
            f"lint.extend-per-file-ignores = {build_inline_per_file_ignores()}",
            *_build_targets(package_name),
        ),
        "ruff-format": _python_module_command(
            "ruff",
            "format",
            *_build_targets(package_name),
        ),
        "mdformat": _python_module_command("crackerjack.tools.mdformat_wrapper"),
        "check-local-links": _python_module_command(
            "crackerjack.tools.local_link_checker"
        ),
        "linkcheckmd": _python_module_command("crackerjack.tools.linkcheckmd_wrapper"),
        "tc-refs": _python_module_command(
            "crackerjack.tools.audit_type_checking_runtime_refs",
            *_build_targets(package_name),
        ),
        "no-conflict-markers": _python_module_command(
            "crackerjack.tools.no_conflict_markers"
        ),
        "creosote": preferred_binary_command(
            "creosote",
            "--venv",
            ".venv",
            "-p",
            package_name,
            "--include-deferred",
        ),
        "complexipy": preferred_binary_command(
            "complexipy",
            "--max-complexity-allowed",
            "25",
            "--failed",
            "--quiet",
            "--output-format",
            "json",
            "--output",
            f"/tmp/complexipy_results_{os.getpid()}.json",
            "-e",
            "tests",
            "-e",
            "test_*.py",
            package_name,
        ),
        "cohesion": preferred_binary_command(
            "cohesion",
            "-d",
            package_name,
            "-b",
            "70",
        ),
        "pymetrica": preferred_binary_command(
            "pymetrica",
            "run-all",
            f"./{package_name}",
            "-a",
        ),
        "refurb": _python_module_command("refurb", f"{package_name}/"),
        "osv-scanner": [
            "osv-scanner",
            "scan",
            "source",
            "--lockfile=uv.lock",
            "--format=json",
        ],
        # Resolved lazily via partial: the version probe spawns a subprocess,
        # and this module builds its command table at import time.
        "pyscn": partial(
            preferred_binary_command_with_min_version,
            "pyscn",
            "1.30",
            "analyze",
            "--select",
            "complexity,deadcode",
            "--json",
            "--min-complexity",
            "5",
            package_name,
        ),
        "lychee": [
            "lychee",
            "--format",
            "json",
            "--no-progress",
            "--cache",
            "--accept",
            "100..=103,200..=299,429",
            # Archive directories (`<area>/.archive/` and the
            # `docs/archive/` legacy tree) contain historical docs with
            # cross-references to other archived files that no longer
            # exist. Their broken internal links aren't a quality issue
            # for active development — same exclusion the fast hook
            # `local-link-checker` applies on line 182 of
            # `crackerjack/tools/local_link_checker.py`. The substring
            # `archive/` matches both `.archive/` and `archive/`.
            "--exclude-path",
            "archive/",
            "--verbose",
            ".",
        ],
    }


@lru_cache(maxsize=8)
def _build_tool_commands_cached(
    package_name: str,
) -> dict[str, tuple[str, ...] | Callable[[], list[str]]]:
    raw = _build_tool_commands(package_name)
    return {k: (tuple(v) if isinstance(v, list) else v) for k, v in raw.items()}


def _materialize_tool_command(
    entry: tuple[str, ...] | Callable[[], list[str]],
) -> list[str]:
    """Resolve a tool command entry into a fresh, mutable argument list.

    ``isinstance(entry, tuple)`` rather than ``callable(entry)``: a
    ``callable()`` test does not narrow the union for a type checker, and
    the tuple/callable split is exactly the distinction that matters here.
    """
    if isinstance(entry, tuple):
        return list(entry)
    return list(entry())


_DEFAULT_CWD_STR = str(Path.cwd())
_DEFAULT_PACKAGE_NAME = _detect_package_name_cached(_DEFAULT_CWD_STR)
_DEFAULT_COMMANDS = _build_tool_commands_cached(_DEFAULT_PACKAGE_NAME)


def get_tool_command(
    hook_name: str,
    pkg_path: Path | None = None,
    *,
    verbose: bool = False,
    settings: HookSettings | None = None,
) -> list[str]:
    if pkg_path is None or pkg_path == _DEFAULT_CWD_STR:
        tool_commands = _DEFAULT_COMMANDS
    else:
        package_name = _detect_package_name_cached(pkg_path)
        tool_commands = _build_tool_commands_cached(package_name)

    if hook_name not in tool_commands:
        msg = f"Unknown hook name: {hook_name}"
        raise KeyError(msg)

    cmd = _materialize_tool_command(tool_commands[hook_name])

    # Stage 2: when settings opt-in, inject --unsafe-fixes right after --fix
    # so the ruff-check command remains safe-by-default.
    if (
        hook_name == "ruff-check"
        and settings is not None
        and settings.ruff_unsafe_fixes
        and "--unsafe-fixes" not in cmd
    ):
        if "--fix" in cmd:
            cmd.insert(cmd.index("--fix") + 1, "--unsafe-fixes")
        else:
            cmd.append("--unsafe-fixes")

    if verbose and hook_name == "ty":
        cmd.append("--verbose")

    # Refurb has no pluggable type checker, so Mypy's own flags are its only
    # speed lever. They are appended after "--" (Refurb forwards everything
    # past that separator to Mypy) and taken from the repository's own
    # [tool.refurb].mypy_args, which Refurb would otherwise discard.
    if hook_name == "refurb":
        cmd.extend(build_refurb_mypy_args(pkg_path))

    return cmd


def list_available_tools() -> list[str]:
    tool_commands = _build_tool_commands_cached("dummy")
    return sorted(tool_commands.keys())


def is_native_tool(hook_name: str) -> bool:
    NATIVE_TOOLS: set[str] = {
        "trailing-whitespace",
        "end-of-file-fixer",
        "check-yaml",
        "check-toml",
        "check-added-large-files",
        "validate-regex-patterns",
    }
    return hook_name in NATIVE_TOOLS
