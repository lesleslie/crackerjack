from __future__ import annotations

from pathlib import Path

__all__ = ["get_slash_command_path", "SLASH_COMMANDS_DIR"]


REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent


SLASH_COMMANDS_DIR: Path = REPO_ROOT / "commands"


def get_slash_command_path(name: str) -> Path:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        msg = f"Invalid slash command name: {name!r}"
        raise ValueError(msg)
    return SLASH_COMMANDS_DIR / f"crackerjack-{name}.md"
