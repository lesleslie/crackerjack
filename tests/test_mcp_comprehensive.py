"""
Comprehensive tests for MCP (Model Context Protocol) components with extensive mocking.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.mcp.cache import ErrorCache, ErrorPattern, FixResult
from crackerjack.mcp.server import main as mcp_main
from crackerjack.mcp.state import (
    Issue,
    Priority,
    SessionState,
    StageResult,
    StageStatus,
    StateManager,
)


class TestErrorPattern:
    """Test ErrorPattern dataclass."""

    def test_error_pattern_creation(self):
        """Test creating an ErrorPattern."""
        pattern = ErrorPattern(
            pattern_id="test_pattern_1",
            error_type="syntax_error",
            error_code="E999",
            message_pattern="SyntaxError",
            file_pattern="*.py",
            common_fixes=["Check syntax"],
        )

        assert pattern.pattern_id == "test_pattern_1"
        assert pattern.error_type == "syntax_error"
        assert pattern.error_code == "E999"
        assert pattern.message_pattern == "SyntaxError"
        assert pattern.file_pattern == "*.py"
        assert pattern.common_fixes == ["Check syntax"]

    def test_error_pattern_defaults(self):
        """Test ErrorPattern with default values."""
        pattern = ErrorPattern(
            pattern_id="test_pattern_2",
            error_type="error",
            error_code="E001",
            message_pattern="Error occurred",
        )

        assert pattern.auto_fixable is False
        assert pattern.frequency == 1
        assert pattern.common_fixes == []

    def test_error_pattern_to_dict(self):
        """Test converting ErrorPattern to dict."""
        pattern = ErrorPattern(
            pattern_id="test_pattern_3",
            error_type="import_error",
            error_code="E401",
            message_pattern="ImportError",
            file_pattern="*.py",
        )

        result = pattern.to_dict()

        assert isinstance(result, dict)
        assert result["pattern_id"] == "test_pattern_3"
        assert result["error_type"] == "import_error"
        assert result["error_code"] == "E401"

    def test_error_pattern_post_init(self):
        """Test ErrorPattern post_init behavior."""
        pattern = ErrorPattern(
            pattern_id="test_pattern_4",
            error_type="type_error",
            error_code="E302",
            message_pattern="TypeError",
        )

        assert pattern.common_fixes == []
        assert pattern.last_seen is not None
        assert pattern.last_seen > 0


class TestFixResult:
    """Test FixResult dataclass."""

    def test_fix_result_creation(self):
        """Test creating a FixResult."""
        result = FixResult(
            fix_id="fix_123",
            pattern_id="test_pattern",
            success=True,
            files_affected=["file1.py", "file2.py"],
            time_taken=1.5,
            error_message=None,
        )

        assert result.fix_id == "fix_123"
        assert result.pattern_id == "test_pattern"
        assert result.success is True
        assert result.files_affected == ["file1.py", "file2.py"]
        assert result.time_taken == 1.5
        assert result.error_message is None

    def test_fix_result_to_dict(self):
        """Test converting FixResult to dict."""
        result = FixResult(
            fix_id="fix_456",
            pattern_id="test",
            success=False,
            files_affected=[],
            time_taken=0.5,
            error_message="Fix failed",
        )

        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["fix_id"] == "fix_456"
        assert data["pattern_id"] == "test"
        assert data["success"] is False
        assert data["error_message"] == "Fix failed"


class TestErrorCache:
    """Test ErrorCache with extensive mocking."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "cache"

    @pytest.fixture
    def error_cache(self, cache_dir):
        """Create ErrorCache instance."""
        return ErrorCache(cache_dir)

    def test_init(self, error_cache, cache_dir):
        """Test ErrorCache initialization."""
        assert error_cache.cache_dir == cache_dir
        assert error_cache.patterns_file == cache_dir / "error_patterns.json"
        assert error_cache.results_file == cache_dir / "cached_results.json"

    def test_ensure_cache_dir(self, error_cache, cache_dir):
        """Test cache directory creation."""
        # Directory shouldn't exist initially
        assert not cache_dir.exists()

        error_cache._ensure_cache_dir()

        # Directory should be created
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_load_patterns_file_not_exists(self, error_cache):
        """Test loading patterns when file doesn't exist."""
        # Clear existing patterns and reload
        error_cache.patterns = {}
        error_cache._load_cache()

        assert len(error_cache.patterns) == 0

    def test_load_patterns_with_data(self, error_cache, cache_dir):
        """Test loading patterns from existing file."""
        # Create cache directory and patterns file
        cache_dir.mkdir(parents=True)
        patterns_data = {
            "syntax_1": {
                "pattern_id": "syntax_1",
                "error_type": "syntax_error",
                "error_code": "E999",
                "message_pattern": "SyntaxError",
                "file_pattern": "*.py",
                "common_fixes": [],
                "auto_fixable": False,
                "frequency": 1,
                "last_seen": time.time(),
            }
        }

        patterns_file = cache_dir / "error_patterns.json"
        patterns_file.write_text(json.dumps(patterns_data))

        # Reload cache
        error_cache._load_cache()

        assert len(error_cache.patterns) == 1
        pattern = error_cache.get_pattern("syntax_1")
        assert pattern is not None
        assert pattern.error_type == "syntax_error"

    def test_save_patterns(self, error_cache, cache_dir):
        """Test saving patterns to file."""
        pattern = ErrorPattern(
            pattern_id="test_error_1",
            error_type="test_error",
            error_code="E001",
            message_pattern="Test error",
            file_pattern="*.py",
        )

        error_cache.add_pattern(pattern)

        # Check file was created
        patterns_file = cache_dir / "error_patterns.json"
        assert patterns_file.exists()

        # Check file content
        data = json.loads(patterns_file.read_text())
        assert "test_error_1" in data
        assert data["test_error_1"]["error_type"] == "test_error"

    def test_add_pattern(self, error_cache):
        """Test adding a new pattern."""
        pattern = ErrorPattern(
            pattern_id="new_error_1",
            error_type="new_error",
            error_code="E002",
            message_pattern="New error",
            file_pattern="*.py",
        )

        with patch.object(error_cache, "_save_patterns") as mock_save:
            error_cache.add_pattern(pattern)

            mock_save.assert_called_once()
            assert error_cache.get_pattern("new_error_1") == pattern

    def test_find_patterns_by_type(self, error_cache):
        """Test finding patterns by error type."""
        pattern1 = ErrorPattern(
            pattern_id="syntax_1",
            error_type="syntax",
            error_code="E999",
            message_pattern="SyntaxError",
        )
        pattern2 = ErrorPattern(
            pattern_id="import_1",
            error_type="import",
            error_code="E401",
            message_pattern="ImportError",
        )

        error_cache.add_pattern(pattern1)
        error_cache.add_pattern(pattern2)

        matches = error_cache.find_patterns_by_type("syntax")

        assert len(matches) == 1
        assert matches[0].error_type == "syntax"

    def test_add_fix_result(self, error_cache):
        """Test adding a fix result."""
        result = FixResult(
            fix_id="fix_123",
            pattern_id="test_pattern",
            success=True,
            files_affected=["file1.py"],
            time_taken=1.0,
        )

        with patch.object(error_cache, "_save_fixes") as mock_save:
            error_cache.add_fix_result(result)

            mock_save.assert_called_once()

    def test_get_fix_success_rate(self, error_cache):
        """Test retrieving fix success rate."""
        result1 = FixResult(
            fix_id="fix_1",
            pattern_id="pattern1",
            success=True,
            files_affected=[],
            time_taken=1.0,
        )
        result2 = FixResult(
            fix_id="fix_2",
            pattern_id="pattern1",
            success=False,
            files_affected=[],
            time_taken=0.5,
        )

        error_cache.add_fix_result(result1)
        error_cache.add_fix_result(result2)

        success_rate = error_cache.get_fix_success_rate("pattern1")

        assert success_rate == 0.5

    def test_cleanup_old_patterns(self, error_cache, cache_dir):
        """Test cleaning up old patterns."""
        # Create old pattern
        old_pattern = ErrorPattern(
            pattern_id="old_pattern",
            error_type="old",
            error_code="E001",
            message_pattern="Old error",
        )
        old_pattern.last_seen = time.time() - (31 * 24 * 3600)  # 31 days ago

        error_cache.add_pattern(old_pattern)

        cleaned = error_cache.cleanup_old_patterns(days=30)

        assert cleaned == 1
        assert error_cache.get_pattern("old_pattern") is None

    def test_get_cache_stats(self, error_cache):
        """Test getting cache statistics."""
        pattern = ErrorPattern(
            pattern_id="test_pattern",
            error_type="test",
            error_code="E001",
            message_pattern="Test error",
            auto_fixable=True,
        )
        error_cache.add_pattern(pattern)

        result = FixResult(
            fix_id="fix_1",
            pattern_id="test_pattern",
            success=True,
            files_affected=[],
            time_taken=1.0,
        )
        error_cache.add_fix_result(result)

        stats = error_cache.get_cache_stats()

        assert stats["total_patterns"] == 1
        assert stats["auto_fixable_patterns"] == 1
        assert stats["total_fix_attempts"] == 1
        assert "error_types" in stats


