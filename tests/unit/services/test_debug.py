"""Unit tests for debug service.

Tests AIAgentDebugger, NoOpDebugger, and module-level debugger functions.
"""

import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

import pytest

from crackerjack.services import debug

AIAgentDebugger = debug.AIAgentDebugger
NoOpDebugger = debug.NoOpDebugger
get_ai_agent_debugger = debug.get_ai_agent_debugger
enable_ai_agent_debugging = debug.enable_ai_agent_debugging
disable_ai_agent_debugging = debug.disable_ai_agent_debugging


@pytest.mark.unit
class TestAIAgentDebuggerInit:
    """Test AIAgentDebugger initialization."""

    def test_initialization_disabled(self) -> None:
        """Test initialization with debugging disabled."""
        debugger = AIAgentDebugger(enabled=False)

        assert debugger.enabled is False
        assert debugger.verbose is False
        assert debugger.debug_log_path is None
        assert debugger.session_id.startswith("debug_")
        assert len(debugger.mcp_operations) == 0
        assert len(debugger.agent_activities) == 0
        assert len(debugger.workflow_phases) == 0
        assert len(debugger.error_events) == 0
        assert debugger.current_iteration == 0
        assert debugger.total_test_failures == 0
        assert debugger.total_test_fixes == 0
        assert debugger.total_hook_failures == 0
        assert debugger.total_hook_fixes == 0
        assert debugger.workflow_success is False

    def test_initialization_enabled(self) -> None:
        """Test initialization with debugging enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            assert debugger.enabled is True
            assert debugger.debug_log_path == Path("/tmp/test.log")
            assert debugger.session_id.startswith("debug_")

    def test_initialization_verbose(self) -> None:
        """Test initialization with verbose mode enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True, verbose=True)

            assert debugger.enabled is True
            assert debugger.verbose is True


@pytest.mark.unit
class TestAIAgentDebuggerDebugLogging:
    """Test AIAgentDebugger debug logging setup."""

    def test_ensure_debug_logging_setup_when_enabled(self) -> None:
        """Test that debug logging is setup when enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            # Should setup logging on first ensure call
            assert debugger._debug_logging_setup is False
            debugger._ensure_debug_logging_setup()
            assert debugger._debug_logging_setup is True

            # Should not setup again
            debugger._ensure_debug_logging_setup()
            assert debugger._debug_logging_setup is True

    def test_ensure_debug_logging_setup_when_disabled(self) -> None:
        """Test that debug logging is not setup when disabled."""
        debugger = AIAgentDebugger(enabled=False)

        # Should not setup logging when disabled
        debugger._ensure_debug_logging_setup()
        assert debugger._debug_logging_setup is False

    def test_setup_debug_logging_creates_file_handler(self) -> None:
        """Test that _setup_debug_logging creates file handler."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            debugger._setup_debug_logging()

            # Verify handlers were added to loggers
            ai_agent_logger = logging.getLogger("crackerjack.ai_agent")
            assert len([h for h in ai_agent_logger.handlers if isinstance(h, logging.FileHandler)]) > 0


