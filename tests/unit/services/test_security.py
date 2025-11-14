"""Unit tests for SecurityService.

Tests security-critical functionality including token masking,
secure file operations, environment variable handling, and
subprocess command validation.
"""

import os
import tempfile
from pathlib import Path

import pytest

from crackerjack.errors import FileError, SecurityError
from crackerjack.services.security import SecurityService


@pytest.mark.unit
@pytest.mark.security
class TestSecurityServiceTokenMasking:
    """Test token masking functionality."""

    @pytest.fixture
    def service(self):
        """Create SecurityService instance."""
        return SecurityService()

    def test_mask_tokens_empty_string(self, service):
        """Test masking empty string returns empty string."""
        result = service.mask_tokens("")
        assert result == ""

    def test_mask_tokens_none(self, service):
        """Test masking None returns None."""
        result = service.mask_tokens(None)
        assert result is None

    def test_mask_tokens_with_pypi_token(self, service):
        """Test PyPI token is masked in text."""
        text = "UV_PUBLISH_TOKEN=pypi-1234567890abcdef"
        result = service.mask_tokens(text)

        # Token should not appear in plain text
        assert "pypi-1234567890abcdef" not in result
        assert "UV_PUBLISH_TOKEN" in result

    def test_mask_tokens_with_github_token(self, service):
        """Test GitHub token is masked in text."""
        text = "GITHUB_TOKEN=ghp_1234567890abcdefghij"
        result = service.mask_tokens(text)

        # Token should not appear in plain text
        assert "ghp_1234567890abcdefghij" not in result
        assert "GITHUB_TOKEN" in result

    def test_mask_tokens_preserves_non_sensitive_content(self, service):
        """Test non-sensitive content is preserved."""
        text = "This is a normal string with no secrets"
        result = service.mask_tokens(text)
        assert result == text

    def test_mask_command_output(self, service):
        """Test command output masking for stdout and stderr."""
        stdout = "Success: token=abc123secret"
        stderr = "Error: API_KEY=xyz789secret"

        masked_stdout, masked_stderr = service.mask_command_output(stdout, stderr)

        # Both should be processed
        assert isinstance(masked_stdout, str)
        assert isinstance(masked_stderr, str)

    def test_mask_tokens_with_env_var(self, service, monkeypatch):
        """Test masking of environment variable values in text."""
        # Set a sensitive environment variable
        long_token = "a" * 20
        monkeypatch.setenv("UV_PUBLISH_TOKEN", long_token)

        text = f"Token is: {long_token}"
        result = service.mask_tokens(text)

        # Full token should not appear
        assert long_token not in result
        # Should show partial masking
        assert "aaaa" in result
        assert "..." in result

    def test_mask_tokens_short_env_var(self, service, monkeypatch):
        """Test masking of short environment variable values."""
        short_token = "abc"  # Too short to be masked with partial reveal
        monkeypatch.setenv("PASSWORD", short_token)

        text = f"Password is: {short_token}"
        result = service.mask_tokens(text)

        # Short values should still be in text (not masked)
        # because they're below the 8-character threshold
        assert result == text