class TestIssue:
    """Test Issue dataclass."""

    def test_issue_creation(self):
        """Test creating Issue."""
        issue = Issue(
            id="issue_1",
            type="syntax_error",
            message="Syntax error detected",
            file_path="test.py",
            line_number=42,
            priority=Priority.HIGH,
            stage="fast",
            suggested_fix="Fix syntax",
            auto_fixable=True,
        )

        assert issue.id == "issue_1"
        assert issue.type == "syntax_error"
        assert issue.message == "Syntax error detected"
        assert issue.file_path == "test.py"
        assert issue.line_number == 42
        assert issue.priority == Priority.HIGH
        assert issue.auto_fixable is True

    def test_issue_defaults(self):
        """Test Issue with defaults."""
        issue = Issue(
            id="issue_2",
            type="warning",
            message="Warning message",
            file_path="warn.py",
        )

        assert issue.line_number is None
        assert issue.priority == Priority.MEDIUM
        assert issue.stage == ""
        assert issue.suggested_fix is None
        assert issue.auto_fixable is False

    def test_issue_to_dict(self):
        """Test converting Issue to dict."""
        issue = Issue(
            id="issue_3",
            type="error",
            message="Error message",
            file_path="error.py",
            priority=Priority.CRITICAL,
        )

        data = issue.to_dict()

        assert isinstance(data, dict)
        assert data["id"] == "issue_3"
        assert data["type"] == "error"
        assert data["priority"] == Priority.CRITICAL


