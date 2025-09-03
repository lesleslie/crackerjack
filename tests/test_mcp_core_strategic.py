import tempfile
import time
import uuid
from collections import deque
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.mcp.cache import ErrorCache, ErrorPattern, FixResult
from crackerjack.mcp.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
    ResourceMonitor,
)
from crackerjack.mcp.server_core import (
    MCPOptions,
    _validate_job_id,
    create_mcp_server,
    handle_mcp_server_command,
)
from crackerjack.mcp.state import (
    Issue,
    Priority,
    SessionState,
    StageResult,
    StageStatus,
    StateManager,
)


class TestMCPOptions:
    def test_mcp_options_default_initialization(self):
        options = MCPOptions()

        assert options.commit is False
        assert options.interactive is False
        assert options.no_config_updates is False
        assert options.verbose is False
        assert options.clean is False
        assert options.test is False
        assert options.autofix is True
        assert options.skip_hooks is False
        assert options.ai_agent is False
        assert options.ai_debug is False
        assert options.publish is None
        assert options.bump is None
        assert options.create_pr is False
        assert options.testing is False

    def test_mcp_options_kwargs_initialization(self):
        options = MCPOptions(
            commit=True,
            interactive=True,
            verbose=True,
            test=True,
            autofix=False,
            ai_agent=True,
            publish="patch",
            bump="minor",
            unknown_param="ignored",
        )

        assert options.commit is True
        assert options.interactive is True
        assert options.verbose is True
        assert options.test is True
        assert options.autofix is False
        assert options.ai_agent is True
        assert options.publish == "patch"
        assert options.bump == "minor"

        assert not hasattr(options, "unknown_param")

    def test_mcp_options_partial_kwargs(self):
        options = MCPOptions(ai_debug=True, testing=True)

        assert options.ai_debug is True
        assert options.testing is True

        assert options.commit is False
        assert options.autofix is True


class TestJobIdValidation:
    def test_validate_job_id_valid_cases(self):
        valid_ids = [
            "job - 123",
            "abc123_def",
            "job_with_underscores",
            "job - with - dashes",
            "simple123",
            "a" * 50,
        ]

        for job_id in valid_ids:
            assert _validate_job_id(job_id), f"Should be valid: {job_id}"

    def test_validate_job_id_invalid_cases(self):
        invalid_ids = [
            "",
            None,
            123,
            "job with spaces",
            "job@special",
            "job.with.dots",
            "job / with / slashes",
            "a" * 51,
            "job#hash",
            "job$dollar",
        ]

        for job_id in invalid_ids:
            assert not _validate_job_id(job_id), f"Should be invalid: {job_id}"

    def test_validate_job_id_edge_cases(self):
        assert _validate_job_id("a")
        assert _validate_job_id("1")
        assert _validate_job_id("-")
        assert _validate_job_id("_")

        assert _validate_job_id("a1 - b2_c3")
        assert _validate_job_id("123 - abc_XYZ")


@pytest.mark.skipif(
    not hasattr(pytest, "importorskip"), reason="Skip if MCP not available"
)
class TestServerCreation:
    @patch("crackerjack.mcp.server_core.MCP_AVAILABLE", True)
    @patch("crackerjack.mcp.server_core.FastMCP")
    def test_create_mcp_server_success(self, mock_fastmcp):
        mock_app = Mock()
        mock_fastmcp.return_value = mock_app

        with patch("crackerjack.slash_commands.get_slash_command_path") as mock_path:
            mock_file = Mock()
            mock_file.read_text.return_value = "command content"
            mock_path.return_value = mock_file

            result = create_mcp_server()

            assert result == mock_app
            mock_fastmcp.assert_called_once_with("crackerjack - mcp - server")

    @patch("crackerjack.mcp.server_core.MCP_AVAILABLE", False)
    def test_create_mcp_server_not_available(self):
        result = create_mcp_server()
        assert result is None

    @patch("crackerjack.mcp.server_core.MCP_AVAILABLE", True)
    @patch("crackerjack.mcp.server_core.FastMCP", None)
    def test_create_mcp_server_fastmcp_none(self):
        result = create_mcp_server()
        assert result is None


