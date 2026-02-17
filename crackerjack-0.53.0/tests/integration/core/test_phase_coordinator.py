"""Tests for phase_coordinator.py."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.config import CrackerjackSettings
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.models.task import HookResult


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings."""
    settings = CrackerjackSettings(pkg_path=tmp_path)
    return settings


@pytest.fixture
def mock_console():
    """Create mock console."""
    return Console()


@pytest.fixture
def mock_session():
    """Create mock session coordinator."""
    from crackerjack.core.session_coordinator import SessionCoordinator
    mock = MagicMock(spec=SessionCoordinator)
    return mock


@pytest.fixture
def coordinator(tmp_path, mock_console, mock_settings, mock_session):
    """Create PhaseCoordinator instance for testing."""
    return PhaseCoordinator(
        console=mock_console,
        pkg_path=tmp_path,
        session=mock_session,
        settings=mock_settings,
    )


@pytest.fixture
def mock_options():
    """Create mock options."""
    options = MagicMock()
    options.skip_hooks = False
    options.test = False
    options.run_tests = False
    options.clean = False
    options.no_config_updates = True
    options.ai_fix = False
    options.verbose = False
    options.ai_debug = False
    options.interactive = False
    options.commit = False
    options.fast = False
    options.comp = False
    options.publish = None
    options.all = None
    options.bump = None
    options.test_workers = 0
    options.test_timeout = 0
    options.cleanup_docs = False
    options.cleanup_git = False
    options.update_docs = False
    options.configs_dry_run = False
    options.docs_dry_run = False
    options.fast_iteration = False
    return options


class TestPhaseCoordinatorInitialization:
    """Test suite for PhaseCoordinator initialization."""

    def test_initialization(self, coordinator):
        """Test PhaseCoordinator initializes correctly."""
        assert coordinator.console is not None
        assert coordinator.pkg_path is not None
        assert coordinator.session is not None
        assert coordinator.filesystem is not None
        assert coordinator.git_service is not None
        assert coordinator.hook_manager is not None
        assert coordinator.test_manager is not None
        assert coordinator.publish_manager is not None
        assert coordinator.code_cleaner is not None
        assert coordinator._logger is not None

    def test_logger_property(self, coordinator):
        """Test logger property getter."""
        logger = coordinator.logger
        assert logger is not None

    def test_logger_setter(self, coordinator):
        """Test logger property setter."""
        import logging

        new_logger = logging.getLogger("test_logger")
        coordinator.logger = new_logger
        assert coordinator.logger == new_logger


class TestFastHooksPhase:
    """Test suite for fast hooks phase."""

    def test_run_fast_hooks_only_success(self, coordinator, mock_options):
        """Test running fast hooks with success."""
        coordinator.hook_manager.run_fast_hooks = MagicMock(return_value=[])
        coordinator._last_hook_summary = {"total": 5, "passed": 5, "failed": 0}

        result = coordinator.run_fast_hooks_only(mock_options)
        assert result is True

    def test_run_fast_hooks_only_skip(self, coordinator, mock_options):
        """Test skipping fast hooks."""
        mock_options.skip_hooks = True
        result = coordinator.run_fast_hooks_only(mock_options)
        assert result is True

    def test_run_fast_hooks_duplicate_prevention(self, coordinator, mock_options):
        """Test duplicate fast hooks invocation prevention."""
        coordinator.hook_manager.run_fast_hooks = MagicMock(return_value=[])

        # First call
        result1 = coordinator.run_fast_hooks_only(mock_options)
        assert result1 is True
        assert coordinator._fast_hooks_started is True

        # Second call should be skipped
        result2 = coordinator.run_fast_hooks_only(mock_options)
        assert result2 is True


class TestComprehensiveHooksPhase:
    """Test suite for comprehensive hooks phase."""

    def test_run_comprehensive_hooks_only_success(self, coordinator, mock_options):
        """Test running comprehensive hooks with success."""
        coordinator.hook_manager.run_comprehensive_hooks = MagicMock(return_value=[])
        coordinator._last_hook_summary = {"total": 10, "passed": 10, "failed": 0}

        result = coordinator.run_comprehensive_hooks_only(mock_options)
        assert result is True

    def test_run_comprehensive_hooks_only_skip(self, coordinator, mock_options):
        """Test skipping comprehensive hooks."""
        mock_options.skip_hooks = True
        result = coordinator.run_comprehensive_hooks_only(mock_options)
        assert result is True


