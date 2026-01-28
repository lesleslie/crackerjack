import asyncio
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
from crackerjack.adapters._tool_adapter_base import (
    ToolIssue,
    ToolExecutionResult,
    ToolAdapterSettings,
    BaseToolAdapter
)
from crackerjack.models.qa_results import QAResultStatus


def test_tool_issue_dataclass():
    """Test the ToolIssue dataclass."""
    issue = ToolIssue(
        file_path=Path("test.py"),
        line_number=10,
        column_number=5,
        message="Test issue",
        code="E001",
        severity="error",
        suggestion="Fix the issue"
    )

    assert issue.file_path == Path("test.py")
    assert issue.line_number == 10
    assert issue.column_number == 5
    assert issue.message == "Test issue"
    assert issue.code == "E001"
    assert issue.severity == "error"
    assert issue.suggestion == "Fix the issue"

    # Test to_dict method
    issue_dict = issue.to_dict()
    assert issue_dict["file_path"] == "test.py"
    assert issue_dict["line_number"] == 10
    assert issue_dict["column_number"] == 5
    assert issue_dict["message"] == "Test issue"
    assert issue_dict["code"] == "E001"
    assert issue_dict["severity"] == "error"
    assert issue_dict["suggestion"] == "Fix the issue"


def test_tool_execution_result_dataclass():
    """Test the ToolExecutionResult dataclass."""
    result = ToolExecutionResult(
        success=True,
        issues=[],
        error_message=None,
        raw_output="output",
        raw_stderr="stderr",
        execution_time_ms=100.0,
        exit_code=0,
        tool_version="1.0.0"
    )

    assert result.success is True
    assert result.issues == []
    assert result.error_message is None
    assert result.raw_output == "output"
    assert result.raw_stderr == "stderr"
    assert result.execution_time_ms == 100.0
    assert result.exit_code == 0
    assert result.tool_version == "1.0.0"

    # Test __post_init__ behavior
    result_with_error = ToolExecutionResult(error_output="error")
    assert result_with_error.raw_stderr == "error"

    # Test success auto-determination
    result_auto_success = ToolExecutionResult(exit_code=0)
    assert result_auto_success.success is True

    result_auto_failure = ToolExecutionResult(exit_code=1)
    assert result_auto_failure.success is False


def test_tool_execution_result_properties():
    """Test properties of ToolExecutionResult."""
    issues = [
        ToolIssue(file_path=Path("test1.py"), severity="error"),
        ToolIssue(file_path=Path("test2.py"), severity="warning"),
        ToolIssue(file_path=Path("test3.py"), severity="error")
    ]

    result = ToolExecutionResult(issues=issues)

    assert result.has_errors is True
    assert result.error_count == 2
    assert result.warning_count == 1


def test_tool_execution_result_to_dict():
    """Test the to_dict method of ToolExecutionResult."""
    result = ToolExecutionResult(
        success=True,
        raw_output="a" * 600,  # Longer than 500 chars to test truncation
        execution_time_ms=100.0,
        exit_code=0,
        tool_version="1.0.0"
    )

    result_dict = result.to_dict()
    assert result_dict["success"] is True
    assert len(result_dict["raw_output"]) <= 500  # Should be truncated
    assert result_dict["execution_time_ms"] == 100.0
    assert result_dict["exit_code"] == 0
    assert result_dict["tool_version"] == "1.0.0"


def test_tool_adapter_settings():
    """Test ToolAdapterSettings."""
    settings = ToolAdapterSettings(
        tool_name="test_tool",
        tool_args=["--arg1", "--arg2"],
        use_json_output=True,
        fix_enabled=False,
        include_warnings=True,
        timeout_seconds=120
    )

    assert settings.tool_name == "test_tool"
    assert settings.tool_args == ["--arg1", "--arg2"]
    assert settings.use_json_output is True
    assert settings.fix_enabled is False
    assert settings.include_warnings is True
    assert settings.timeout_seconds == 120


