"""Tool command registry for direct tool invocation.

This module provides mappings from hook names to direct tool commands,
replacing the legacy pre-commit wrapper approach.

Each command is a list of strings that can be passed directly to subprocess.run().
Commands use 'uv run' for Python-based tools to leverage dependency management.
"""

from __future__ import annotations

from pathlib import Path


def _detect_package_name(pkg_path: Path) -> str:
    """Detect the main package name from pyproject.toml or directory structure.

    Args:
        pkg_path: Path to the project root

    Returns:
        The detected package name (defaults to 'crackerjack' if detection fails)
    """
    # Method 1: Try to read from pyproject.toml
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

    # Fallback: use 'crackerjack' for backward compatibility
    return "crackerjack"


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
            ".",
        ],  # Use current CLI: `uv run skylos --exclude-folder tests .`
        "zuban": [
            "uv",
            "run",
            "zuban",
            "check",
            "--config-file",
            "mypy.ini",
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
            "python",
            "-m",
            "bandit",
            "-c",
            "pyproject.toml",
            "-r",
            package_name,
        ],
        "codespell": [
            "uv",
            "run",
            "python",
            "-m",
            "crackerjack.tools.codespell_wrapper",
        ],
        "ruff-check": ["uv", "run", "python", "-m", "ruff", "check", "."],
        "ruff-format": ["uv", "run", "python", "-m", "ruff", "format", "."],
        "mdformat": ["uv", "run", "python", "-m", "mdformat", "--check", "."],
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
    if pkg_path is None:
        pkg_path = Path.cwd()
    package_name = _detect_package_name(pkg_path)

    # Build tool commands with detected package name
    tool_commands = _build_tool_commands(package_name)

    if hook_name not in tool_commands:
        msg = f"Unknown hook name: {hook_name}"
        raise KeyError(msg)

    return tool_commands[hook_name].copy()  # Return copy to prevent mutation


def list_available_tools() -> list[str]:
    """Get list of all available tool names.

    Returns:
        Sorted list of hook names that can be executed
    """
    # Build with a dummy package name just to get the keys
    tool_commands = _build_tool_commands("dummy")
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