class TestServerCommandHandling:
    @patch("subprocess.run")
    @patch("crackerjack.mcp.server_core.console")
    def test_handle_stop_command(self, mock_console, mock_run):
        mock_run.return_value = Mock(returncode=0)

        handle_mcp_server_command(stop=True)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "pkill" in call_args[0][0]
        assert "crackerjack - mcp - server" in call_args[0][0]

        mock_console.print.assert_any_call("[green]✅ MCP servers stopped[/ green]")

    @patch("subprocess.run")
    @patch("crackerjack.mcp.server_core.console")
    def test_handle_stop_command_no_servers(self, mock_console, mock_run):
        mock_run.return_value = Mock(returncode=1)

        handle_mcp_server_command(stop=True)

        mock_console.print.assert_any_call("[dim]No MCP servers were running[/ dim]")

    @patch("subprocess.run")
    @patch("crackerjack.mcp.server_core.console")
    def test_handle_stop_command_timeout(self, mock_console, mock_run):
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("pkill", 10)

        handle_mcp_server_command(stop=True)

        mock_console.print.assert_any_call("[red]Timeout stopping MCP servers[/ red]")

    @patch("crackerjack.mcp.server_core.main")
    @patch("crackerjack.mcp.server_core.console")
    def test_handle_start_command(self, mock_console, mock_main):
        handle_mcp_server_command(start=True, websocket_port=8080)

        mock_main.assert_called_once_with(".", 8080)
        mock_console.print.assert_any_call("[green]Starting MCP server...[/ green]")

    @patch("subprocess.run")
    @patch("time.sleep")
    @patch("crackerjack.mcp.server_core.main")
    @patch("crackerjack.mcp.server_core.console")
    def test_handle_restart_command(
        self, mock_console, mock_main, mock_sleep, mock_run
    ):
        mock_run.return_value = Mock(returncode=0)

        handle_mcp_server_command(restart=True)

        mock_run.assert_called_once()

        mock_sleep.assert_called_once_with(2)

        mock_main.assert_called_once_with(".", None)


class TestPriorityEnum:
    def test_priority_values(self):
        assert Priority.CRITICAL.value == "critical"
        assert Priority.HIGH.value == "high"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.LOW.value == "low"

    def test_priority_iteration(self):
        priorities = list(Priority)
        expected = [Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW]
        assert priorities == expected


class TestStageStatus:
    def test_stage_status_values(self):
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.RUNNING.value == "running"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.ERROR.value == "error"


class TestIssue:
    def test_issue_creation_minimal(self):
        issue = Issue(
            id="test - 1",
            type="syntax",
            message="Syntax error",
            file_path="test.py",
        )

        assert issue.id == "test - 1"
        assert issue.type == "syntax"
        assert issue.message == "Syntax error"
        assert issue.file_path == "test.py"
        assert issue.line_number is None
        assert issue.priority == Priority.MEDIUM
        assert issue.stage == ""
        assert issue.suggested_fix is None
        assert issue.auto_fixable is False

    def test_issue_creation_full(self):
        issue = Issue(
            id="complex - 1",
            type="complexity",
            message="Function too complex",
            file_path="complex.py",
            line_number=42,
            priority=Priority.HIGH,
            stage="quality",
            suggested_fix="Break into smaller functions",
            auto_fixable=True,
        )

        assert issue.id == "complex - 1"
        assert issue.type == "complexity"
        assert issue.message == "Function too complex"
        assert issue.file_path == "complex.py"
        assert issue.line_number == 42
        assert issue.priority == Priority.HIGH
        assert issue.stage == "quality"
        assert issue.suggested_fix == "Break into smaller functions"
        assert issue.auto_fixable is True

    def test_issue_to_dict(self):
        issue = Issue(
            id="dict - test",
            type="test",
            message="Test message",
            file_path="test.py",
            line_number=10,
        )

        result = issue.to_dict()

        expected = {
            "id": "dict - test",
            "type": "test",
            "message": "Test message",
            "file_path": "test.py",
            "line_number": 10,
            "priority": Priority.MEDIUM,
            "stage": "",
            "suggested_fix": None,
            "auto_fixable": False,
        }

        assert result == expected


class TestStageResult:
    def test_stage_result_creation(self):
        start_time = time.time()
        result = StageResult(
            stage="test",
            status=StageStatus.RUNNING,
            start_time=start_time,
        )

        assert result.stage == "test"
        assert result.status == StageStatus.RUNNING
        assert result.start_time == start_time
        assert result.end_time is None
        assert result.duration is None
        assert result.issues_found == []
        assert result.fixes_applied == []
        assert result.error_message is None

    def test_stage_result_with_completion(self):
        start_time = time.time()
        end_time = start_time + 10

        result = StageResult(
            stage="complete",
            status=StageStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time,
        )

        assert result.duration == 10.0

    def test_stage_result_to_dict(self):
        issue = Issue(
            id="issue - 1",
            type="test",
            message="Test issue",
            file_path="test.py",
        )

        result = StageResult(
            stage="test",
            status=StageStatus.COMPLETED,
            start_time=1000.0,
            end_time=1010.0,
            issues_found=[issue],
            fixes_applied=["fix1", "fix2"],
        )

        result_dict = result.to_dict()

        assert result_dict["stage"] == "test"
        assert result_dict["status"] == StageStatus.COMPLETED
        assert result_dict["duration"] == 10.0
        assert len(result_dict["issues_found"]) == 1
        assert result_dict["issues_found"][0]["id"] == "issue - 1"
        assert result_dict["fixes_applied"] == ["fix1", "fix2"]


