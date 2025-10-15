import os
import tempfile
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.errors import FileError, SecurityError
from crackerjack.models.protocols import SecurityServiceProtocol
from crackerjack.services.regex_patterns import SAFE_PATTERNS


class SecurityService(SecurityServiceProtocol):
    TOKEN_PATTERN_NAMES = [
        "mask_pypi_token",
        "mask_github_token",
        "mask_generic_long_token",
        "mask_token_assignment",
        "mask_password_assignment",
    ]

    SENSITIVE_ENV_VARS = {
        "UV_PUBLISH_TOKEN",
        "PYPI_TOKEN",
        "GITHUB_TOKEN",
        "AUTH_TOKEN",
        "API_KEY",
        "SECRET_KEY",
        "PASSWORD",
    }

    def mask_tokens(self, text: str) -> str:
        if not text:
            return text

        masked_text = text

        for pattern_name in self.TOKEN_PATTERN_NAMES:
            if pattern_name in SAFE_PATTERNS:
                pattern = SAFE_PATTERNS[pattern_name]
                masked_text = pattern.apply(masked_text)

        for env_var in self.SENSITIVE_ENV_VARS:
            value = os.getenv(env_var)
            if value and len(value) > 8:
                masked_value = (
                    f"{value[:4]}...{value[-4:]}" if len(value) > 12 else "****"
                )
                masked_text = masked_text.replace(value, masked_value)

        return masked_text

    def mask_command_output(self, stdout: str, stderr: str) -> tuple[str, str]:
        return self.mask_tokens(stdout), self.mask_tokens(stderr)

    def create_secure_token_file(
        self,
        token: str,
        prefix: str = "crackerjack_token",
    ) -> Path:
        if not token:
            raise SecurityError(
                message="Invalid token provided",
                details="Token must be a non-empty string",
                recovery="Provide a valid authentication token",
            )
        if len(token) < 8:
            raise SecurityError(
                message="Token appears too short to be valid",
                details=f"Token length: {len(token)} characters",
                recovery="Ensure you're using a full authentication token",
            )
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=f"{prefix}_",
                suffix=".token",
                text=True,
            )
            temp_file = Path(temp_path)
            try:
                temp_file.chmod(0o600)
            except OSError as e:
                with suppress(OSError):
                    temp_file.unlink()
                raise FileError(
                    message="Failed to set[t.Any] secure file permissions",
                    details=str(e),
                    recovery="Check file system permissions and try again",
                ) from e
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(token)
            except OSError as e:
                with suppress(OSError):
                    temp_file.unlink()
                raise FileError(
                    message="Failed to write token to secure file",
                    details=str(e),
                    recovery="Check disk space and file system integrity",
                ) from e

            return temp_file
        except OSError as e:
            raise FileError(
                message="Failed to create secure token file",
                details=str(e),
                recovery="Check temporary directory permissions and disk space",
            ) from e

    def cleanup_token_file(self, token_file: Path) -> None:
        if not token_file or not token_file.exists():
            return
        with suppress(OSError):
            if token_file.is_file():
                with token_file.open("w") as f:
                    f.write("0" * max(1024, token_file.stat().st_size))
                    f.flush()
                    os.fsync(f.fileno())
            token_file.unlink()

    def get_masked_env_summary(self) -> dict[str, str]:
        env_summary = {}
        for key, value in os.environ.items():
            if any(sensitive in key.upper() for sensitive in self.SENSITIVE_ENV_VARS):
                if value:
                    env_summary[key] = (
                        "* ** *" if len(value) <= 8 else f"{value[:2]}...{value[-2:]}"
                    )
                else:
                    env_summary[key] = "(empty)"
            elif key.startswith(("PATH", "HOME", "USER", "SHELL", "TERM")):
                env_summary[key] = value

        return env_summary

    def validate_token_format(self, token: str, token_type: str | None = None) -> bool:
        if not token:
            return False
        if len(token) < 8:
            return False

        if token_type and token_type.lower() == "pypi":
            return token.startswith("pypi-") and len(token) >= 16

        if token_type and token_type.lower() == "github":
            return token.startswith("ghp_") and len(token) == 40

        return len(token) >= 16 and not token.isspace()

    def create_secure_command_env(
        self,
        base_env: dict[str, str] | None = None,
        additional_vars: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if base_env is None:
            base_env = os.environ.copy()

        secure_env = base_env.copy()

        if additional_vars:
            secure_env.update(additional_vars)

        dangerous_vars = [
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "PYTHONPATH",
        ]

        for var in dangerous_vars:
            secure_env.pop(var, None)

        return secure_env

    def validate_file_safety(self, path: str | Path) -> bool:
        try:
            file_path = Path(path)

            if not file_path.exists():
                return False

            if file_path.is_symlink():
                return False
            return True
        except Exception:
            return False

    def check_hardcoded_secrets(self, content: str) -> list[dict[str, t.Any]]:
        secrets = []

        patterns = {
            "api_key": r'api[_-]?key["\s]*[: =]["\s]*([a-zA-Z0-9_-]{20, })',
            "password": r'password["\s]*[: =]["\s]*([^\s"]{8, })',
            "token": r'token["\s]*[: =]["\s]*([a-zA-Z0-9_-]{20, })',
        }

        import re

        for secret_type, pattern in patterns.items():
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                secrets.append(
                    {
                        "type": secret_type,
                        "value": match.group(1)[:10] + "...",
                        "line": content[: match.start()].count("\n") + 1,
                    }
                )
        return secrets

    def is_safe_subprocess_call(self, cmd: list[str]) -> bool:
        if not cmd:
            return False

        dangerous_commands = {
            "rm",
            "rmdir",
            "del",
            "format",
            "fdisk",
            "sudo",
            "su",
            "chmod",
            "chown",
            "curl",
            "wget",
            "nc",
            "netcat",
        }

        command = cmd[0].split("/")[-1]
        return command not in dangerous_commands
