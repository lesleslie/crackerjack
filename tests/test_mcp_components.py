import pytest

from crackerjack.mcp.cache import ErrorCache, ErrorPattern, FixResult
from crackerjack.mcp.state import (
    Issue,
    Priority,
    StageStatus,
    StateManager,
)


class TestErrorPattern:
    def test_error_pattern_creation(self) -> None:
        pattern = ErrorPattern(
            pattern_id="test_pattern_1",
            error_type="syntax_error",
            error_code="E999",
            message_pattern="SyntaxError",
            file_pattern=" * .py",
            common_fixes=["Check syntax"],
        )

        assert pattern.pattern_id == "test_pattern_1"
        assert pattern.error_type == "syntax_error"
        assert pattern.error_code == "E999"
        assert pattern.message_pattern == "SyntaxError"
        assert pattern.file_pattern == " * .py"
        assert pattern.common_fixes == ["Check syntax"]

    def test_error_pattern_defaults(self) -> None:
        pattern = ErrorPattern(
            pattern_id="test_pattern_2",
            error_type="error",
            error_code="E001",
            message_pattern="Error occurred",
        )

        assert pattern.auto_fixable is False
        assert pattern.frequency == 1
        assert pattern.common_fixes == []

    def test_error_pattern_post_init(self) -> None:
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
    def test_fix_result_creation(self) -> None:
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

    def test_fix_result_failure(self) -> None:
        result = FixResult(
            fix_id="fix_456",
            pattern_id="test",
            success=False,
            files_affected=[],
            time_taken=0.5,
            error_message="Fix failed",
        )

        assert result.success is False
        assert result.error_message == "Fix failed"


class TestErrorCache:
    @pytest.fixture
    def cache_dir(self, tmp_path):
        return tmp_path / "cache"

    @pytest.fixture
    def error_cache(self, cache_dir):
        return ErrorCache(cache_dir)

    def test_init(self, error_cache, cache_dir) -> None:
        assert error_cache.cache_dir == cache_dir
        assert error_cache.patterns_file == cache_dir / "error_patterns.json"
        assert error_cache.fixes_file == cache_dir / "fix_results.json"

    def test_add_pattern(self, error_cache) -> None:
        pattern = ErrorPattern(
            pattern_id="new_error_1",
            error_type="new_error",
            error_code="E002",
            message_pattern="New error",
            file_pattern=" * .py",
        )

        error_cache.add_pattern(pattern)
        retrieved = error_cache.get_pattern("new_error_1")

        assert retrieved == pattern

    def test_find_patterns_by_type(self, error_cache) -> None:
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

        syntax_patterns = error_cache.find_patterns_by_type("syntax")

        assert len(syntax_patterns) == 1
        assert syntax_patterns[0].error_type == "syntax"

    def test_add_fix_result(self, error_cache) -> None:
        pattern = ErrorPattern(
            pattern_id="test_pattern",
            error_type="test",
            error_code="E001",
            message_pattern="Test error",
        )
        error_cache.add_pattern(pattern)

        result = FixResult(
            fix_id="fix_123",
            pattern_id="test_pattern",
            success=True,
            files_affected=["file1.py"],
            time_taken=1.0,
        )

        error_cache.add_fix_result(result)

        success_rate = error_cache.get_fix_success_rate("test_pattern")
        assert success_rate == 1.0

    def test_get_cache_stats(self, error_cache) -> None:
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
    def test_issue_creation(self) -> None:
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

    def test_issue_defaults(self) -> None:
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