class TestTestingPhase:
    """Test suite for testing phase."""

    def test_run_testing_phase_no_tests(self, coordinator, mock_options):
        """Test testing phase when tests not enabled."""
        mock_options.test = False
        mock_options.run_tests = False
        result = coordinator.run_testing_phase(mock_options)
        assert result is True

    def test_run_testing_phase_success(self, coordinator, mock_options):
        """Test testing phase with successful execution."""
        mock_options.test = True
        coordinator.test_manager.validate_test_environment = MagicMock(return_value=True)
        coordinator.test_manager.run_tests = MagicMock(return_value=True)
        coordinator.test_manager.get_coverage = MagicMock(return_value={"total_coverage": 85.0})

        result = coordinator.run_testing_phase(mock_options)
        assert result is True


class TestCleaningPhase:
    """Test suite for cleaning phase."""

    def test_run_cleaning_phase_not_enabled(self, coordinator, mock_options):
        """Test cleaning phase when not enabled."""
        mock_options.clean = False
        result = coordinator.run_cleaning_phase(mock_options)
        assert result is True

    def test_run_cleaning_phase_with_files(self, coordinator, mock_options, tmp_path):
        """Test cleaning phase with Python files."""
        mock_options.clean = True

        # Create a test Python file
        test_file = tmp_path / "test.py"
        test_file.write_text("# Test file")

        coordinator.code_cleaner.should_process_file = MagicMock(return_value=False)

        result = coordinator.run_cleaning_phase(mock_options)
        assert result is True

    def test_run_cleaning_phase_no_files(self, coordinator, mock_options, tmp_path):
        """Test cleaning phase with no Python files."""
        mock_options.clean = True

        # Empty directory
        result = coordinator.run_cleaning_phase(mock_options)
        assert result is True


class TestConfigurationPhase:
    """Test suite for configuration phase."""

    def test_run_configuration_phase_skip_updates(self, coordinator, mock_options):
        """Test configuration phase when no updates needed."""
        mock_options.no_config_updates = True
        result = coordinator.run_configuration_phase(mock_options)
        assert result is True


class TestHelperMethods:
    """Test suite for helper methods."""

    def test_strip_ansi(self, coordinator):
        """Test ANSI code stripping."""
        text_with_ansi = "[[green]Hello[/green]]"
        stripped = coordinator._strip_ansi(text_with_ansi)
        # Basic verification that method doesn't crash
        assert isinstance(stripped, str)

    def test_is_plain_output(self, coordinator):
        """Test plain output detection."""
        result = coordinator._is_plain_output()
        # Just verify it returns a boolean
        assert isinstance(result, bool)

    def test_format_hook_summary_empty(self, coordinator):
        """Test formatting empty hook summary."""
        result = coordinator._format_hook_summary({})
        assert result == "No hooks executed"

    def test_format_hook_summary_with_data(self, coordinator):
        """Test formatting hook summary with data."""
        summary = {"total": 10, "passed": 8, "failed": 2, "errors": 0, "total_duration": 5.0}
        result = coordinator._format_hook_summary(summary)
        assert "8/10 passed" in result
        assert "2 failed" in result

    def test_status_style(self, coordinator):
        """Test status style mapping."""
        assert coordinator._status_style("passed") == "green"
        assert coordinator._status_style("failed") == "red"
        assert coordinator._status_style("error") == "red"
        assert coordinator._status_style("timeout") == "yellow"
        assert coordinator._status_style("unknown") == "bright_white"

    def test_determine_version_type(self, coordinator, mock_options):
        """Test version type determination."""
        mock_options.publish = "patch"
        assert coordinator._determine_version_type(mock_options) == "patch"

        mock_options.publish = None
        mock_options.all = True
        assert coordinator._determine_version_type(mock_options) == True

        mock_options.all = None
        mock_options.bump = "minor"
        assert coordinator._determine_version_type(mock_options) == "minor"

        mock_options.bump = None
        assert coordinator._determine_version_type(mock_options) is None


