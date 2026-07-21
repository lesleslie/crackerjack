"""Slash command file resolution.

Maps Crackerjack slash command names (e.g. ``"run"``, ``"init"``, ``"status"``)
to the corresponding Markdown source files in the top-level ``commands/``
directory.  The Markdown sources are the canonical content that the MCP
server exposes as prompt templates.

The command files themselves (e.g. ``commands/crackerjack-run.md``) live in
the repository root and are shipped as part of the published distribution
so MCP clients always have the latest prompt text without needing a
separate asset bundle.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["get_slash_command_path", "SLASH_COMMANDS_DIR"]

# ``crackerjack/slash_commands/__init__.py`` lives three levels below the
# repository root: ``<repo>/crackerjack/slash_commands/__init__.py``.
REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent

# Slash-command Markdown sources are kept in ``<repo>/commands/`` so they
# ship alongside the project and are easy for end users to discover.
SLASH_COMMANDS_DIR: Path = REPO_ROOT / "commands"


def get_slash_command_path(name: str) -> Path:
    """Return the path to the Markdown file for ``name``.

    The convention is ``crackerjack-<name>.md`` — the ``crackerjack-`` prefix
    matches the namespace advertised to MCP clients.

    Args:
        name: Slash command name without the leading ``/`` and without the
            ``crackerjack-`` prefix.  For example, ``"run"`` resolves to
            ``commands/crackerjack-run.md``.

    Returns:
        Absolute path to the Markdown source file.  The file may not exist
        yet — callers are expected to handle ``FileNotFoundError`` from
        ``read_text()``.

    Raises:
        ValueError: If ``name`` is empty or contains path separators.
    """
    if not name or "/" in name or "\\" in name or name.startswith("."):
        msg = f"Invalid slash command name: {name!r}"
        raise ValueError(msg)
    return SLASH_COMMANDS_DIR / f"crackerjack-{name}.md"
