"""
Quick tests to boost coverage toward 42%.
"""

from crackerjack.errors import (
    CrackerjackError,
    ErrorCode,
    FileError,
    format_error_report,
)
from crackerjack.models.task import Task, TaskStatus
from crackerjack.services.security import SecurityService


class TestErrorsQuick:
    """Quick error tests."""

    def test_file_error(self):
        """Test FileError creation."""
        error = FileError(message="File not found", error_code=ErrorCode.FILE_NOT_FOUND)
        assert error.message == "File not found"
        assert error.error_code == ErrorCode.FILE_NOT_FOUND

    def test_format_error_report(self):
        """Test format_error_report function."""
        error = CrackerjackError(
            message="Test error", error_code=ErrorCode.GENERAL_ERROR
        )
        report = format_error_report(error)
        assert "Test error" in report


class TestTaskQuick:
    """Quick task tests."""

    def test_task_creation(self):
        """Test Task creation."""
        task = Task(id="test-task", name="Test Task", status=TaskStatus.PENDING)
        assert task.id == "test-task"
        assert task.status == TaskStatus.PENDING

    def test_task_to_dict(self):
        """Test Task to_dict method."""
        task = Task(id="test-task", name="Test Task", status=TaskStatus.COMPLETED)
        task_dict = task.to_dict()
        assert task_dict["id"] == "test-task"


class TestSecurityQuick:
    """Quick security tests."""

    def test_mask_tokens(self):
        """Test masking tokens."""
        service = SecurityService()
        text = "Using token pypi-abcd1234efgh5678ijkl"
        masked = service.mask_tokens(text)
        assert "pypi-****" in masked

    def test_validate_token_format(self):
        """Test token validation."""
        service = SecurityService()
        assert service.validate_token_format("pypi-abcd1234efgh5678", "pypi") is True
        assert service.validate_token_format("invalid", "pypi") is False