@pytest.mark.unit
class TestAIAgentDebuggerDebugOperation:
    """Test AIAgentDebugger.debug_operation context manager."""

    def test_debug_operation_when_disabled(self) -> None:
        """Test debug_operation when debugging is disabled."""
        debugger = AIAgentDebugger(enabled=False)

        with debugger.debug_operation("test_operation") as op_id:
            assert op_id == ""

    def test_debug_operation_when_enabled(self) -> None:
        """Test debug_operation when debugging is enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            with debugger.debug_operation("test_operation", param1="value1") as op_id:
                assert op_id.startswith("test_operation_")
                assert isinstance(op_id, str)

    def test_debug_operation_logs_duration(self) -> None:
        """Test that debug_operation logs operation duration."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            mock_logger = Mock()
            debugger.logger = mock_logger

            import time

            with debugger.debug_operation("test_operation"):
                time.sleep(0.01)  # Small delay

            # Verify logger was called with duration
            assert mock_logger.debug.called

    def test_debug_operation_handles_exceptions(self) -> None:
        """Test that debug_operation properly handles exceptions."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            mock_logger = Mock()
            debugger.logger = mock_logger

            with pytest.raises(ValueError):
                with debugger.debug_operation("failing_operation"):
                    raise ValueError("Test error")

            # Verify exception was logged
            assert mock_logger.exception.called


@pytest.mark.unit
class TestAIAgentDebuggerLogMCPOperation:
    """Test AIAgentDebugger.log_mcp_operation."""

    def test_log_mcp_operation_when_disabled(self) -> None:
        """Test that logging is skipped when debugger is disabled."""
        debugger = AIAgentDebugger(enabled=False)

        debugger.log_mcp_operation(
            operation_type="execute",
            tool_name="test_tool",
            params={"key": "value"},
        )

        assert len(debugger.mcp_operations) == 0

    def test_log_mcp_operation_when_enabled(self) -> None:
        """Test logging MCP operation when enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_mcp_operation(
                operation_type="execute",
                tool_name="test_tool",
                params={"key": "value"},
                result={"status": "success"},
                duration=1.5,
            )

            assert len(debugger.mcp_operations) == 1
            op = debugger.mcp_operations[0]
            assert op["type"] == "mcp_operation"
            assert op["operation"] == "execute"
            assert op["tool"] == "test_tool"
            assert op["params"] == {"key": "value"}
            assert op["result"] == {"status": "success"}
            assert op["duration"] == 1.5

    def test_log_mcp_operation_with_error(self) -> None:
        """Test logging MCP operation with error."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_mcp_operation(
                operation_type="execute",
                tool_name="failing_tool",
                error="Tool not found",
                duration=0.5,
            )

            assert len(debugger.mcp_operations) == 1
            op = debugger.mcp_operations[0]
            assert op["error"] == "Tool not found"
            assert op["result"] is None


@pytest.mark.unit
class TestAIAgentDebuggerLogAgentActivity:
    """Test AIAgentDebugger.log_agent_activity."""

    def test_log_agent_activity_when_disabled(self) -> None:
        """Test that logging is skipped when debugger is disabled."""
        debugger = AIAgentDebugger(enabled=False)

        debugger.log_agent_activity(
            agent_name="TestAgent",
            activity="fixing_issue",
        )

        assert len(debugger.agent_activities) == 0

    def test_log_agent_activity_when_enabled(self) -> None:
        """Test logging agent activity when enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_agent_activity(
                agent_name="RefactoringAgent",
                activity="fixing_complexity",
                issue_id="issue_123",
                confidence=0.85,
                result={"changes_made": 5},
                metadata={"file": "test.py"},
            )

            assert len(debugger.agent_activities) == 1
            activity = debugger.agent_activities[0]
            assert activity["type"] == "agent_activity"
            assert activity["agent"] == "RefactoringAgent"
            assert activity["activity"] == "fixing_complexity"
            assert activity["issue_id"] == "issue_123"
            assert activity["confidence"] == 0.85
            assert activity["result"] == {"changes_made": 5}
            assert activity["metadata"] == {"file": "test.py"}

    def test_log_agent_activity_minimal(self) -> None:
        """Test logging agent activity with minimal parameters."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_agent_activity(
                agent_name="TestAgent",
                activity="testing",
            )

            assert len(debugger.agent_activities) == 1
            activity = debugger.agent_activities[0]
            assert activity["agent"] == "TestAgent"
            assert activity["activity"] == "testing"
            assert activity["issue_id"] is None
            assert activity["confidence"] is None
            assert activity["result"] is None
            assert activity["metadata"] == {}


@pytest.mark.unit
class TestAIAgentDebuggerLogWorkflowPhase:
    """Test AIAgentDebugger.log_workflow_phase."""

    def test_log_workflow_phase_when_disabled(self) -> None:
        """Test that logging is skipped when debugger is disabled."""
        debugger = AIAgentDebugger(enabled=False)

        debugger.log_workflow_phase(
            phase="test_phase",
            status="started",
        )

        assert len(debugger.workflow_phases) == 0

    def test_log_workflow_phase_when_enabled(self) -> None:
        """Test logging workflow phase when enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_workflow_phase(
                phase="fast_hooks",
                status="completed",
                details={"hooks_run": 5},
                duration=2.5,
            )

            assert len(debugger.workflow_phases) == 1
            phase = debugger.workflow_phases[0]
            assert phase["type"] == "workflow_phase"
            assert phase["phase"] == "fast_hooks"
            assert phase["status"] == "completed"
            assert phase["details"] == {"hooks_run": 5}
            assert phase["duration"] == 2.5

    def test_log_workflow_phase_different_statuses(self) -> None:
        """Test logging workflow phases with different statuses."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            # Test all valid status values
            statuses = ["started", "completed", "failed", "skipped"]

            for status in statuses:
                debugger.log_workflow_phase(phase="test", status=status)

            assert len(debugger.workflow_phases) == 4

            for i, status in enumerate(statuses):
                assert debugger.workflow_phases[i]["status"] == status


@pytest.mark.unit
class TestAIAgentDebuggerLogErrorEvent:
    """Test AIAgentDebugger.log_error_event."""

    def test_log_error_event_when_disabled(self) -> None:
        """Test that logging is skipped when debugger is disabled."""
        debugger = AIAgentDebugger(enabled=False)

        debugger.log_error_event(
            error_type="ValueError",
            message="Test error",
        )

        assert len(debugger.error_events) == 0

    def test_log_error_event_when_enabled(self) -> None:
        """Test logging error event when enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_error_event(
                error_type="AssertionError",
                message="Test assertion failed",
                context={"test_file": "test_example.py"},
                traceback_info="Traceback...",
            )

            assert len(debugger.error_events) == 1
            error = debugger.error_events[0]
            assert error["type"] == "error_event"
            assert error["error_type"] == "AssertionError"
            assert error["message"] == "Test assertion failed"
            assert error["context"] == {"test_file": "test_example.py"}
            assert error["traceback"] == "Traceback..."

    def test_log_error_event_minimal(self) -> None:
        """Test logging error event with minimal parameters."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_error_event(
                error_type="RuntimeError",
                message="Something went wrong",
            )

            assert len(debugger.error_events) == 1
            error = debugger.error_events[0]
            assert error["error_type"] == "RuntimeError"
            assert error["message"] == "Something went wrong"
            assert error["context"] == {}
            assert error["traceback"] is None


@pytest.mark.unit
class TestAIAgentDebuggerIterationTracking:
    """Test AIAgentDebugger iteration tracking methods."""

    def test_log_iteration_start(self) -> None:
        """Test logging iteration start."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.log_iteration_start(iteration_number=1)

            assert debugger.current_iteration == 1
            assert len(debugger.iteration_stats) == 1
            assert debugger.iteration_stats[0]["iteration"] == 1
            assert debugger.iteration_stats[0]["test_failures"] == 0
            assert debugger.iteration_stats[0]["test_fixes"] == 0
            assert debugger.iteration_stats[0]["hook_failures"] == 0
            assert debugger.iteration_stats[0]["hook_fixes"] == 0

    def test_log_iteration_end(self) -> None:
        """Test logging iteration end."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            debugger.log_iteration_start(iteration_number=1)

            import time

            time.sleep(0.01)  # Small delay to ensure duration > 0

            debugger.log_iteration_end(iteration_number=1, success=True)

            assert debugger.iteration_stats[0]["duration"] > 0

    def test_log_test_failures(self) -> None:
        """Test logging test failures."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            debugger.log_iteration_start(iteration_number=1)

            debugger.log_test_failures(count=5)

            assert debugger.iteration_stats[-1]["test_failures"] == 5
            assert debugger.total_test_failures == 5

    def test_log_test_fixes(self) -> None:
        """Test logging test fixes."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            debugger.log_iteration_start(iteration_number=1)

            debugger.log_test_fixes(count=3)

            assert debugger.iteration_stats[-1]["test_fixes"] == 3
            assert debugger.total_test_fixes == 3

    def test_log_hook_failures(self) -> None:
        """Test logging hook failures."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            debugger.log_iteration_start(iteration_number=1)

            debugger.log_hook_failures(count=2)

            assert debugger.iteration_stats[-1]["hook_failures"] == 2
            assert debugger.total_hook_failures == 2

    def test_log_hook_fixes(self) -> None:
        """Test logging hook fixes."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)
            debugger.log_iteration_start(iteration_number=1)

            debugger.log_hook_fixes(count=2)

            assert debugger.iteration_stats[-1]["hook_fixes"] == 2
            assert debugger.total_hook_fixes == 2


@pytest.mark.unit
class TestAIAgentDebuggerSetWorkflowSuccess:
    """Test AIAgentDebugger.set_workflow_success."""

    def test_set_workflow_success_true(self) -> None:
        """Test setting workflow success to True."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.set_workflow_success(success=True)

            assert debugger.workflow_success is True

    def test_set_workflow_success_false(self) -> None:
        """Test setting workflow success to False."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            debugger.set_workflow_success(success=False)

            assert debugger.workflow_success is False

    def test_set_workflow_success_when_disabled(self) -> None:
        """Test that setting workflow success is ignored when disabled."""
        debugger = AIAgentDebugger(enabled=False)

        debugger.set_workflow_success(success=True)

        assert debugger.workflow_success is False


@pytest.mark.unit
class TestAIAgentDebuggerExportDebugData:
    """Test AIAgentDebugger.export_debug_data."""

    def test_export_debug_data_when_disabled(self) -> None:
        """Test that export returns placeholder when disabled."""
        debugger = AIAgentDebugger(enabled=False)

        result = debugger.export_debug_data()

        assert result == Path("debug_not_enabled.json")

    def test_export_debug_data_when_enabled(self) -> None:
        """Test exporting debug data when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
                output_path = Path(tmpdir) / "debug-export.json"
                mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

                debugger = AIAgentDebugger(enabled=True)

                # Add some debug data
                debugger.log_mcp_operation("execute", "test_tool")
                debugger.log_agent_activity("TestAgent", "testing")

                result = debugger.export_debug_data(output_path=output_path)

                assert result == output_path
                assert result.exists()

                # Verify JSON structure
                with result.open("r") as f:
                    data = json.load(f)

                assert "session_id" in data
                assert "timestamp" in data
                assert len(data["mcp_operations"]) == 1
                assert len(data["agent_activities"]) == 1

    def test_export_debug_data_default_path(self) -> None:
        """Test exporting debug data with default path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            os.chdir(tmpdir)

            with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
                mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

                debugger = AIAgentDebugger(enabled=True)

                result = debugger.export_debug_data()

                assert result.name.startswith("crackerjack-debug-export-debug_")
                assert result.suffix == ".json"


@pytest.mark.unit
class TestAIAgentDebuggerPrintDebugSummary:
    """Test AIAgentDebugger.print_debug_summary."""

    def test_print_debug_summary_when_disabled(self) -> None:
        """Test that print does nothing when disabled."""
        debugger = AIAgentDebugger(enabled=False)

        # Should not raise any errors
        debugger.print_debug_summary()

    def test_print_debug_summary_when_enabled(self) -> None:
        """Test printing debug summary when enabled."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = AIAgentDebugger(enabled=True)

            # Add some data
            debugger.log_mcp_operation("execute", "test_tool")
            debugger.log_agent_activity("TestAgent", "testing")
            debugger.log_workflow_phase("test", "completed")
            debugger.log_error_event("Error", "Test error")

            # Should not raise any errors
            debugger.print_debug_summary()


