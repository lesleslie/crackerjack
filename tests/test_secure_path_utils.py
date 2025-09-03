import tempfile
from pathlib import Path

import pytest

from crackerjack.errors import ExecutionError
from crackerjack.services.secure_path_utils import (
    AtomicFileOperations,
    SecurePathValidator,
)


class TestSecurePathValidator:
    """Test secure path validation functionality."""

    def test_validate_safe_path_basic(self):
        """Test basic path validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.txt"
            test_file.write_text("test content")

            # Valid path should work
            validated = SecurePathValidator.validate_safe_path(test_file)
            assert validated.exists()
            assert validated.is_absolute()

    def test_validate_safe_path_traversal_attack(self):
        """Test that path traversal attacks are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir)

            # Directory traversal should be blocked
            with pytest.raises(
                ExecutionError, match="Directory traversal pattern detected"
            ):
                SecurePathValidator.validate_safe_path("../../../etc/passwd")

    def test_validate_safe_path_null_byte_attack(self):
        """Test that null byte attacks are blocked."""
        with pytest.raises(ExecutionError, match="Null byte pattern detected"):
            SecurePathValidator.validate_safe_path("/test/file%00.txt")

    def test_validate_safe_path_encoded_traversal(self):
        """Test that URL encoded traversal attacks are blocked."""
        with pytest.raises(
            ExecutionError, match="Directory traversal pattern detected"
        ):
            SecurePathValidator.validate_safe_path(
                "/test/%2e%2e%2f%2e%2e%2f/etc/passwd"
            )

    def test_is_within_directory(self):
        """Test directory containment validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "subdir" / "test.txt"
            test_file.parent.mkdir()
            test_file.write_text("test")

            # Should be within directory
            assert SecurePathValidator.is_within_directory(test_file, temp_path)

            # Should not be within unrelated directory
            with tempfile.TemporaryDirectory() as other_dir:
                other_path = Path(other_dir)
                assert not SecurePathValidator.is_within_directory(
                    test_file, other_path
                )

    def test_secure_path_join(self):
        """Test secure path joining."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Valid join should work
            result = SecurePathValidator.secure_path_join(
                temp_path, "subdir", "file.txt"
            )
            expected = temp_path / "subdir" / "file.txt"

            # Use resolved paths for comparison to handle macOS /private prefix
            assert result.resolve() == expected.resolve()

            # Directory traversal in join should be blocked
            with pytest.raises(
                ExecutionError, match="Directory traversal pattern detected"
            ):
                SecurePathValidator.secure_path_join(
                    temp_path, "../outside", "file.txt"
                )

    def test_dangerous_components_detection(self):
        """Test detection of dangerous path components."""
        with pytest.raises(ExecutionError, match="Dangerous path component detected"):
            SecurePathValidator.validate_safe_path("/test/CON/file.txt")

        with pytest.raises(ExecutionError, match="Dangerous path component detected"):
            SecurePathValidator.validate_safe_path("/test/NUL/file.txt")

    def test_create_secure_temp_file(self):
        """Test secure temporary file creation."""
        temp_file = SecurePathValidator.create_secure_temp_file(
            suffix=".test", prefix="secure_test_", purpose="unit_testing"
        )

        try:
            assert temp_file.name.endswith(".test")
            assert "secure_test_" in temp_file.name

            # Verify file permissions (owner read/write only)
            import os
            import stat

            file_mode = os.stat(temp_file.name).st_mode
            assert stat.S_IMODE(file_mode) == 0o600

        finally:
            temp_file.close()
            Path(temp_file.name).unlink(missing_ok=True)


class TestAtomicFileOperations:
    """Test atomic file operations with security."""

    def test_atomic_write(self):
        """Test atomic file writing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "atomic_test.txt"
            test_content = "This is a test of atomic writing"

            # Atomic write should succeed
            AtomicFileOperations.atomic_write(test_file, test_content, temp_path)

            # File should exist with correct content
            assert test_file.exists()
            assert test_file.read_text() == test_content

    def test_atomic_backup_and_write(self):
        """Test atomic backup and write operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "backup_test.txt"
            original_content = "Original content"
            new_content = "New content"

            # Create original file
            test_file.write_text(original_content)

            # Backup and write new content
            backup_path = AtomicFileOperations.atomic_backup_and_write(
                test_file, new_content, temp_path
            )

            # Original file should have new content
            assert test_file.read_text() == new_content

            # Backup should have original content
            assert backup_path.exists()
            assert backup_path.read_text() == original_content

    def test_atomic_operations_path_validation(self):
        """Test that atomic operations validate paths securely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Directory traversal should be blocked
            with pytest.raises(ExecutionError):
                AtomicFileOperations.atomic_write(
                    "../../../etc/passwd", "malicious content", temp_path
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