class TestSessionState:
    """Test SessionState with mocking."""

    @pytest.fixture
    def session_state(self):
        """Create SessionState instance."""
        return SessionState(
            session_id="test_session",
            start_time=time.time(),
        )

    def test_init(self, session_state):
        """Test SessionState initialization."""
        assert session_state.session_id == "test_session"
        assert session_state.start_time > 0
        assert session_state.stages == {}
        assert session_state.global_issues == []
        assert session_state.fixes_applied == []
        assert session_state.metadata == {}

    def test_add_stage_result(self, session_state):
        """Test adding a stage result to session."""
        stage_result = StageResult(
            stage="fast",
            status=StageStatus.COMPLETED,
            start_time=time.time(),
            end_time=time.time() + 10,
        )

        session_state.stages["fast"] = stage_result

        assert "fast" in session_state.stages
        assert session_state.stages["fast"] == stage_result

    def test_add_global_issue(self, session_state):
        """Test adding a global issue."""
        issue = Issue(
            id="issue_1",
            type="error",
            message="Test error",
            file_path="test.py",
        )

        session_state.global_issues.append(issue)

        assert len(session_state.global_issues) == 1
        assert session_state.global_issues[0] == issue

    def test_set_metadata(self, session_state):
        """Test setting session metadata."""
        session_state.metadata["user"] = "test_user"
        session_state.metadata["project"] = "test_project"

        assert session_state.metadata["user"] == "test_user"
        assert session_state.metadata["project"] == "test_project"

    def test_to_dict(self, session_state):
        """Test converting session to dict."""
        issue = Issue(
            id="issue_1",
            type="error",
            message="Test error",
            file_path="test.py",
        )
        session_state.global_issues.append(issue)
        session_state.metadata["test"] = "value"

        data = session_state.to_dict()

        assert isinstance(data, dict)
        assert data["session_id"] == session_state.session_id
        assert "stages" in data
        assert "global_issues" in data
        assert "metadata" in data
        assert data["metadata"]["test"] == "value"