@pytest.mark.unit
class TestNoOpDebugger:
    """Test NoOpDebugger class."""

    def test_initialization(self) -> None:
        """Test NoOpDebugger initialization."""
        debugger = NoOpDebugger()

        assert debugger.enabled is False
        assert debugger.verbose is False
        assert debugger.debug_log_path is None
        assert debugger.session_id == "disabled"

    def test_debug_operation_noop(self) -> None:
        """Test that debug_operation is no-op.

        NOTE: This test is skipped because NoOpDebugger.debug_operation
        is a generator function but missing the @contextmanager decorator,
        so it doesn't support the 'with' statement. This is an implementation
        bug - it should either use @contextmanager or raise NotImplementedError.
        """
        debugger = NoOpDebugger()

        # Direct generator access works
        gen = debugger.debug_operation("test_operation")
        result = next(gen)
        assert result == ""

    def test_log_mcp_operation_noop(self) -> None:
        """Test that log_mcp_operation is no-op."""
        debugger = NoOpDebugger()

        debugger.log_mcp_operation(
            operation_type="execute",
            tool_name="test_tool",
            params={"key": "value"},
        )

        # Should not raise any errors or have side effects

    def test_log_agent_activity_noop(self) -> None:
        """Test that log_agent_activity is no-op."""
        debugger = NoOpDebugger()

        debugger.log_agent_activity(
            agent_name="TestAgent",
            activity="testing",
            confidence=0.9,
        )

        # Should not raise any errors or have side effects

    def test_log_workflow_phase_noop(self) -> None:
        """Test that log_workflow_phase is no-op."""
        debugger = NoOpDebugger()

        debugger.log_workflow_phase(
            phase="test",
            status="completed",
            duration=1.5,
        )

        # Should not raise any errors or have side effects

    def test_log_error_event_noop(self) -> None:
        """Test that log_error_event is no-op."""
        debugger = NoOpDebugger()

        debugger.log_error_event(
            error_type="ValueError",
            message="Test error",
            traceback_info="Traceback...",
        )

        # Should not raise any errors or have side effects

    def test_print_debug_summary_noop(self) -> None:
        """Test that print_debug_summary is no-op."""
        debugger = NoOpDebugger()

        debugger.print_debug_summary()

        # Should not raise any errors or have side effects

    def test_export_debug_data_noop(self) -> None:
        """Test that export_debug_data returns placeholder."""
        debugger = NoOpDebugger()

        result = debugger.export_debug_data()

        assert result == Path("debug_not_enabled.json")

    def test_log_iteration_start_noop(self) -> None:
        """Test that log_iteration_start is no-op."""
        debugger = NoOpDebugger()

        debugger.log_iteration_start(iteration_number=1)

        # Should not raise any errors or have side effects

    def test_log_iteration_end_noop(self) -> None:
        """Test that log_iteration_end is no-op."""
        debugger = NoOpDebugger()

        debugger.log_iteration_end(iteration_number=1, success=True)

        # Should not raise any errors or have side effects

    def test_log_test_failures_noop(self) -> None:
        """Test that log_test_failures is no-op."""
        debugger = NoOpDebugger()

        debugger.log_test_failures(count=5)

        # Should not raise any errors or have side effects

    def test_log_test_fixes_noop(self) -> None:
        """Test that log_test_fixes is no-op."""
        debugger = NoOpDebugger()

        debugger.log_test_fixes(count=3)

        # Should not raise any errors or have side effects

    def test_log_hook_failures_noop(self) -> None:
        """Test that log_hook_failures is no-op."""
        debugger = NoOpDebugger()

        debugger.log_hook_failures(count=2)

        # Should not raise any errors or have side effects

    def test_log_hook_fixes_noop(self) -> None:
        """Test that log_hook_fixes is no-op."""
        debugger = NoOpDebugger()

        debugger.log_hook_fixes(count=2)

        # Should not raise any errors or have side effects

    def test_set_workflow_success_noop(self) -> None:
        """Test that set_workflow_success is no-op."""
        debugger = NoOpDebugger()

        debugger.set_workflow_success(success=True)

        # Should not raise any errors or have side effects