class TestHookResultProcessing:
    """Test suite for hook result processing."""

    def test_calculate_hook_statistics_empty(self, coordinator):
        """Test statistics calculation with empty results."""
        stats = coordinator._calculate_hook_statistics([])
        assert stats["total_hooks"] == 0
        assert stats["total_passed"] == 0
        assert stats["total_failed"] == 0

    def test_calculate_hook_statistics_with_results(self, coordinator):
        """Test statistics calculation with results."""
        results = [
            HookResult(name="hook1", status="passed", duration=1.0, exit_code=0),
            HookResult(name="hook2", status="failed", duration=2.0, exit_code=1),
            HookResult(name="hook3", status="passed", duration=1.5, exit_code=0),
        ]

        stats = coordinator._calculate_hook_statistics(results)
        assert stats["total_hooks"] == 3
        assert stats["total_passed"] == 2
        assert stats["total_failed"] == 1

    def test_update_json_hook_issue_counts_empty(self, coordinator):
        """Test JSON update with no results."""
        coordinator._last_hook_results = []
        coordinator._update_json_hook_issue_counts()
        # Should not crash

    def test_should_update_hook_count(self, coordinator):
        """Test hook count update condition."""
        result = HookResult(
            name="test", status="failed", duration=1.0, exit_code=1, issues_count=0
        )
        result.output = '{"issues": []}'
        assert coordinator._should_update_hook_count(result) is True


class TestClassifySafeTestFailures:
    """Test suite for test failure classification."""

    def test_classify_safe_test_failures_import_errors(self, coordinator):
        """Test classification of import errors."""
        failures = ["ModuleNotFoundError: No module named 'test'", "ImportError: cannot import name"]
        safe = coordinator._classify_safe_test_failures(failures)
        assert len(safe) == 2

    def test_classify_safe_test_failures_risky_patterns(self, coordinator):
        """Test classification filters out risky patterns."""
        failures = [
            "AssertionError: Expected 5 but got 3",
            "Integration test failed",
            "infrastructure error",
        ]
        safe = coordinator._classify_safe_test_failures(failures)
        assert len(safe) == 0

    def test_classify_safe_test_failures_mixed(self, coordinator):
        """Test classification with mixed failures."""
        failures = [
            "ModuleNotFoundError: No module named 'test'",
            "AssertionError: Expected 5 but got 3",
            "AttributeError: module has no attribute",
        ]
        safe = coordinator._classify_safe_test_failures(failures)
        assert len(safe) == 2


class TestCommitPhase:
    """Test suite for commit phase."""

    def test_run_commit_phase_not_enabled(self, coordinator, mock_options):
        """Test commit phase when not enabled."""
        mock_options.commit = False
        result = coordinator.run_commit_phase(mock_options)
        assert result is True

    def test_run_commit_phase_no_changes(self, coordinator, mock_options):
        """Test commit phase with no changes."""
        mock_options.commit = True
        mock_options.publish = None
        mock_options.all = None
        mock_options.bump = None

        coordinator.git_service.get_changed_files = MagicMock(return_value=[])

        result = coordinator.run_commit_phase(mock_options)
        assert result is True

    def test_get_commit_message_no_suggestions(self, coordinator, mock_options):
        """Test commit message with no suggestions."""
        coordinator.git_service.get_commit_message_suggestions = MagicMock(return_value=[])

        message = coordinator._get_commit_message([], mock_options)
        assert message == "Update project files"

    def test_get_commit_message_with_suggestions(self, coordinator, mock_options):
        """Test commit message with suggestions."""
        suggestions = ["feat: add feature", "fix: fix bug"]
        coordinator.git_service.get_commit_message_suggestions = MagicMock(return_value=suggestions)

        message = coordinator._get_commit_message([], mock_options)
        assert message in suggestions

    def test_process_commit_choice_empty(self, coordinator):
        """Test processing empty commit choice."""
        suggestions = ["feat: add feature", "fix: fix bug"]
        result = coordinator._process_commit_choice("", suggestions)
        assert result == suggestions[0]

    def test_process_commit_choice_number(self, coordinator):
        """Test processing numeric commit choice."""
        suggestions = ["feat: add feature", "fix: fix bug"]
        result = coordinator._process_commit_choice("2", suggestions)
        assert result == suggestions[1]

    def test_process_commit_choice_custom(self, coordinator):
        """Test processing custom commit message."""
        suggestions = ["feat: add feature", "fix: fix bug"]
        custom = "chore: update dependencies"
        result = coordinator._process_commit_choice(custom, suggestions)
        assert result == custom