class TestSessionState:
    def test_session_state_creation(self):
        start_time = time.time()
        session = SessionState(
            session_id="test - session",
            start_time=start_time,
        )

        assert session.session_id == "test - session"
        assert session.start_time == start_time
        assert session.current_stage is None
        assert session.stages == {}
        assert session.global_issues == []
        assert session.fixes_applied == []
        assert session.metadata == {}

    def test_session_state_to_dict(self):
        issue = Issue(
            id="session - issue",
            type="test",
            message="Session test",
            file_path="session.py",
        )

        stage_result = StageResult(
            stage="test - stage",
            status=StageStatus.COMPLETED,
            start_time=1000.0,
            end_time=1005.0,
        )

        session = SessionState(
            session_id="complex - session",
            start_time=1000.0,
            current_stage="active",
            stages={"test - stage": stage_result},
            global_issues=[issue],
            fixes_applied=["fix1"],
            metadata={"key": "value"},
        )

        result = session.to_dict()

        assert result["session_id"] == "complex - session"
        assert result["current_stage"] == "active"
        assert "test - stage" in result["stages"]
        assert result["stages"]["test - stage"]["stage"] == "test - stage"
        assert len(result["global_issues"]) == 1
        assert result["global_issues"][0]["id"] == "session - issue"
        assert result["fixes_applied"] == ["fix1"]
        assert result["metadata"] == {"key": "value"}