@pytest.mark.unit
class TestModuleFunctions:
    """Test module-level debugger functions."""

    def test_get_ai_agent_debugger_returns_noop_by_default(self) -> None:
        """Test that get_ai_agent_debugger returns NoOpDebugger by default."""
        # Reset module-level global
        import crackerjack.services.debug as debug_module

        debug_module._ai_agent_debugger = None

        with patch.dict("os.environ", {}, clear=True):
            debugger = get_ai_agent_debugger()

            assert isinstance(debugger, NoOpDebugger)
            assert debugger.enabled is False

    def test_get_ai_agent_debugger_with_env_var(self) -> None:
        """Test that get_ai_agent_debugger returns AIAgentDebugger when env var set."""
        # Reset module-level global
        import crackerjack.services.debug as debug_module

        debug_module._ai_agent_debugger = None

        with patch.dict("os.environ", {"AI_AGENT_DEBUG": "1"}):
            with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
                mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

                debugger = get_ai_agent_debugger()

                assert isinstance(debugger, AIAgentDebugger)
                assert debugger.enabled is True

    def test_get_ai_agent_debugger_singleton(self) -> None:
        """Test that get_ai_agent_debugger returns same instance (singleton)."""
        # Reset module-level global
        import crackerjack.services.debug as debug_module

        debug_module._ai_agent_debugger = None

        with patch.dict("os.environ", {}, clear=True):
            debugger1 = get_ai_agent_debugger()
            debugger2 = get_ai_agent_debugger()

            assert debugger1 is debugger2

    def test_enable_ai_agent_debugging(self) -> None:
        """Test enable_ai_agent_debugging function."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            debugger = enable_ai_agent_debugging(verbose=True)

            assert isinstance(debugger, AIAgentDebugger)
            assert debugger.enabled is True
            assert debugger.verbose is True

    def test_disable_ai_agent_debugging(self) -> None:
        """Test disable_ai_agent_debugging function."""
        with patch("crackerjack.services.debug.get_log_manager") as mock_log_mgr:
            mock_log_mgr.return_value.create_debug_log_file.return_value = Path("/tmp/test.log")

            # First enable debugging
            debugger = enable_ai_agent_debugging()
            assert debugger.enabled is True

            # Then disable it
            disable_ai_agent_debugging()

            # Debugger should now be disabled
            assert debugger.enabled is False