class ConcreteToolAdapter(BaseToolAdapter):
    """Concrete implementation of BaseToolAdapter for testing."""

    @property
    def tool_name(self) -> str:
        return "test_tool"

    def build_command(
        self,
        files: list[Path],
        config=None,
    ) -> list[str]:
        return ["test_tool"] + [str(f) for f in files]

    async def parse_output(
        self,
        result,
    ) -> list[ToolIssue]:
        return []


def test_base_tool_adapter_initialization():
    """Test BaseToolAdapter initialization."""
    settings = ToolAdapterSettings(tool_name="test_tool")
    adapter = ConcreteToolAdapter(settings=settings)

    assert adapter.settings == settings
    assert adapter._tool_version is None
    assert adapter._tool_available is None


@pytest.mark.asyncio
async def test_base_tool_adapter_init():
    """Test BaseToolAdapter init method."""
    adapter = ConcreteToolAdapter()

    with patch.object(adapter, 'validate_tool_available', return_value=True), \
         patch.object(adapter, 'get_tool_version', return_value="1.0.0"), \
         patch.object(adapter, '_get_timeout_from_settings', return_value=60):

        await adapter.init()

        assert adapter.settings is not None
        assert adapter._tool_version == "1.0.0"


@pytest.mark.asyncio
async def test_validate_tool_available():
    """Test validate_tool_available method."""
    adapter = ConcreteToolAdapter()

    with patch('shutil.which', return_value="/usr/bin/test_tool"):
        result = await adapter.validate_tool_available()
        assert result is True
        assert adapter._tool_available is True

    # Test cached result
    adapter._tool_available = False
    result = await adapter.validate_tool_available()
    assert result is False


@pytest.mark.asyncio
async def test_get_tool_version():
    """Test get_tool_version method."""
    adapter = ConcreteToolAdapter()

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"1.0.0", b"")

    with patch('asyncio.create_subprocess_exec', return_value=mock_process):
        version = await adapter.get_tool_version()
        assert version == "1.0.0"
        assert adapter._tool_version == "1.0.0"


@pytest.mark.asyncio
async def test_execute_tool():
    """Test _execute_tool method."""
    adapter = ConcreteToolAdapter()
    adapter.settings = ToolAdapterSettings(timeout_seconds=30)

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"output", b"")
    mock_process.returncode = 0

    with patch('asyncio.create_subprocess_exec', return_value=mock_process):
        start_time = asyncio.get_event_loop().time()
        result = await adapter._execute_tool(
            ["test_tool", "file.py"],
            [Path("file.py")],
            start_time
        )

        assert result.success is True
        assert result.raw_output == "output"
        assert result.exit_code == 0


@pytest.mark.asyncio
async def test_is_gitignored():
    """Test _is_gitignored method."""
    adapter = ConcreteToolAdapter()

    # Test when git command returns 0 (file is ignored)
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        result = await adapter._is_gitignored(Path("ignored_file.py"))
        assert result is True

    # Test when git command returns non-zero (file is not ignored)
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 1
        result = await adapter._is_gitignored(Path("normal_file.py"))
        assert result is False


def test_get_standard_excludes():
    """Test _get_standard_excludes method."""
    adapter = ConcreteToolAdapter()

    # Test with regular config
    mock_config = Mock()
    mock_config.is_comprehensive_stage = False
    excludes = adapter._get_standard_excludes(mock_config)
    assert ".venv" in excludes
    assert "tests" not in excludes  # Should not be excluded for regular stage

    # Test with comprehensive stage
    mock_config.is_comprehensive_stage = True
    excludes = adapter._get_standard_excludes(mock_config)
    assert "tests" in excludes  # Should be excluded for comprehensive stage