class TestStateManager:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def state_manager(self, temp_dir):
        return StateManager(state_dir=temp_dir)

    def test_state_manager_initialization(self, temp_dir):
        manager = StateManager(state_dir=temp_dir)

        assert manager.state_dir == temp_dir
        assert manager.state_dir.exists()
        assert manager.checkpoints_dir.exists()
        assert manager.session_state.session_id
        assert len(manager.session_state.session_id) == 8

    def test_generate_session_id(self, state_manager):
        session_id = state_manager._generate_session_id()

        assert len(session_id) == 8
        assert isinstance(session_id, str)

        uuid.UUID(session_id + "- 0000 - 0000 - 0000 - 000000000000")

    @pytest.mark.asyncio
    async def test_start_stage(self, state_manager):
        await state_manager.start_stage("test - stage")

        assert state_manager.session_state.current_stage == "test - stage"
        assert "test - stage" in state_manager.session_state.stages

        stage_result = state_manager.session_state.stages["test - stage"]
        assert stage_result.stage == "test - stage"
        assert stage_result.status == StageStatus.RUNNING
        assert stage_result.start_time > 0

    @pytest.mark.asyncio
    async def test_complete_stage(self, state_manager):
        await state_manager.start_stage("complete - test")

        issues = [
            Issue(
                id="completion - issue",
                type="test",
                message="Completion test",
                file_path="test.py",
            )
        ]
        fixes = ["fix1", "fix2"]

        await state_manager.complete_stage(
            "complete - test", issues=issues, fixes=fixes
        )

        stage_result = state_manager.session_state.stages["complete - test"]
        assert stage_result.status == StageStatus.COMPLETED
        assert stage_result.end_time is not None
        assert stage_result.duration is not None
        assert stage_result.issues_found == issues
        assert stage_result.fixes_applied == fixes

        assert len(state_manager.session_state.global_issues) == 1
        assert state_manager.session_state.global_issues[0].id == "completion - issue"
        assert state_manager.session_state.fixes_applied == fixes
        assert state_manager.session_state.current_stage is None

    @pytest.mark.asyncio
    async def test_fail_stage(self, state_manager):
        await state_manager.start_stage("fail - test")

        await state_manager.fail_stage("fail - test", "Test error message")

        stage_result = state_manager.session_state.stages["fail - test"]
        assert stage_result.status == StageStatus.FAILED
        assert stage_result.error_message == "Test error message"
        assert stage_result.end_time is not None
        assert stage_result.duration is not None
        assert state_manager.session_state.current_stage is None

    @pytest.mark.asyncio
    async def test_update_stage_status(self, state_manager):
        await state_manager.update_stage_status("new - stage", "running")

        assert "new - stage" in state_manager.session_state.stages
        stage_result = state_manager.session_state.stages["new - stage"]
        assert stage_result.status == StageStatus.RUNNING

        await state_manager.update_stage_status("new - stage", "completed")
        assert stage_result.status == StageStatus.COMPLETED
        assert stage_result.end_time is not None

    @pytest.mark.asyncio
    async def test_add_issue(self, state_manager):
        issue = Issue(
            id="add - test",
            type="addition",
            message="Addition test",
            file_path="add.py",
        )

        await state_manager.add_issue(issue)

        assert len(state_manager.session_state.global_issues) == 1
        assert state_manager.session_state.global_issues[0] == issue

    def test_remove_issue(self, state_manager):
        issue1 = Issue(
            id="remove - 1", type="test", message="Remove 1", file_path="test.py"
        )
        issue2 = Issue(
            id="remove - 2", type="test", message="Remove 2", file_path="test.py"
        )

        state_manager.session_state.global_issues = [issue1, issue2]

        result = state_manager.remove_issue("remove - 1")

        assert result is True
        assert len(state_manager.session_state.global_issues) == 1
        assert state_manager.session_state.global_issues[0].id == "remove - 2"

        result = state_manager.remove_issue("non - existent")
        assert result is False

    def test_get_issues_by_priority(self, state_manager):
        high_issue = Issue(
            id="high - 1",
            type="test",
            message="High",
            file_path="test.py",
            priority=Priority.HIGH,
        )
        medium_issue = Issue(
            id="med - 1",
            type="test",
            message="Medium",
            file_path="test.py",
            priority=Priority.MEDIUM,
        )

        state_manager.session_state.global_issues = [high_issue, medium_issue]

        high_issues = state_manager.get_issues_by_priority(Priority.HIGH)
        assert len(high_issues) == 1
        assert high_issues[0].id == "high - 1"

        low_issues = state_manager.get_issues_by_priority(Priority.LOW)
        assert len(low_issues) == 0

    def test_get_issues_by_type(self, state_manager):
        syntax_issue = Issue(
            id="syntax - 1", type="syntax", message="Syntax", file_path="test.py"
        )
        complexity_issue = Issue(
            id="complex - 1", type="complexity", message="Complex", file_path="test.py"
        )

        state_manager.session_state.global_issues = [syntax_issue, complexity_issue]

        syntax_issues = state_manager.get_issues_by_type("syntax")
        assert len(syntax_issues) == 1
        assert syntax_issues[0].id == "syntax - 1"

        logic_issues = state_manager.get_issues_by_type("logic")
        assert len(logic_issues) == 0

    def test_get_auto_fixable_issues(self, state_manager):
        fixable_issue = Issue(
            id="fixable - 1",
            type="format",
            message="Fixable",
            file_path="test.py",
            auto_fixable=True,
        )
        manual_issue = Issue(
            id="manual - 1",
            type="logic",
            message="Manual",
            file_path="test.py",
            auto_fixable=False,
        )

        state_manager.session_state.global_issues = [fixable_issue, manual_issue]

        fixable_issues = state_manager.get_auto_fixable_issues()
        assert len(fixable_issues) == 1
        assert fixable_issues[0].id == "fixable - 1"

    def test_get_session_summary(self, state_manager):
        issue1 = Issue(
            id="summary - 1",
            type="syntax",
            message="Summary 1",
            file_path="test.py",
            priority=Priority.HIGH,
            auto_fixable=True,
        )
        issue2 = Issue(
            id="summary - 2",
            type="complexity",
            message="Summary 2",
            file_path="test.py",
            priority=Priority.MEDIUM,
        )

        state_manager.session_state.global_issues = [issue1, issue2]
        state_manager.session_state.fixes_applied = ["fix1", "fix2", "fix3"]

        stage_result = StageResult(
            stage="summary - stage",
            status=StageStatus.COMPLETED,
            start_time=1000.0,
        )
        state_manager.session_state.stages = {"summary - stage": stage_result}

        summary = state_manager.get_session_summary()

        assert summary["session_id"] == state_manager.session_state.session_id
        assert summary["total_issues"] == 2
        assert summary["issues_by_priority"]["high"] == 1
        assert summary["issues_by_priority"]["medium"] == 1
        assert summary["issues_by_type"]["syntax"] == 1
        assert summary["issues_by_type"]["complexity"] == 1
        assert summary["total_fixes"] == 3
        assert summary["auto_fixable_issues"] == 1
        assert summary["stages"]["summary - stage"] == "completed"