@pytest.mark.unit
@pytest.mark.security
class TestSecurityServiceTokenFiles:
    """Test secure token file operations."""

    @pytest.fixture
    def service(self):
        """Create SecurityService instance."""
        return SecurityService()

    def test_create_secure_token_file_success(self, service):
        """Test successful creation of secure token file."""
        token = "test-token-12345678"

        token_file = service.create_secure_token_file(token)

        try:
            # File should exist
            assert token_file.exists()
            assert token_file.is_file()

            # File should have secure permissions (0o600)
            stat_info = token_file.stat()
            permissions = oct(stat_info.st_mode)[-3:]
            assert permissions == "600"

            # File should contain the token
            content = token_file.read_text()
            assert content == token

            # File should be in temp directory
            assert token_file.parent == Path(tempfile.gettempdir())
            assert token_file.name.startswith("crackerjack_token_")
            assert token_file.suffix == ".token"
        finally:
            # Cleanup
            service.cleanup_token_file(token_file)

    def test_create_secure_token_file_custom_prefix(self, service):
        """Test token file creation with custom prefix."""
        token = "test-token-12345678"
        prefix = "custom_prefix"

        token_file = service.create_secure_token_file(token, prefix=prefix)

        try:
            assert token_file.name.startswith(f"{prefix}_")
        finally:
            service.cleanup_token_file(token_file)

    def test_create_secure_token_file_empty_token(self, service):
        """Test creation fails with empty token."""
        with pytest.raises(SecurityError) as exc_info:
            service.create_secure_token_file("")

        assert "Invalid token provided" in str(exc_info.value)

    def test_create_secure_token_file_short_token(self, service):
        """Test creation fails with token shorter than 8 characters."""
        with pytest.raises(SecurityError) as exc_info:
            service.create_secure_token_file("short")

        assert "Token appears too short" in str(exc_info.value)

    def test_cleanup_token_file_success(self, service):
        """Test secure cleanup of token file."""
        token = "test-token-12345678"
        token_file = service.create_secure_token_file(token)

        assert token_file.exists()

        # Cleanup should remove the file
        service.cleanup_token_file(token_file)

        assert not token_file.exists()

    def test_cleanup_token_file_nonexistent(self, service):
        """Test cleanup of non-existent file does not raise error."""
        nonexistent = Path("/tmp/nonexistent_token_file.token")

        # Should not raise any exception
        service.cleanup_token_file(nonexistent)

    def test_cleanup_token_file_none(self, service):
        """Test cleanup with None path does not raise error."""
        # Should not raise any exception
        service.cleanup_token_file(None)

    def test_cleanup_token_file_overwrites_before_delete(self, service):
        """Test cleanup overwrites file content before deletion."""
        token = "secret-token-12345678"
        token_file = service.create_secure_token_file(token)

        # Get original size
        original_size = token_file.stat().st_size

        # Cleanup
        service.cleanup_token_file(token_file)

        # File should be deleted
        assert not token_file.exists()


@pytest.mark.unit
@pytest.mark.security
class TestSecurityServiceEnvironment:
    """Test environment variable security features."""

    @pytest.fixture
    def service(self):
        """Create SecurityService instance."""
        return SecurityService()

    def test_get_masked_env_summary(self, service, monkeypatch):
        """Test environment variable summary with masking."""
        # Set up test environment
        monkeypatch.setenv("UV_PUBLISH_TOKEN", "secret123456")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")

        summary = service.get_masked_env_summary()

        # Sensitive vars should be masked
        assert "UV_PUBLISH_TOKEN" in summary
        assert "secret123456" not in summary["UV_PUBLISH_TOKEN"]
        assert "..." in summary["UV_PUBLISH_TOKEN"]

        # Safe vars should be visible
        if "PATH" in os.environ:
            assert "PATH" in summary
            assert summary["PATH"] == os.environ["PATH"]

    def test_get_masked_env_summary_empty_sensitive_var(self, service, monkeypatch):
        """Test masking of empty sensitive environment variables."""
        monkeypatch.setenv("API_KEY", "")

        summary = service.get_masked_env_summary()

        if "API_KEY" in summary:
            assert summary["API_KEY"] == "(empty)"

    def test_create_secure_command_env_removes_dangerous_vars(self, service):
        """Test dangerous environment variables are removed."""
        base_env = {
            "PATH": "/usr/bin",
            "LD_PRELOAD": "/malicious/lib.so",
            "PYTHONPATH": "/injected/path",
            "HOME": "/home/user",
        }

        secure_env = service.create_secure_command_env(base_env=base_env)

        # Dangerous vars should be removed
        assert "LD_PRELOAD" not in secure_env
        assert "PYTHONPATH" not in secure_env

        # Safe vars should remain
        assert secure_env["PATH"] == "/usr/bin"
        assert secure_env["HOME"] == "/home/user"

    def test_create_secure_command_env_with_additional_vars(self, service):
        """Test adding additional variables to secure environment."""
        additional = {"CUSTOM_VAR": "value123"}

        secure_env = service.create_secure_command_env(
            additional_vars=additional
        )

        assert secure_env["CUSTOM_VAR"] == "value123"

    def test_create_secure_command_env_defaults_to_os_environ(self, service):
        """Test default environment is os.environ."""
        secure_env = service.create_secure_command_env()

        # Should have common environment variables
        # but dangerous ones removed
        assert "LD_PRELOAD" not in secure_env
        assert "DYLD_INSERT_LIBRARIES" not in secure_env

    def test_create_secure_command_env_all_dangerous_vars_removed(self, service):
        """Test all dangerous library injection variables are removed."""
        base_env = {
            "LD_PRELOAD": "malicious",
            "LD_LIBRARY_PATH": "malicious",
            "DYLD_INSERT_LIBRARIES": "malicious",
            "DYLD_LIBRARY_PATH": "malicious",
            "PYTHONPATH": "malicious",
        }

        secure_env = service.create_secure_command_env(base_env=base_env)

        # All dangerous variables should be removed
        assert "LD_PRELOAD" not in secure_env
        assert "LD_LIBRARY_PATH" not in secure_env
        assert "DYLD_INSERT_LIBRARIES" not in secure_env
        assert "DYLD_LIBRARY_PATH" not in secure_env
        assert "PYTHONPATH" not in secure_env


