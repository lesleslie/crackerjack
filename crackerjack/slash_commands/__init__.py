from pathlib import Path

SLASH_COMMANDS_DIR = Path(__file__).parent


def get_slash_command_path(command_name: str) -> Path:
    return SLASH_COMMANDS_DIR / f"{command_name}.md"


def list_available_commands() -> list[str]:
    return [f.stem for f in SLASH_COMMANDS_DIR.glob("*.md")]


__all__ = ["SLASH_COMMANDS_DIR", "get_slash_command_path", "list_available_commands"]