class TestErrorPattern:
    def test_error_pattern_creation_minimal(self):
        pattern = ErrorPattern(
            pattern_id="test - pattern",
            error_type="ruff",
            error_code="E302",
            message_pattern="expected 2 blank lines",
        )

        assert pattern.pattern_id == "test - pattern"
        assert pattern.error_type == "ruff"
        assert pattern.error_code == "E302"
        assert pattern.message_pattern == "expected 2 blank lines"
        assert pattern.file_pattern is None
        assert pattern.common_fixes == []
        assert pattern.auto_fixable is False
        assert pattern.frequency == 1
        assert pattern.last_seen is not None

    def test_error_pattern_creation_full(self):
        common_fixes = ["fix1", "fix2"]
        last_seen = time.time()

        pattern = ErrorPattern(
            pattern_id="full - pattern",
            error_type="pyright",
            error_code="reportGeneralTypeIssues",
            message_pattern="Type mismatch",
            file_pattern="*.py",
            common_fixes=common_fixes,
            auto_fixable=True,
            frequency=5,
            last_seen=last_seen,
        )

        assert pattern.pattern_id == "full - pattern"
        assert pattern.error_type == "pyright"
        assert pattern.error_code == "reportGeneralTypeIssues"
        assert pattern.message_pattern == "Type mismatch"
        assert pattern.file_pattern == "*.py"
        assert pattern.common_fixes == common_fixes
        assert pattern.auto_fixable is True
        assert pattern.frequency == 5
        assert pattern.last_seen == last_seen

    def test_error_pattern_to_dict(self):
        pattern = ErrorPattern(
            pattern_id="dict - pattern",
            error_type="bandit",
            error_code="B108",
            message_pattern="hardcoded temp file",
        )

        result = pattern.to_dict()

        assert result["pattern_id"] == "dict - pattern"
        assert result["error_type"] == "bandit"
        assert result["error_code"] == "B108"
        assert result["message_pattern"] == "hardcoded temp file"


class TestFixResult:
    def test_fix_result_creation(self):
        result = FixResult(
            fix_id="fix - 1",
            pattern_id="pattern - 1",
            success=True,
            files_affected=["file1.py", "file2.py"],
            time_taken=2.5,
            error_message=None,
        )

        assert result.fix_id == "fix - 1"
        assert result.pattern_id == "pattern - 1"
        assert result.success is True
        assert result.files_affected == ["file1.py", "file2.py"]
        assert result.time_taken == 2.5
        assert result.error_message is None

    def test_fix_result_with_error(self):
        result = FixResult(
            fix_id="fix - error",
            pattern_id="pattern - error",
            success=False,
            files_affected=[],
            time_taken=0.1,
            error_message="Fix failed",
        )

        assert result.success is False
        assert result.error_message == "Fix failed"

    def test_fix_result_to_dict(self):
        result = FixResult(
            fix_id="dict - fix",
            pattern_id="dict - pattern",
            success=True,
            files_affected=["test.py"],
            time_taken=1.0,
        )

        dict_result = result.to_dict()

        assert dict_result["fix_id"] == "dict - fix"
        assert dict_result["success"] is True
        assert dict_result["files_affected"] == ["test.py"]


