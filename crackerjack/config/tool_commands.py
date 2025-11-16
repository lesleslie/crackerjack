"""Tool command registry for direct tool invocation.

This module provides mappings from hook names to direct tool commands,
replacing the legacy pre-commit wrapper approach.

Each command is a list of strings that can be passed directly to subprocess.run().
Commands use 'uv run' for Python-based tools to leverage dependency management.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def _detect_package_name_cached(pkg_path_str: str) -> str:
    """Detect the main package name from pyproject.toml or directory structure.

    Args:
        pkg_path: Path to the project root

    Returns:
        The detected package name (defaults to 'crackerjack' if detection fails)
    """
    # Method 1: Try to read from pyproject.toml
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
                    # Convert project name to package name (hyphens to underscores)
                    return project_name.replace("-", "_")

    # Method 2: Look for Python packages in the project root
    for item in pkg_path.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            # Skip common non-package directories
            if item.name not in {"tests", "docs", ".venv", "venv", "build", "dist"}:
                return item.name

    # Method 3: Use the directory name as the package name
    # Convert hyphens to underscores to match Python package naming conventions
    return pkg_path.name.replace("-", "_")


def _build_tool_commands(package_name: str) -> dict[str, list[str]]:
    """Build tool command registry with dynamic package name.

    Args:
        package_name: The name of the package being analyzed

    Returns:
        Dictionary mapping hook names to command lists
    """
    return {
        # ========================================================================
        # CUSTOM TOOLS (crackerjack native)
        # ========================================================================
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
            "check",
            "--config-file",
            "mypy.ini",  # Required: zuban v0.2.2 can't parse [tool.mypy] from pyproject.toml
            "--no-error-summary",  # Suppress summary line (e.g., "Found N errors") to keep issue output clean
            f"./{package_name}",
        ],
        # ========================================================================
        # PRE-COMMIT-HOOKS (native implementations in crackerjack.tools)
        # ========================================================================
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
            "1000",  # 1MB limit for comprehensive frameworks with large lock files
        ],
        # ========================================================================
        # THIRD-PARTY TOOLS (direct invocation)
        # ========================================================================
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
            "-r",  # Recursive scanning
            "--format",
            "json",  # JSON output for structured parsing
            "--severity-level",
            "low",  # Detect all severity levels
            "--confidence-level",
            "low",  # Detect all confidence levels
            "-x",
            "tests",  # Exclude tests directory
            f"./{package_name}",  # Target only the package directory
        ],
        "semgrep": [
            "uvx",  # Use uvx for isolated semgrep environment
            "--python=3.13",  # Explicitly use Python 3.13 for match/case syntax support
            "semgrep",
            "scan",
            "--error",  # Exit with non-zero code when findings detected (CRITICAL security level)
            "--json",  # JSON output for structured parsing
            "--config",
            "p/security-audit",  # Security-focused ruleset (comprehensive)
            "--exclude",
            ".pytest_cache",
            "--exclude",
            ".ruff_cache",
            "--exclude",
            "__pycache__",
            "--exclude",
            "tests",
            f"./{package_name}",  # Target only the package directory
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
            f"./{package_name}",
        ],
        "ruff-format": [
            "uv",
            "run",
            "python",
            "-m",
            "ruff",
            "format",
            "--check",
            f"./{package_name}",
        ],
        # Mdformat in auto-fix mode for fast hooks (no --check)
        "mdformat": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.mdformat_wrapper",
        ],
        # Use explicit project path flag; include venv discovery
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
    }


@lru_cache(maxsize=8)
def _build_tool_commands_cached(package_name: str) -> dict[str, tuple[str, ...]]:
    """Cached variant of tool command map returning immutable tuples.

    Using tuples ensures cached structures aren’t accidentally mutated, while
    get_tool_command converts back to lists for callers.
    """
    raw = _build_tool_commands(package_name)
    return {k: tuple(v) for k, v in raw.items()}


# Precompute defaults for the active working directory to avoid hot-path lookups
_DEFAULT_CWD_STR = str(Path.cwd())
_DEFAULT_PACKAGE_NAME = _detect_package_name_cached(_DEFAULT_CWD_STR)
_DEFAULT_COMMANDS = _build_tool_commands_cached(_DEFAULT_PACKAGE_NAME)


def get_tool_command(hook_name: str, pkg_path: Path | None = None) -> list[str]:
    """Get the direct command for a tool by hook name.

    Args:
        hook_name: The name of the hook (e.g., "ruff-check", "trailing-whitespace")
        pkg_path: Optional path to the project root (for package name detection)

    Returns:
        List of command arguments for subprocess execution

    Raises:
        KeyError: If the hook name is not found in the registry
    """
    # Detect package name from project root
    if pkg_path is None or str(pkg_path) == _DEFAULT_CWD_STR:
        tool_commands = _DEFAULT_COMMANDS
    else:
        package_name = _detect_package_name_cached(str(pkg_path))
        tool_commands = _build_tool_commands_cached(package_name)

    if hook_name not in tool_commands:
        msg = f"Unknown hook name: {hook_name}"
        raise KeyError(msg)

    # Return a fresh list to prevent caller mutation
    return list(tool_commands[hook_name])


def list_available_tools() -> list[str]:
    """Get list of all available tool names.

    Returns:
        Sorted list of hook names that can be executed
    """
    # Build with a dummy package name just to get the keys
    tool_commands = _build_tool_commands_cached("dummy")
    return sorted(tool_commands.keys())


def is_native_tool(hook_name: str) -> bool:
    """Check if a tool is implemented as a native crackerjack tool.

    We classify only the built-in Python implementations as native. Wrappers
    around third-party tools (e.g., codespell) are not considered native.

    Args:
        hook_name: The name of the hook

    Returns:
        True if the tool is natively implemented in crackerjack.tools, else False
    """
    NATIVE_TOOLS: set[str] = {
        # Native Python implementations in crackerjack.tools
        "trailing-whitespace",
        "end-of-file-fixer",
        "check-yaml",
        "check-toml",
        "check-added-large-files",
        # Classified as native per tests and docs
        "validate-regex-patterns",
    }
    return hook_name in NATIVE_TOOLS