def test_get_check_type():
    """Test _get_check_type method."""
    adapter = ConcreteToolAdapter()

    # Test different tool names
    class FormatAdapter(ConcreteToolAdapter):
        @property
        def tool_name(self) -> str:
            return "black"

    class TypeAdapter(ConcreteToolAdapter):
        @property
        def tool_name(self) -> str:
            return "zuban"

    class SecurityAdapter(ConcreteToolAdapter):
        @property
        def tool_name(self) -> str:
            return "gitleaks"

    class TestAdapter(ConcreteToolAdapter):
        @property
        def tool_name(self) -> str:
            return "pytest"

    class RefactorAdapter(ConcreteToolAdapter):
        @property
        def tool_name(self) -> str:
            return "refurb"

    from crackerjack.models.qa_results import QACheckType

    format_adapter = FormatAdapter()
    assert format_adapter._get_check_type() == QACheckType.FORMAT

    type_adapter = TypeAdapter()
    assert type_adapter._get_check_type() == QACheckType.TYPE

    security_adapter = SecurityAdapter()
    assert security_adapter._get_check_type() == QACheckType.SECURITY

    test_adapter = TestAdapter()
    assert test_adapter._get_check_type() == QACheckType.TEST

    refactor_adapter = RefactorAdapter()
    assert refactor_adapter._get_check_type() == QACheckType.REFACTOR

    # Test default case
    assert adapter._get_check_type() == QACheckType.LINT


def test_count_issues_by_severity():
    """Test _count_issues_by_severity method."""
    adapter = ConcreteToolAdapter()

    issues = [
        ToolIssue(file_path=Path("test1.py"), severity="error"),
        ToolIssue(file_path=Path("test2.py"), severity="warning"),
        ToolIssue(file_path=Path("test3.py"), severity="error"),
        ToolIssue(file_path=Path("test4.py"), severity="warning"),
        ToolIssue(file_path=Path("test5.py"), severity="info")
    ]

    error_count, warning_count = adapter._count_issues_by_severity(issues)
    assert error_count == 2
    assert warning_count == 2


def test_determine_qa_status_and_message():
    """Test _determine_qa_status_and_message method."""
    adapter = ConcreteToolAdapter()

    # Test with error message
    exec_result = ToolExecutionResult(error_message="Some error")
    status, message = adapter._determine_qa_status_and_message(exec_result, [])
    assert status == QAResultStatus.ERROR
    assert message == "Some error"

    # Test with non-zero exit code
    exec_result = ToolExecutionResult(exit_code=2)
    status, message = adapter._determine_qa_status_and_message(exec_result, [])
    assert status == QAResultStatus.ERROR
    assert message == "Tool exited with code 2"

    # Test with no issues
    exec_result = ToolExecutionResult(success=True)
    status, message = adapter._determine_qa_status_and_message(exec_result, [])
    assert status == QAResultStatus.SUCCESS
    assert message == "No issues found"

    # Test with errors
    issues = [
        ToolIssue(file_path=Path("test.py"), severity="error"),
        ToolIssue(file_path=Path("test2.py"), severity="warning")
    ]
    exec_result = ToolExecutionResult(success=True)
    status, message = adapter._determine_qa_status_and_message(exec_result, issues)
    assert status == QAResultStatus.FAILURE
    assert "Found 1 errors and 1 warnings" in message

    # Test with warnings only
    issues = [ToolIssue(file_path=Path("test.py"), severity="warning")]
    status, message = adapter._determine_qa_status_and_message(exec_result, issues)
    assert status == QAResultStatus.WARNING
    assert "Found 1 warnings" in message


def test_build_details_from_issues():
    """Test _build_details_from_issues method."""
    adapter = ConcreteToolAdapter()

    issues = [
        ToolIssue(file_path=Path("test1.py"), line_number=10, message="Error 1"),
        ToolIssue(file_path=Path("test2.py"), line_number=20, column_number=5, message="Error 2"),
    ]

    details = adapter._build_details_from_issues(issues)
    assert "test1.py:10: Error 1" in details
    assert "test2.py:20:5: Error 2" in details


def test_get_default_config():
    """Test get_default_config method."""
    adapter = ConcreteToolAdapter()
    config = adapter.get_default_config()

    assert config.check_id == adapter.module_id
    assert config.check_name == adapter.adapter_name
    assert config.enabled is True
    assert config.file_patterns == ["**/*.py"]
    assert config.timeout_seconds == 60