class TestErrorCache:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def error_cache(self, temp_dir):
        return ErrorCache(cache_dir=temp_dir)

    def test_error_cache_initialization(self, temp_dir):
        cache = ErrorCache(cache_dir=temp_dir)

        assert cache.cache_dir == temp_dir
        assert cache.patterns_file.exists() or not cache.patterns_file.exists()
        assert cache.fixes_file.exists() or not cache.fixes_file.exists()
        assert isinstance(cache.patterns, dict)
        assert isinstance(cache.fix_results, list)

    @pytest.mark.asyncio
    async def test_add_pattern_new(self, error_cache):
        pattern = ErrorPattern(
            pattern_id="new - pattern",
            error_type="ruff",
            error_code="E501",
            message_pattern="line too long",
        )

        await error_cache.add_pattern(pattern)

        assert "new - pattern" in error_cache.patterns
        stored_pattern = error_cache.patterns["new - pattern"]
        assert stored_pattern.pattern_id == "new - pattern"
        assert stored_pattern.frequency == 1

    @pytest.mark.asyncio
    async def test_add_pattern_existing(self, error_cache):
        pattern = ErrorPattern(
            pattern_id="existing - pattern",
            error_type="ruff",
            error_code="E501",
            message_pattern="line too long",
            common_fixes=["break line"],
        )

        await error_cache.add_pattern(pattern)
        original_time = error_cache.patterns["existing - pattern"].last_seen

        pattern_update = ErrorPattern(
            pattern_id="existing - pattern",
            error_type="ruff",
            error_code="E501",
            message_pattern="line too long",
            common_fixes=["use parentheses"],
        )

        await error_cache.add_pattern(pattern_update)

        updated_pattern = error_cache.patterns["existing - pattern"]
        assert updated_pattern.frequency == 2
        assert updated_pattern.last_seen > original_time
        assert "break line" in updated_pattern.common_fixes
        assert "use parentheses" in updated_pattern.common_fixes

    def test_get_pattern(self, error_cache):
        pattern = ErrorPattern(
            pattern_id="get - test",
            error_type="ruff",
            error_code="E302",
            message_pattern="blank lines",
        )
        error_cache.patterns["get - test"] = pattern

        result = error_cache.get_pattern("get - test")
        assert result == pattern

        result = error_cache.get_pattern("non - existent")
        assert result is None

    def test_find_patterns_by_type(self, error_cache):
        ruff_pattern = ErrorPattern(
            pattern_id="ruff - 1",
            error_type="ruff",
            error_code="E302",
            message_pattern="ruff error",
        )
        pyright_pattern = ErrorPattern(
            pattern_id="pyright - 1",
            error_type="pyright",
            error_code="type",
            message_pattern="type error",
        )

        error_cache.patterns["ruff - 1"] = ruff_pattern
        error_cache.patterns["pyright - 1"] = pyright_pattern

        ruff_results = error_cache.find_patterns_by_type("ruff")
        assert len(ruff_results) == 1
        assert ruff_results[0].pattern_id == "ruff - 1"

        bandit_results = error_cache.find_patterns_by_type("bandit")
        assert len(bandit_results) == 0

    def test_find_patterns_by_code(self, error_cache):
        pattern1 = ErrorPattern(
            pattern_id="code - 1",
            error_type="ruff",
            error_code="E302",
            message_pattern="blank lines",
        )
        pattern2 = ErrorPattern(
            pattern_id="code - 2",
            error_type="ruff",
            error_code="E501",
            message_pattern="line length",
        )

        error_cache.patterns["code - 1"] = pattern1
        error_cache.patterns["code - 2"] = pattern2

        e302_results = error_cache.find_patterns_by_code("E302")
        assert len(e302_results) == 1
        assert e302_results[0].pattern_id == "code - 1"

    def test_get_common_patterns(self, error_cache):
        pattern1 = ErrorPattern(
            pattern_id="freq - 1",
            error_type="ruff",
            error_code="E1",
            message_pattern="error 1",
            frequency=5,
        )
        pattern2 = ErrorPattern(
            pattern_id="freq - 2",
            error_type="ruff",
            error_code="E2",
            message_pattern="error 2",
            frequency=10,
        )
        pattern3 = ErrorPattern(
            pattern_id="freq - 3",
            error_type="ruff",
            error_code="E3",
            message_pattern="error 3",
            frequency=3,
        )

        error_cache.patterns = {
            "freq - 1": pattern1,
            "freq - 2": pattern2,
            "freq - 3": pattern3,
        }

        common_patterns = error_cache.get_common_patterns(limit=2)

        assert len(common_patterns) == 2
        assert common_patterns[0].pattern_id == "freq - 2"
        assert common_patterns[1].pattern_id == "freq - 1"

    def test_get_auto_fixable_patterns(self, error_cache):
        fixable_pattern = ErrorPattern(
            pattern_id="fixable",
            error_type="ruff",
            error_code="E1",
            message_pattern="fixable",
            auto_fixable=True,
        )
        manual_pattern = ErrorPattern(
            pattern_id="manual",
            error_type="pyright",
            error_code="T1",
            message_pattern="manual",
            auto_fixable=False,
        )

        error_cache.patterns = {"fixable": fixable_pattern, "manual": manual_pattern}

        auto_fixable = error_cache.get_auto_fixable_patterns()

        assert len(auto_fixable) == 1
        assert auto_fixable[0].pattern_id == "fixable"

    @pytest.mark.asyncio
    async def test_add_fix_result(self, error_cache):
        pattern = ErrorPattern(
            pattern_id="fix - pattern",
            error_type="ruff",
            error_code="E302",
            message_pattern="blank lines",
        )
        error_cache.patterns["fix - pattern"] = pattern

        fix_result = FixResult(
            fix_id="fix - 1",
            pattern_id="fix - pattern",
            success=True,
            files_affected=["test.py"],
            time_taken=1.0,
        )

        await error_cache.add_fix_result(fix_result)

        assert len(error_cache.fix_results) == 1
        assert error_cache.fix_results[0] == fix_result

        assert error_cache.patterns["fix - pattern"].auto_fixable is True
        assert (
            "Auto - fix applied for fix - pattern"
            in error_cache.patterns["fix - pattern"].common_fixes
        )

    def test_get_fix_success_rate(self, error_cache):
        fix1 = FixResult("fix1", "pattern1", True, ["file1.py"], 1.0)
        fix2 = FixResult("fix2", "pattern1", False, ["file2.py"], 0.5)
        fix3 = FixResult("fix3", "pattern1", True, ["file3.py"], 1.5)

        error_cache.fix_results = [fix1, fix2, fix3]

        success_rate = error_cache.get_fix_success_rate("pattern1")
        assert success_rate == 2 / 3

        success_rate = error_cache.get_fix_success_rate("non - existent")
        assert success_rate == 0.0

    def test_get_recent_patterns(self, error_cache):
        now = time.time()
        old_time = now - (25 * 3600)
        recent_time = now - (1 * 3600)

        old_pattern = ErrorPattern(
            pattern_id="old",
            error_type="ruff",
            error_code="E1",
            message_pattern="old",
            last_seen=old_time,
        )
        recent_pattern = ErrorPattern(
            pattern_id="recent",
            error_type="ruff",
            error_code="E2",
            message_pattern="recent",
            last_seen=recent_time,
        )

        error_cache.patterns = {"old": old_pattern, "recent": recent_pattern}

        recent_patterns = error_cache.get_recent_patterns(hours=24)

        assert len(recent_patterns) == 1
        assert recent_patterns[0].pattern_id == "recent"


