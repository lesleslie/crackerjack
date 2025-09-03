"""Tests for secure status formatter."""

import tempfile
from pathlib import Path

from crackerjack.services.secure_status_formatter import (
    SecureStatusFormatter,
    StatusVerbosity,
    format_secure_status,
)


class TestSecureStatusFormatter:
    """Test secure status formatter functionality."""

    def test_path_sanitization(self):
        """Test absolute path sanitization to relative paths."""
        formatter = SecureStatusFormatter(project_root=Path("/project"))

        test_data = {
            "project_path": "/project/src/main.py",
            "temp_dir": "/tmp/test-files",
            "user_path": "/Users/username/documents",
            "relative_path": "./existing/relative",
        }

        result = formatter.format_status(test_data, StatusVerbosity.STANDARD)

        # Paths should be sanitized
        assert "project_path" in result
        assert "/project/src/main.py" not in str(result)
        assert "/tmp/test-files" not in str(result)
        assert "/Users/username/documents" not in str(result)

        # Security metadata should be present
        assert result["_security"]["sanitized"] is True
        assert result["_security"]["verbosity"] == "standard"

    def test_url_sanitization(self):
        """Test internal URL sanitization."""
        formatter = SecureStatusFormatter()

        test_data = {
            "websocket_url": "ws://localhost:8675/progress",
            "api_endpoint": "http://127.0.0.1:3000/api/status",
            "external_url": "https://api.example.com/data",
        }

        result = formatter.format_status(test_data, StatusVerbosity.STANDARD)

        # Internal URLs should be masked
        assert "localhost" not in str(result)
        assert "127.0.0.1" not in str(result)
        assert "[INTERNAL_URL]" in str(result)

        # External URLs should remain (in this case, they get processed too)
        # But the main point is localhost/127.0.0.1 are masked

    def test_verbosity_levels(self):
        """Test different verbosity levels."""
        formatter = SecureStatusFormatter()

        test_data = {
            "progress_dir": "/tmp/progress",
            "temp_files_count": 42,
            "project_path": "/project/path",
            "status": "running",
            "message": "All good",
        }

        # Test MINIMAL verbosity - should remove many keys
        minimal = formatter.format_status(test_data, StatusVerbosity.MINIMAL)
        assert "progress_dir" not in minimal
        assert "temp_files_count" not in minimal
        assert "status" in minimal  # Essential operational data

        # Test STANDARD verbosity - should keep more operational data
        standard = formatter.format_status(test_data, StatusVerbosity.STANDARD)
        assert "progress_dir" not in standard  # Still removed
        assert "status" in standard
        assert "message" in standard

        # Test FULL verbosity - should keep everything but still sanitize
        full = formatter.format_status(test_data, StatusVerbosity.FULL)
        assert "progress_dir" in full
        assert "temp_files_count" in full
        assert "status" in full

    def test_sensitive_key_masking(self):
        """Test masking of sensitive configuration values."""
        formatter = SecureStatusFormatter()

        test_data = {
            "api_key": "sk-1234567890abcdef",
            "password": "secret123",
            "token": "jwt-token-here",
            "normal_field": "normal_value",
        }

        result = formatter.format_status(test_data, StatusVerbosity.STANDARD)

        # Sensitive fields should be masked
        assert result["api_key"] != "sk-1234567890abcdef"
        assert "*" in result["api_key"]
        assert result["password"] != "secret123"
        assert "*" in result["password"]
        assert result["token"] != "jwt-token-here"
        assert "*" in result["token"]

        # Normal fields should be unchanged
        assert result["normal_field"] == "normal_value"

    def test_nested_data_sanitization(self):
        """Test sanitization of nested data structures."""
        formatter = SecureStatusFormatter()

        test_data = {
            "server_info": {
                "project_path": "/absolute/path",
                "websocket_url": "ws://localhost:8675",
                "config": {
                    "api_key": "secret-key",
                    "debug": True,
                },
            },
            "jobs": [
                {
                    "id": "job-1",
                    "path": "/tmp/job-1",
                    "url": "http://127.0.0.1:3000/job-1",
                }
            ],
        }

        result = formatter.format_status(test_data, StatusVerbosity.STANDARD)

        # Nested paths and URLs should be sanitized
        result_str = str(result)
        assert "localhost" not in result_str
        assert "127.0.0.1" not in result_str
        assert "/absolute/path" not in result_str
        assert "/tmp/job-1" not in result_str

        # Structure should be preserved
        assert "server_info" in result
        assert "config" in result["server_info"]
        assert "jobs" in result
        assert len(result["jobs"]) == 1

        # Sensitive data should be masked
        assert result["server_info"]["config"]["api_key"] != "secret-key"
        assert "*" in result["server_info"]["config"]["api_key"]

    def test_error_response_formatting(self):
        """Test secure error response formatting."""
        formatter = SecureStatusFormatter()

        # Test with system path in error
        error_with_path = "File not found: /absolute/system/path/file.txt"
        result = formatter.format_error_response(
            error_with_path, StatusVerbosity.STANDARD
        )

        assert result["success"] is False
        assert "error" in result
        assert "/absolute/system/path/file.txt" not in result["error"]
        assert "[REDACTED_PATH]" in result["error"]

        # Test minimal verbosity - should use generic message
        minimal_result = formatter.format_error_response(
            "Connection refused to localhost:8675", StatusVerbosity.MINIMAL
        )

        assert minimal_result["success"] is False
        assert "localhost:8675" not in str(minimal_result)
        assert (
            minimal_result["error"]
            == "Service temporarily unavailable. Please try again later."
        )

    def test_convenience_function(self):
        """Test the convenience function works correctly."""
        test_data = {
            "project_path": "/test/project",
            "status": "running",
        }

        result = format_secure_status(
            test_data,
            verbosity=StatusVerbosity.STANDARD,
            project_root=Path("/test"),
        )

        assert result["_security"]["sanitized"] is True
        assert result["status"] == "running"
        assert "/test/project" not in str(result)

    def test_security_logging_called(self, mocker):
        """Test that security events are logged during sanitization."""
        # Mock the security logger
        mock_logger = mocker.patch(
            "crackerjack.services.secure_status_formatter.get_security_logger"
        )

        formatter = SecureStatusFormatter()
        test_data = {"test": "data"}

        formatter.format_status(test_data, StatusVerbosity.STANDARD, "test_user")

        # Verify logging was called
        mock_logger.return_value.log_status_access_attempt.assert_called_once()
        call_args = mock_logger.return_value.log_status_access_attempt.call_args
        assert call_args[1]["endpoint"] == "status_data"
        assert call_args[1]["verbosity_level"] == "standard"
        assert call_args[1]["user_context"] == "test_user"

    def test_potential_secret_masking(self):
        """Test masking of potential secrets in strings."""
        formatter = SecureStatusFormatter()

        test_data = {
            "long_string": "ThisIsAVeryLongAlphanumericStringThatMightBeAToken123456",
            "short_string": "short",
            "normal_text": "This is normal text with spaces",
        }

        result = formatter.format_status(test_data, StatusVerbosity.MINIMAL)

        # Long alphanumeric strings should be masked in minimal mode
        long_result = result["long_string"]
        assert long_result != test_data["long_string"]
        assert "*" in long_result

        # Short strings should not be masked
        assert result["short_string"] == "short"

        # Normal text should not be masked
        assert result["normal_text"] == "This is normal text with spaces"