class TestStateManager:
    @pytest.fixture
    def state_manager(self, tmp_path):
        return StateManager(state_dir=tmp_path / "state")

    def test_init(self, state_manager) -> None:
        assert state_manager.session_state is not None
        assert state_manager.session_state.session_id is not None
        assert state_manager.session_state.start_time > 0

    def test_start_complete_stage(self, state_manager) -> None:
        state_manager.start_stage("fast")

        assert state_manager.session_state.current_stage == "fast"
        assert "fast" in state_manager.session_state.stages
        assert state_manager.session_state.stages["fast"].status == StageStatus.RUNNING

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

    def test_fail_stage(self, state_manager) -> None:
        state_manager.start_stage("comprehensive")

        state_manager.fail_stage("comprehensive", "Error occurred")

        stage_result = state_manager.session_state.stages["comprehensive"]
        assert stage_result.status == StageStatus.FAILED
        assert stage_result.error_message == "Error occurred"
        assert state_manager.session_state.current_stage is None

    def test_issue_management(self, state_manager) -> None:
        issue = Issue(
            id="removable_issue",
            type="error",
            message="Removable error",
            file_path="remove.py",
            priority=Priority.HIGH,
        )

        state_manager.add_issue(issue)
        assert len(state_manager.session_state.global_issues) == 1

        high_issues = state_manager.get_issues_by_priority(Priority.HIGH)
        assert len(high_issues) == 1
        assert high_issues[0].priority == Priority.HIGH

        success = state_manager.remove_issue("removable_issue")
        assert success is True
        assert len(state_manager.session_state.global_issues) == 0

    def test_session_summary(self, state_manager) -> None:
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

    def test_checkpoint_functionality(self, state_manager) -> None:
        issue = Issue(
            id="checkpoint_issue",
            type="error",
            message="Checkpoint error",
            file_path="checkpoint.py",
        )

        state_manager.add_issue(issue)
        original_session_id = state_manager.session_state.session_id

        state_manager.save_checkpoint("test_checkpoint")

        state_manager.reset_session()
        assert state_manager.session_state.session_id != original_session_id
        assert len(state_manager.session_state.global_issues) == 0

        success = state_manager.load_checkpoint("test_checkpoint")
        assert success is True
        assert state_manager.session_state.session_id == original_session_id
        assert len(state_manager.session_state.global_issues) == 1

    def test_list_checkpoints(self, state_manager) -> None:
        state_manager.save_checkpoint("checkpoint_1")
        state_manager.save_checkpoint("checkpoint_2")

        checkpoints = state_manager.list_checkpoints()

        assert len(checkpoints) >= 2
        checkpoint_names = [cp["name"] for cp in checkpoints]
        assert "checkpoint_1" in checkpoint_names
        assert "checkpoint_2" in checkpoint_names


class TestMCPIntegration:
    def test_error_cache_state_integration(self, tmp_path) -> None:
        cache_dir = tmp_path / "cache"
        state_dir = tmp_path / "state"

        cache = ErrorCache(cache_dir)
        state_manager = StateManager(state_dir)

        pattern = ErrorPattern(
            pattern_id="integration_test",
            error_type="syntax",
            error_code="E999",
            message_pattern="SyntaxError: test",
        )
        cache.add_pattern(pattern)

        issue = Issue(
            id="syntax_issue_1",
            type="syntax",
            message="SyntaxError: test",
            file_path="test.py",
            priority=Priority.HIGH,
            auto_fixable=True,
        )
        state_manager.add_issue(issue)

        cached_pattern = cache.get_pattern("integration_test")
        assert cached_pattern is not None

        high_priority_issues = state_manager.get_issues_by_priority(Priority.HIGH)
        assert len(high_priority_issues) == 1
        assert high_priority_issues[0].message == "SyntaxError: test"

    def test_error_pattern_creation_from_output(self) -> None:
        cache = ErrorCache()

        ruff_output = "src / test.py: 10: 5: E999 SyntaxError: invalid syntax"
        pattern = cache.create_pattern_from_error(ruff_output, "ruff")

        assert pattern is not None
        assert pattern.error_type == "ruff"
        assert "SyntaxError" in pattern.message_pattern

    def test_persistence_workflow(self, tmp_path) -> None:
        state_dir = tmp_path / "state"
        cache_dir = tmp_path / "cache"

        state_manager = StateManager(state_dir=state_dir)
        error_cache = ErrorCache(cache_dir=cache_dir)

        state_manager.start_stage("fast")

        pattern = ErrorPattern(
            pattern_id="workflow_test",
            error_type="import",
            error_code="E401",
            message_pattern="ImportError: module not found",
        )
        error_cache.add_pattern(pattern)

        issue = Issue(
            id="import_issue",
            type="import",
            message="ImportError: module not found",
            file_path="src / main.py",
            priority=Priority.MEDIUM,
        )

        state_manager.complete_stage("fast", issues=[issue], fixes=["added import"])
        state_manager.save_checkpoint("workflow_checkpoint")

        assert (state_dir / "current_session.json").exists()
        assert (cache_dir / "error_patterns.json").exists()

        new_state_manager = StateManager(state_dir=state_dir)
        new_error_cache = ErrorCache(cache_dir=cache_dir)

        success = new_state_manager.load_checkpoint("workflow_checkpoint")
        assert success is True

        summary = new_state_manager.get_session_summary()
        assert summary["total_issues"] == 1
        assert summary["total_fixes"] == 1

        restored_pattern = new_error_cache.get_pattern("workflow_test")
        assert restored_pattern is not None
        assert restored_pattern.error_type == "import"