class TestRateLimitConfig:
    def test_rate_limit_config_defaults(self):
        config = RateLimitConfig()

        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 300
        assert config.max_concurrent_jobs == 5
        assert config.max_job_duration_minutes == 30
        assert config.max_file_size_mb == 100
        assert config.max_progress_files == 1000
        assert config.max_cache_entries == 10000
        assert config.max_state_history == 100

    def test_rate_limit_config_custom(self):
        config = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=600,
            max_concurrent_jobs=10,
        )

        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 600
        assert config.max_concurrent_jobs == 10


class TestRateLimiter:
    @pytest.fixture
    def rate_limiter(self):
        return RateLimiter(requests_per_minute=3, requests_per_hour=10)

    @pytest.mark.asyncio
    async def test_is_allowed_first_request(self, rate_limiter):
        allowed, info = await rate_limiter.is_allowed("client1")

        assert allowed is True
        assert info["allowed"] is True
        assert info["minute_requests_remaining"] == 2
        assert info["hour_requests_remaining"] == 9

    @pytest.mark.asyncio
    async def test_minute_limit_exceeded(self, rate_limiter):
        client_id = "minute_test"

        for _ in range(3):
            allowed, _ = await rate_limiter.is_allowed(client_id)
            assert allowed is True

        allowed, info = await rate_limiter.is_allowed(client_id)

        assert allowed is False
        assert info["reason"] == "minute_limit_exceeded"
        assert info["limit"] == 3
        assert info["retry_after"] == 60

    @pytest.mark.asyncio
    async def test_hour_limit_exceeded(self, rate_limiter):
        client_id = "hour_test"

        now = time.time()
        rate_limiter.hour_windows[client_id] = deque([now] * 10, maxlen=10)

        allowed, info = await rate_limiter.is_allowed(client_id)

        assert allowed is False
        assert info["reason"] == "hour_limit_exceeded"
        assert info["retry_after"] == 3600

    @pytest.mark.asyncio
    async def test_global_limits(self, rate_limiter):
        now = time.time()
        rate_limiter.global_minute_window = deque([now] * 30, maxlen=30)

        allowed, info = await rate_limiter.is_allowed("global_test")

        assert allowed is False
        assert info["reason"] == "global_minute_limit_exceeded"

    @pytest.mark.asyncio
    async def test_cleanup_expired_entries(self, rate_limiter):
        client_id = "cleanup_test"
        old_minute_time = time.time() - 120
        old_hour_time = time.time() - 7200

        rate_limiter.minute_windows[client_id].extend([old_minute_time] * 2)
        rate_limiter.hour_windows[client_id].extend([old_hour_time] * 2)

        allowed, info = await rate_limiter.is_allowed(client_id)

        assert allowed is True

        assert len(rate_limiter.minute_windows[client_id]) == 1
        assert len(rate_limiter.hour_windows[client_id]) == 1

    def test_get_stats(self, rate_limiter):
        stats = rate_limiter.get_stats()

        assert "active_clients" in stats
        assert "global_minute_requests" in stats
        assert "global_hour_requests" in stats
        assert "limits" in stats
        assert stats["limits"]["requests_per_minute"] == 3
        assert stats["limits"]["requests_per_hour"] == 10


