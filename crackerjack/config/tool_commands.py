from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path


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


_SKYLOS_EXCLUDE_FOLDERS = [
    "tests",
    "docs",
    "scripts",
    "examples",
    "archive",
    "assets",
    "templates",
    "tools",
    "worktrees",
    "settings",
    ".venv",
    "venv",
    "build",
    "dist",
    "htmlcov",
    "logs",
    "node_modules",
]


def _build_skylos_command(package_name: str) -> list[str]:

    venv_skylos = Path.cwd() / ".venv" / "bin" / "skylos"
    if venv_skylos.exists():
        cmd = [str(venv_skylos)]
    else:
        cmd = ["uv", "run", "skylos"]

    for folder in _SKYLOS_EXCLUDE_FOLDERS:
        cmd.extend(["--exclude-folder", folder])

    cmd.extend(["--confidence", "70"])

    cmd.extend(["--limit", "50"])

    diff_base = os.environ.get("PRE_COMMIT_FROM_REF", "HEAD~1")
    cmd.extend(["--diff-base", diff_base])

    cmd.append(f"./{package_name}")

    return cmd


def _python_module_command(module: str, *args: str) -> list[str]:
    return [sys.executable, "-m", module, *args]


def _preferred_binary_command(tool_name: str, *args: str) -> list[str]:
    venv_tool = Path.cwd() / ".venv" / "bin" / tool_name
    if venv_tool.exists():
        return [str(venv_tool), *args]

    resolved = shutil.which(tool_name)
    if resolved:
        return [resolved, *args]

    return [tool_name, *args]


def _build_tool_commands(package_name: str) -> dict[str, list[str]]:
    return {
        "validate-regex-patterns": _python_module_command(
            "crackerjack.tools.validate_regex_patterns"
        ),
        "skylos": _build_skylos_command(package_name),
        "zuban": _preferred_binary_command(
            "zuban",
            "mypy",
            "--config-file",
            "mypy.ini",
            "--no-error-summary",
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
            "crackerjack.tools.check_jsonschema"
        ),
        "check-ast": _python_module_command("crackerjack.tools.check_ast"),
        "check-added-large-files": _python_module_command(
            "crackerjack.tools.check_added_large_files",
            "--maxkb",
            "1000",
            "--suggest-gitignore",
        ),
        "uv-lock": ["uv", "lock"],
        "gitleaks": _preferred_binary_command(
            "gitleaks",
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
        "semgrep": _preferred_binary_command(
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
        "codespell": _python_module_command("crackerjack.tools.codespell_wrapper"),
        "ruff-check": _python_module_command(
            "ruff",
            "check",
            "--output-format",
            "json",
            "--fix",
            "--unsafe-fixes",
            f"./{package_name}",
        ),
        "ruff-format": _python_module_command(
            "ruff",
            "format",
            f"./{package_name}",
        ),
        "mdformat": _python_module_command("crackerjack.tools.mdformat_wrapper"),
        "check-local-links": _python_module_command(
            "crackerjack.tools.local_link_checker"
        ),
        "linkcheckmd": _python_module_command("crackerjack.tools.linkcheckmd_wrapper"),
        "creosote": _preferred_binary_command(
            "creosote",
            "-p",
            package_name,
            "--venv",
            ".venv",
        ),
        "complexipy": _preferred_binary_command(
            "complexipy",
            "--max-complexity-allowed",
            "15",
            "--failed",
            "--quiet",
            "-e",
            "tests",
            "-e",
            "test_*.py",
            package_name,
        ),
        "refurb": _python_module_command("refurb", f"{package_name}/"),
        "pip-audit": [
            "uv",
            "run",
            "pip-audit",
            "--format",
            "json",
            "--desc",
            "--skip-editable",
            "--vulnerability-service",
            "osv",
            "--ignore-vuln",
            "CVE-2025-53000",
            "--ignore-vuln",
            "CVE-2026-0994",
            "--ignore-vuln",
            "CVE-2025-69872",
            "--ignore-vuln",
            "CVE-2025-14009",
            "--fix",
        ],
        "pyscn": _preferred_binary_command(
            "pyscn",
            "check",
            "--max-complexity",
            "15",
            "--skip-clones",
            package_name,
        ),
        "lychee": [
            "lychee",
            "--no-progress",
            "--cache",
            ".cache/lychee",
            "--verbose",
            ".",
        ],
    }


@lru_cache(maxsize=8)
def _build_tool_commands_cached(package_name: str) -> dict[str, tuple[str, ...]]:
    raw = _build_tool_commands(package_name)
    return {k: tuple(v) for k, v in raw.items()}


_DEFAULT_CWD_STR = str(Path.cwd())
_DEFAULT_PACKAGE_NAME = _detect_package_name_cached(_DEFAULT_CWD_STR)
_DEFAULT_COMMANDS = _build_tool_commands_cached(_DEFAULT_PACKAGE_NAME)


def get_tool_command(hook_name: str, pkg_path: Path | None = None) -> list[str]:
    if pkg_path is None or pkg_path == _DEFAULT_CWD_STR:
        tool_commands = _DEFAULT_COMMANDS
    else:
        package_name = _detect_package_name_cached(pkg_path)
        tool_commands = _build_tool_commands_cached(package_name)

    if hook_name not in tool_commands:
        msg = f"Unknown hook name: {hook_name}"
        raise KeyError(msg)

    return list(tool_commands[hook_name])


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