class TestStateManager:
    """Test StateManager with extensive mocking."""

    @pytest.fixture
    def state_manager(self, tmp_path):
        """Create StateManager instance."""
        return StateManager(state_dir=tmp_path / "state")

    def test_init(self, state_manager):
        """Test StateManager initialization."""
        assert state_manager.session_state is not None
        assert state_manager.session_state.session_id is not None
        assert state_manager.session_state.start_time > 0

    def test_start_stage(self, state_manager):
        """Test starting a new stage."""
        state_manager.start_stage("fast")

        assert state_manager.session_state.current_stage == "fast"
        assert "fast" in state_manager.session_state.stages
        assert state_manager.session_state.stages["fast"].status == StageStatus.RUNNING

    def test_complete_stage(self, state_manager):
        """Test completing a stage."""
        state_manager.start_stage("fast")

        issue = Issue(
            id="issue_1",
            type="error",
            message="Test error",
            file_path="test.py",
        )

        state_manager.complete_stage("fast", issues=[issue], fixes=["fix_1"])

        stage_result = state_manager.session_state.stages["fast"]
        assert stage_result.status == StageStatus.COMPLETED
        assert stage_result.end_time is not None
        assert len(stage_result.issues_found) == 1
        assert len(stage_result.fixes_applied) == 1

    def test_fail_stage(self, state_manager):
        """Test failing a stage."""
        state_manager.start_stage("comprehensive")

        state_manager.fail_stage("comprehensive", "Error occurred")

        stage_result = state_manager.session_state.stages["comprehensive"]
        assert stage_result.status == StageStatus.FAILED
        assert stage_result.error_message == "Error occurred"
        assert state_manager.session_state.current_stage is None

    def test_add_issue(self, state_manager):
        """Test adding an issue."""
        issue = Issue(
            id="global_issue",
            type="warning",
            message="Global warning",
            file_path="global.py",
        )

        state_manager.add_issue(issue)

        assert len(state_manager.session_state.global_issues) == 1
        assert state_manager.session_state.global_issues[0] == issue

    def test_remove_issue(self, state_manager):
        """Test removing an issue."""
        issue = Issue(
            id="removable_issue",
            type="error",
            message="Removable error",
            file_path="remove.py",
        )

        state_manager.add_issue(issue)
        success = state_manager.remove_issue("removable_issue")

        assert success is True
        assert len(state_manager.session_state.global_issues) == 0

    def test_get_issues_by_priority(self, state_manager):
        """Test filtering issues by priority."""
        high_issue = Issue(
            id="high_issue",
            type="error",
            message="High priority error",
            file_path="high.py",
            priority=Priority.HIGH,
        )
        low_issue = Issue(
            id="low_issue",
            type="warning",
            message="Low priority warning",
            file_path="low.py",
            priority=Priority.LOW,
        )

        state_manager.add_issue(high_issue)
        state_manager.add_issue(low_issue)

        high_issues = state_manager.get_issues_by_priority(Priority.HIGH)

        assert len(high_issues) == 1
        assert high_issues[0].priority == Priority.HIGH

    def test_get_session_summary(self, state_manager):
        """Test getting session summary."""
        state_manager.start_stage("fast")

        issue = Issue(
            id="summary_issue",
            type="error",
            message="Summary error",
            file_path="summary.py",
            priority=Priority.CRITICAL,
            auto_fixable=True,
        )

        state_manager.complete_stage("fast", issues=[issue], fixes=["fix_1"])

        summary = state_manager.get_session_summary()

        assert summary["session_id"] == state_manager.session_state.session_id
        assert summary["total_issues"] == 1
        assert summary["total_fixes"] == 1
        assert summary["auto_fixable_issues"] == 1
        assert "fast" in summary["stages"]

    def test_save_and_load_checkpoint(self, state_manager):
        """Test saving and loading checkpoints."""
        issue = Issue(
            id="checkpoint_issue",
            type="error",
            message="Checkpoint error",
            file_path="checkpoint.py",
        )

        state_manager.add_issue(issue)
        state_manager.save_checkpoint("test_checkpoint")

        # Reset session
        original_session_id = state_manager.session_state.session_id
        state_manager.reset_session()

        assert state_manager.session_state.session_id != original_session_id
        assert len(state_manager.session_state.global_issues) == 0

        # Load checkpoint
        success = state_manager.load_checkpoint("test_checkpoint")

        assert success is True
        assert state_manager.session_state.session_id == original_session_id
        assert len(state_manager.session_state.global_issues) == 1

    def test_list_checkpoints(self, state_manager):
        """Test listing checkpoints."""
        state_manager.save_checkpoint("checkpoint_1")
        state_manager.save_checkpoint("checkpoint_2")

        checkpoints = state_manager.list_checkpoints()

        assert len(checkpoints) >= 2
        checkpoint_names = [cp["name"] for cp in checkpoints]
        assert "checkpoint_1" in checkpoint_names
        assert "checkpoint_2" in checkpoint_names