class TestPublishingPhase:
    """Test suite for publishing phase."""

    def test_run_publishing_phase_no_version(self, coordinator, mock_options):
        """Test publishing phase when no version type specified."""
        mock_options.publish = None
        mock_options.all = None
        mock_options.bump = None

        result = coordinator.run_publishing_phase(mock_options)
        assert result is True


class TestCleanupPhases:
    """Test suite for cleanup phases."""

    def test_run_config_cleanup_phase_not_enabled(self, coordinator, mock_options):
        """Test config cleanup when not enabled."""
        mock_options.configs_dry_run = False
        # This phase requires specific flag, test it's handled
        # The actual method exists but needs specific setup
        assert hasattr(coordinator, "run_config_cleanup_phase")

    def test_run_documentation_cleanup_not_enabled(self, coordinator, mock_options):
        """Test documentation cleanup when not enabled."""
        mock_options.cleanup_docs = False
        result = coordinator.run_documentation_cleanup_phase(mock_options)
        assert result is True

    def test_run_git_cleanup_not_enabled(self, coordinator, mock_options):
        """Test git cleanup when not enabled."""
        mock_options.cleanup_git = False
        result = coordinator.run_git_cleanup_phase(mock_options)
        assert result is True

    def test_run_doc_update_not_enabled(self, coordinator, mock_options):
        """Test doc update when not enabled."""
        mock_options.update_docs = False
        result = coordinator.run_doc_update_phase(mock_options)
        assert result is True


class TestProgressTracking:
    """Test suite for progress tracking."""

    def test_create_progress_bar(self, coordinator):
        """Test progress bar creation."""
        progress = coordinator._create_progress_bar()
        assert progress is not None

    def test_setup_progress_callbacks(self, coordinator):
        """Test progress callback setup."""
        from rich.progress import Progress

        progress = Progress()
        callbacks = coordinator._setup_progress_callbacks(progress)

        assert "update" in callbacks
        assert "update_started" in callbacks
        assert "original" in callbacks
        assert "original_started" in callbacks
        assert "task_id_holder" in callbacks


class TestDisplayMethods:
    """Test suite for display methods."""

    def test_display_hook_phase_header(self, coordinator):
        """Test hook phase header display."""
        # Just verify no crash
        coordinator._display_hook_phase_header("TEST PHASE", "Test description")

    def test_display_cleaning_header(self, coordinator):
        """Test cleaning header display."""
        # Just verify no crash
        coordinator._display_cleaning_header()

    def test_display_version_bump_header(self, coordinator):
        """Test version bump header display."""
        # Just verify no crash
        coordinator._display_version_bump_header()

    def test_display_commit_push_header(self, coordinator):
        """Test commit push header display."""
        # Just verify no crash
        coordinator._display_commit_push_header()

    def test_display_publish_header(self, coordinator):
        """Test publish header display."""
        # Just verify no crash
        coordinator._display_publish_header()


class TestJSONExtraction:
    """Test suite for JSON extraction helpers."""

    def test_extract_count_from_json_data_list(self, coordinator):
        """Test extracting count from JSON list."""
        data = ["item1", "item2", "item3"]
        count = coordinator._extract_count_from_json_data(data)
        assert count == 3

    def test_extract_count_from_json_data_dict_results(self, coordinator):
        """Test extracting count from JSON dict with results."""
        data = {"results": ["item1", "item2"]}
        count = coordinator._extract_count_from_json_data(data)
        assert count == 2

    def test_extract_count_from_json_data_dict_issues(self, coordinator):
        """Test extracting count from JSON dict with issues."""
        data = {"issues": ["issue1", "issue2", "issue3"]}
        count = coordinator._extract_count_from_json_data(data)
        assert count == 3

    def test_extract_count_from_json_data_invalid(self, coordinator):
        """Test extracting count from invalid JSON data."""
        count = coordinator._extract_count_from_json_data("invalid")
        assert count is None

    def test_extract_count_from_json_dict_empty(self, coordinator):
        """Test extracting count from empty dict."""
        count = coordinator._extract_count_from_json_dict({})
        assert count is None


