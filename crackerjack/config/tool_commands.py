"""Tool command registry for direct tool invocation.

This module provides mappings from hook names to direct tool commands,
replacing the legacy pre-commit wrapper approach.

Each command is a list of strings that can be passed directly to subprocess.run().
Commands use 'uv run' for Python-based tools to leverage dependency management.
"""

from __future__ import annotations

# Tool command registry mapping hook names to direct commands
TOOL_COMMANDS: dict[str, list[str]] = {
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
        "check",
        "crackerjack",
        "--exclude",
        "tests",
    ],  # Phase 10.4.2: Harmonized with .pre-commit-config.yaml
    "zuban": [
        "uv",
        "run",
        "zuban",
        "check",
        "--config-file",
        "mypy.ini",
        "./crackerjack",
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
    ],
    # ========================================================================
    # THIRD-PARTY TOOLS (direct invocation)
    # ========================================================================
    "uv-lock": ["uv", "lock"],
    "gitleaks": ["uv", "run", "gitleaks", "detect", "--no-git", "-v"],
    "bandit": [
        "uv",
        "run",
        "bandit",
        "-c",
        "pyproject.toml",
        "-r",
        "crackerjack",
    ],
    "codespell": ["uv", "run", "codespell"],
    "ruff-check": ["uv", "run", "ruff", "check", "."],
    "ruff-format": ["uv", "run", "ruff", "format", "."],
    "mdformat": ["uv", "run", "mdformat", "--check", "."],
    "creosote": ["uv", "run", "creosote", "--venv", ".venv"],
    "complexipy": [
        "uv",
        "run",
        "complexipy",
        "crackerjack",
        "--max-complexity",
        "15",
    ],
    "refurb": ["uv", "run", "refurb", "crackerjack"],
}


def get_tool_command(hook_name: str) -> list[str]:
    """Get the direct command for a tool by hook name.

    Args:
        hook_name: The name of the hook (e.g., "ruff-check", "trailing-whitespace")

    Returns:
        List of command arguments for subprocess execution

    Raises:
        KeyError: If the hook name is not found in the registry
    """
    if hook_name not in TOOL_COMMANDS:
        msg = f"Unknown hook name: {hook_name}"
        raise KeyError(msg)

    return TOOL_COMMANDS[hook_name].copy()  # Return copy to prevent mutation


def list_available_tools() -> list[str]:
    """Get list of all available tool names.

    Returns:
        Sorted list of hook names that can be executed
    """
    return sorted(TOOL_COMMANDS.keys())


def is_native_tool(hook_name: str) -> bool:
    """Check if a tool is implemented as a native crackerjack tool.

    Native tools are Python modules in crackerjack.tools package.

    Args:
        hook_name: The name of the hook

    Returns:
        True if the tool is native (in crackerjack.tools), False otherwise
    """
    if hook_name not in TOOL_COMMANDS:
        return False

    command = TOOL_COMMANDS[hook_name]
    return "crackerjack.tools." in " ".join(command)