class TestMCPIntegration:
    """Integration tests for MCP components."""

    def test_session_state_workflow(self):
        """Test complete session state workflow."""
        manager = StateManager()

        # Create session
        manager.create_session()
        session = manager.get_current_session()

        # Add issues
        issue1 = Issue(
            issue_type="test_error",
            file_path="/test/file1.py",
            line_number=10,
            message="Test error 1",
            priority=Priority.HIGH,
        )
        issue2 = Issue(
            issue_type="lint_warning",
            file_path="/test/file2.py",
            line_number=20,
            message="Test warning 2",
            priority=Priority.LOW,
        )

        session.add_issue(issue1)
        session.add_issue(issue2)

        # Verify final state
        assert len(session.issues) == 2
        assert session.issues[0].message == "Test error 1"
        assert session.issues[1].message == "Test warning 2"

    @pytest.mark.asyncio
    async def test_mcp_main_function(self):
        """Test the main MCP server function."""
        with patch("crackerjack.mcp.server.Server") as mock_server_class:
            with patch("crackerjack.mcp.server.stdio_server") as mock_stdio:
                mock_server = Mock()
                mock_server_class.return_value = mock_server
                mock_stdio.return_value = AsyncMock()

                # Mock the async context manager
                async def mock_serve():
                    pass

                mock_stdio.return_value.__aenter__ = AsyncMock(return_value=mock_serve)
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

                # This would normally run the server
                # We'll just test that it can be called without error
                try:
                    await asyncio.wait_for(mcp_main(), timeout=0.1)
                except TimeoutError:
                    # Expected - the server would run indefinitely
                    pass

                # Verify server setup was called
                mock_server_class.assert_called_once()