class TestStatusVerbosityEnum:
    """Test StatusVerbosity enum values."""

    def test_verbosity_enum_values(self):
        """Test that all verbosity levels exist with correct values."""
        assert StatusVerbosity.MINIMAL.value == "minimal"
        assert StatusVerbosity.STANDARD.value == "standard"
        assert StatusVerbosity.DETAILED.value == "detailed"
        assert StatusVerbosity.FULL.value == "full"


class TestIntegrationWithTempFiles:
    """Test integration with actual temp files and paths."""

    def test_with_real_temp_directory(self):
        """Test with real temporary directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_root = temp_path / "project"
            project_root.mkdir()

            # Create some test files
            test_file = project_root / "test.py"
            test_file.write_text("# test file")

            formatter = SecureStatusFormatter(project_root=project_root)

            test_data = {
                "project_path": str(project_root / "src"),
                "temp_file": str(temp_path / "temp.json"),
                "test_file": str(test_file),
                "external_path": "/completely/different/path",
            }

            result = formatter.format_status(test_data, StatusVerbosity.STANDARD)

            # Paths should be sanitized
            result_str = str(result)
            assert str(temp_path) not in result_str
            assert str(project_root) not in result_str

            # Should contain relative or masked paths
            assert "[REDACTED_PATH]" in result_str or "./test.py" in result_str