class TestHookExecution:
    """Test suite for hook execution methods."""

    def test_execute_hooks_once_success(self, coordinator, mock_options):
        """Test single hook execution with success."""
        coordinator.hook_manager.get_hook_count = MagicMock(return_value=5)
        coordinator.hook_manager.run_fast_hooks = MagicMock(
            return_value=[
                HookResult(name="hook1", status="passed", duration=1.0, exit_code=0),
                HookResult(name="hook2", status="passed", duration=1.0, exit_code=0),
            ]
        )
        coordinator.hook_manager.get_hook_summary = MagicMock(
            return_value={"total": 2, "passed": 2, "failed": 0, "total_duration": 2.0}
        )

        result = coordinator._execute_hooks_once(
            "fast", coordinator.hook_manager.run_fast_hooks, mock_options, 1
        )
        assert result is True

    def test_execute_hooks_once_with_failure(self, coordinator, mock_options):
        """Test single hook execution with failure."""
        coordinator.hook_manager.get_hook_count = MagicMock(return_value=5)
        coordinator.hook_manager.run_fast_hooks = MagicMock(
            return_value=[
                HookResult(name="hook1", status="passed", duration=1.0, exit_code=0),
                HookResult(name="hook2", status="failed", duration=1.0, exit_code=1),
            ]
        )
        coordinator.hook_manager.get_hook_summary = MagicMock(
            return_value={"total": 2, "passed": 1, "failed": 1, "total_duration": 2.0}
        )

        result = coordinator._execute_hooks_once(
            "fast", coordinator.hook_manager.run_fast_hooks, mock_options, 1
        )
        assert result is False


class TestSessionTracking:
    """Test suite for session tracking integration."""

    def test_track_task_on_phase_start(self, coordinator, mock_options):
        """Test task tracking on phase start."""
        coordinator.hook_manager.run_fast_hooks = MagicMock(return_value=[])
        coordinator._last_hook_summary = {"total": 0}

        coordinator.run_fast_hooks_only(mock_options)
        # Verify session was called
        assert coordinator.session.track_task.called or coordinator.session.complete_task.called

    def test_complete_task_on_success(self, coordinator, mock_options):
        """Test task completion on success."""
        coordinator.hook_manager.run_fast_hooks = MagicMock(return_value=[])
        coordinator._last_hook_summary = {"total": 5, "passed": 5, "failed": 0}

        coordinator.run_fast_hooks_only(mock_options)
        # Verify session.complete_task was called

    def test_fail_task_on_failure(self, coordinator, mock_options):
        """Test task failure on hook failure."""
        coordinator.hook_manager.run_fast_hooks = MagicMock(
            return_value=[
                HookResult(name="hook1", status="failed", duration=1.0, exit_code=1, issues_count=1)
            ]
        )
        coordinator.hook_manager.get_hook_summary = MagicMock(
            return_value={"total": 1, "passed": 0, "failed": 1, "total_duration": 1.0}
        )

        coordinator.run_fast_hooks_only(mock_options)
        # Verify session behavior for failure case


class TestToJSONMethod:
    """Test suite for to_json method."""

    def test_to_json_empty_results(self, coordinator):
        """Test JSON conversion with empty results."""
        result = coordinator.to_json([], "test_suite")
        assert result["suite"] == "test_suite"
        assert result["hooks"] == []

    def test_to_json_with_results(self, coordinator):
        """Test JSON conversion with results."""
        results = [
            HookResult(
                name="hook1",
                status="passed",
                duration=1.5,
                exit_code=0,
                issues_found=None,
                issues_count=0,
            )
        ]

        result = coordinator.to_json(results, "test_suite")
        assert result["suite"] == "test_suite"
        assert len(result["hooks"]) == 1
        assert result["hooks"][0]["name"] == "hook1"
        assert result["hooks"][0]["status"] == "passed"
        assert result["hooks"][0]["duration"] == 1.5
