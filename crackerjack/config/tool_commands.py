from __future__ import annotations

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

    for item in pkg_path.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            if item.name not in {"tests", "docs", ".venv", "venv", "build", "dist"}:
                return item.name

    return pkg_path.name.replace("-", "_")


def _build_tool_commands(package_name: str) -> dict[str, list[str]]:
    return {
        "validate-regex-patterns": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.validate_regex_patterns",
        ],
        "skylos": [
            "uv",
            "run",
            "skylos",
            "--exclude-folder",
            "tests",
            f"./{package_name}",
        ],
        "zuban": [
            "uv",
            "run",
            "zuban",
            "mypy",
            "--config-file",
            "mypy.ini",
            "--no-error-summary",
            f"./{package_name}",
        ],
        "trailing-whitespace": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.trailing_whitespace",
        ],
        "end-of-file-fixer": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.end_of_file_fixer",
        ],
        "check-yaml": ["uv", "run", "python", "-m", "crackerjack.tools.check_yaml"],
        "check-toml": ["uv", "run", "python", "-m", "crackerjack.tools.check_toml"],
        "check-json": ["uv", "run", "python", "-m", "crackerjack.tools.check_json"],
        "format-json": ["uv", "run", "python", "-m", "crackerjack.tools.format_json"],
        "check-jsonschema": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.check_jsonschema",
        ],
        "check-ast": ["uv", "run", "python", "-m", "crackerjack.tools.check_ast"],
        "check-added-large-files": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.check_added_large_files",
            "--maxkb",
            "1000",
        ],
        "uv-lock": ["uv", "lock"],
        "gitleaks": [
            "uv",
            "run",
            "gitleaks",
            "protect",
            "-v",
        ],
        "bandit": [
            "uv",
            "run",
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
        ],
        "semgrep": [
            "uvx",
            "--python=3.13",
            "semgrep",
            "scan",
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
        ],
        "codespell": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.codespell_wrapper",
        ],
        "ruff-check": [
            "uv",
            "run",
            "python",
            "-m",
            "ruff",
            "check",
            "--fix",
            f"./{package_name}",
        ],
        "ruff-format": [
            "uv",
            "run",
            "python",
            "-m",
            "ruff",
            "format",
            f"./{package_name}",
        ],
        "mdformat": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.mdformat_wrapper",
        ],
        "check-local-links": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.local_link_checker",
        ],
        "linkcheckmd": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.linkcheckmd_wrapper",
        ],
        "creosote": [
            "uv",
            "run",
            "creosote",
            "-p",
            package_name,
            "--venv",
            ".venv",
        ],
        "complexipy": [
            "uv",
            "run",
            "complexipy",
            "--max-complexity-allowed",
            "15",
            package_name,
        ],
        "refurb": ["uv", "run", "python", "-m", "refurb", package_name],
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
        ],
        "pyscn": [
            "uv",
            "run",
            "pyscn",
            "check",
            "--max-complexity",
            "15",
            "--skip-clones",
            package_name,
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
    if pkg_path is None or str(pkg_path) == _DEFAULT_CWD_STR:
        tool_commands = _DEFAULT_COMMANDS
    else:
        package_name = _detect_package_name_cached(str(pkg_path))
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