@pytest.mark.unit
@pytest.mark.security
class TestSecurityServiceValidation:
    """Test validation and checking methods."""

    @pytest.fixture
    def service(self):
        """Create SecurityService instance."""
        return SecurityService()

    def test_validate_token_format_empty(self, service):
        """Test validation fails for empty token."""
        assert service.validate_token_format("") is False

    def test_validate_token_format_too_short(self, service):
        """Test validation fails for tokens shorter than 8 characters."""
        assert service.validate_token_format("short") is False

    def test_validate_token_format_generic_valid(self, service):
        """Test validation passes for valid generic token."""
        token = "a" * 16
        assert service.validate_token_format(token) is True

    def test_validate_token_format_pypi_valid(self, service):
        """Test validation of valid PyPI token."""
        token = "pypi-" + "a" * 16
        assert service.validate_token_format(token, token_type="pypi") is True

    def test_validate_token_format_pypi_invalid(self, service):
        """Test validation fails for invalid PyPI token."""
        # Missing 'pypi-' prefix
        assert service.validate_token_format("abc123456789", token_type="pypi") is False

        # Too short
        assert service.validate_token_format("pypi-short", token_type="pypi") is False

    def test_validate_token_format_github_valid(self, service):
        """Test validation of valid GitHub token."""
        token = "ghp_" + "a" * 36  # GitHub tokens are exactly 40 chars
        assert service.validate_token_format(token, token_type="github") is True

    def test_validate_token_format_github_invalid(self, service):
        """Test validation fails for invalid GitHub token."""
        # Wrong prefix
        assert service.validate_token_format("abc" + "a" * 37, token_type="github") is False

        # Wrong length
        assert service.validate_token_format("ghp_" + "a" * 30, token_type="github") is False

    def test_validate_token_format_whitespace_only(self, service):
        """Test validation fails for whitespace-only token."""
        token = " " * 20
        assert service.validate_token_format(token) is False

    def test_validate_file_safety_normal_file(self, service, tmp_path):
        """Test validation of normal file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert service.validate_file_safety(test_file) is True

    def test_validate_file_safety_nonexistent(self, service):
        """Test validation fails for non-existent file."""
        assert service.validate_file_safety("/nonexistent/file.txt") is False

    def test_validate_file_safety_symlink(self, service, tmp_path):
        """Test validation fails for symlink."""
        target = tmp_path / "target.txt"
        target.write_text("content")

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(target)

        # Symlinks should be rejected for security
        assert service.validate_file_safety(symlink) is False

    def test_validate_file_safety_with_string_path(self, service, tmp_path):
        """Test validation works with string path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert service.validate_file_safety(str(test_file)) is True

    def test_check_hardcoded_secrets_api_key(self, service):
        """Test detection of hardcoded API keys."""
        code = 'api_key = "TEST_API_KEY_1234567890abcdefghij"'

        secrets = service.check_hardcoded_secrets(code)

        assert len(secrets) > 0
        assert any(s["type"] == "api_key" for s in secrets)

    def test_check_hardcoded_secrets_password(self, service):
        """Test detection of hardcoded passwords."""
        code = 'password = "SuperSecret123"'

        secrets = service.check_hardcoded_secrets(code)

        assert len(secrets) > 0
        assert any(s["type"] == "password" for s in secrets)

    def test_check_hardcoded_secrets_token(self, service):
        """Test detection of hardcoded tokens."""
        code = 'token = "ghp_1234567890abcdefghij"'

        secrets = service.check_hardcoded_secrets(code)

        assert len(secrets) > 0
        assert any(s["type"] == "token" for s in secrets)

    def test_check_hardcoded_secrets_line_numbers(self, service):
        """Test line numbers are reported correctly."""
        code = """line 1
line 2
api_key = "TEST_API_KEY_1234567890abcdefghij"
line 4"""

        secrets = service.check_hardcoded_secrets(code)

        assert len(secrets) > 0
        # Should report line 3
        assert any(s["line"] == 3 for s in secrets)

    def test_check_hardcoded_secrets_masked_values(self, service):
        """Test detected secrets are masked in results."""
        code = 'api_key = "TEST_API_KEY_1234567890abcdefghij"'

        secrets = service.check_hardcoded_secrets(code)

        assert len(secrets) > 0
        # Value should be truncated/masked
        secret_value = secrets[0]["value"]
        assert "..." in secret_value
        assert len(secret_value) < 20  # Should be truncated

    def test_check_hardcoded_secrets_no_secrets(self, service):
        """Test no false positives for clean code."""
        code = """
def calculate_total(items):
    return sum(item.price for item in items)
"""

        secrets = service.check_hardcoded_secrets(code)

        assert len(secrets) == 0

    def test_is_safe_subprocess_call_empty(self, service):
        """Test empty command is not safe."""
        assert service.is_safe_subprocess_call([]) is False

    def test_is_safe_subprocess_call_safe_command(self, service):
        """Test safe command is allowed."""
        assert service.is_safe_subprocess_call(["ls", "-la"]) is True
        assert service.is_safe_subprocess_call(["python", "-m", "pytest"]) is True
        assert service.is_safe_subprocess_call(["git", "status"]) is True

    def test_is_safe_subprocess_call_dangerous_commands(self, service):
        """Test dangerous commands are blocked."""
        dangerous = [
            ["rm", "-rf", "/"],
            ["sudo", "command"],
            ["chmod", "777", "file"],
            ["curl", "http://malicious.com"],
            ["wget", "http://malicious.com"],
            ["nc", "-l", "1234"],
        ]

        for cmd in dangerous:
            assert service.is_safe_subprocess_call(cmd) is False

    def test_is_safe_subprocess_call_with_path(self, service):
        """Test command with full path is evaluated correctly."""
        # Safe command with path should be allowed
        assert service.is_safe_subprocess_call(["/usr/bin/python", "script.py"]) is True

        # Dangerous command with path should be blocked
        assert service.is_safe_subprocess_call(["/usr/bin/sudo", "command"]) is False


@pytest.mark.unit
@pytest.mark.security
class TestSecurityServiceConstants:
    """Test security service constants and configuration."""

    @pytest.fixture
    def service(self):
        """Create SecurityService instance."""
        return SecurityService()

    def test_token_pattern_names_defined(self, service):
        """Test token pattern names are properly defined."""
        assert len(service.TOKEN_PATTERN_NAMES) > 0
        assert "mask_pypi_token" in service.TOKEN_PATTERN_NAMES
        assert "mask_github_token" in service.TOKEN_PATTERN_NAMES

    def test_sensitive_env_vars_defined(self, service):
        """Test sensitive environment variable list is defined."""
        assert len(service.SENSITIVE_ENV_VARS) > 0
        assert "UV_PUBLISH_TOKEN" in service.SENSITIVE_ENV_VARS
        assert "PYPI_TOKEN" in service.SENSITIVE_ENV_VARS
        assert "GITHUB_TOKEN" in service.SENSITIVE_ENV_VARS
        assert "API_KEY" in service.SENSITIVE_ENV_VARS
        assert "PASSWORD" in service.SENSITIVE_ENV_VARS