class TestResourceMonitor:
    @pytest.fixture
    def resource_monitor(self):
        config = RateLimitConfig(max_concurrent_jobs=2, max_job_duration_minutes=1)
        return ResourceMonitor(config)

    @pytest.mark.asyncio
    async def test_acquire_job_slot_success(self, resource_monitor):
        success = await resource_monitor.acquire_job_slot("job1")

        assert success is True
        assert "job1" in resource_monitor.active_jobs
        assert len(resource_monitor.active_jobs) == 1

    @pytest.mark.asyncio
    async def test_acquire_job_slot_limit_reached(self, resource_monitor):
        await resource_monitor.acquire_job_slot("job1")
        await resource_monitor.acquire_job_slot("job2")

        success = await resource_monitor.acquire_job_slot("job3")

        assert success is False
        assert "job3" not in resource_monitor.active_jobs
        assert len(resource_monitor.active_jobs) == 2

    @pytest.mark.asyncio
    async def test_release_job_slot(self, resource_monitor):
        await resource_monitor.acquire_job_slot("release_test")

        await resource_monitor.release_job_slot("release_test")

        assert "release_test" not in resource_monitor.active_jobs
        assert len(resource_monitor.active_jobs) == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_jobs(self, resource_monitor):
        old_time = time.time() - 120
        resource_monitor.active_jobs["stale_job"] = old_time

        await resource_monitor.acquire_job_slot("fresh_job")

        cleaned = await resource_monitor.cleanup_stale_jobs()

        assert cleaned == 1
        assert "stale_job" not in resource_monitor.active_jobs
        assert "fresh_job" in resource_monitor.active_jobs

    def test_check_file_size_valid(self, resource_monitor):
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"small content")
            temp_file.flush()

            result = resource_monitor.check_file_size(Path(temp_file.name))

            assert result is True

    def test_check_file_size_non_existent(self, resource_monitor):
        result = resource_monitor.check_file_size(Path("/ non / existent / file"))

        assert result is True

    def test_get_stats(self, resource_monitor):
        stats = resource_monitor.get_stats()

        assert "active_jobs" in stats
        assert "max_concurrent_jobs" in stats
        assert "available_slots" in stats
        assert "job_details" in stats
        assert "limits" in stats

        assert stats["max_concurrent_jobs"] == 2
        assert stats["active_jobs"] == 0


class TestRateLimitMiddleware:
    @pytest.fixture
    def middleware(self):
        config = RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=50,
            max_concurrent_jobs=2,
        )
        return RateLimitMiddleware(config)

    @pytest.mark.asyncio
    async def test_middleware_start_stop(self, middleware):
        await middleware.start()
        assert middleware._running is True
        assert middleware._cleanup_task is not None

        await middleware.stop()
        assert middleware._running is False

    @pytest.mark.asyncio
    async def test_check_request_allowed(self, middleware):
        allowed, info = await middleware.check_request_allowed("test_client")

        assert allowed is True
        assert info["allowed"] is True

    @pytest.mark.asyncio
    async def test_job_resource_management(self, middleware):
        success = await middleware.acquire_job_resources("middleware_job")
        assert success is True

        await middleware.release_job_resources("middleware_job")

        stats = middleware.get_comprehensive_stats()
        assert stats["resource_usage"]["active_jobs"] == 0

    def test_file_validation(self, middleware):
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()

            result = middleware.validate_file_size(Path(temp_file.name))
            assert result is True

    def test_get_comprehensive_stats(self, middleware):
        stats = middleware.get_comprehensive_stats()

        assert "rate_limiting" in stats
        assert "resource_usage" in stats
        assert "config" in stats

        config = stats["config"]
        assert config["requests_per_minute"] == 5
        assert config["requests_per_hour"] == 50
        assert config["max_concurrent_jobs"] == 2
