from pathlib import Path

from ..errors import ErrorCode, ExecutionError
from ..services.input_validator import validate_and_sanitize_string

SLASH_COMMANDS_DIR = Path(__file__).parent


def get_slash_command_path(command_name: str) -> Path:
    try:
        sanitized_name = validate_and_sanitize_string(
            command_name, max_length=50, strict_alphanumeric=True
        )

        command_path = SLASH_COMMANDS_DIR / f"{sanitized_name}.md"

        if not str(command_path.resolve()).startswith(
            str(SLASH_COMMANDS_DIR.resolve())
        ):
            raise ExecutionError(
                message=f"Command path outside allowed directory: {command_name}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        return command_path

    except Exception as e:
        if isinstance(e, ExecutionError):
            raise
        raise ExecutionError(
            message=f"Invalid command name: {command_name}",
            error_code=ErrorCode.VALIDATION_ERROR,
        ) from e


def list_available_commands() -> list[str]:
    try:
        commands = []
        for file_path in SLASH_COMMANDS_DIR.glob("*.md"):
            command_name = file_path.stem

            try:
                validate_and_sanitize_string(
                    command_name, max_length=50, strict_alphanumeric=True
                )
                commands.append(command_name)
            except ExecutionError:
                continue

        return sorted(commands)

    except Exception as e:
        raise ExecutionError(
            message="Failed to list[t.Any] available commands",
            error_code=ErrorCode.FILE_READ_ERROR,
        ) from e


__all__ = ["SLASH_COMMANDS_DIR", "get_slash_command_path", "list_available_commands"]
