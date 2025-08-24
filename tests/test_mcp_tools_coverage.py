"""Comprehensive test coverage for MCP tools modules.

Tests the MCP tools that currently have 0% coverage:
- core_tools.py - Basic execution and stage tools
- monitoring_tools.py - Status monitoring and health checks
- Tools registration and functionality
- Error handling and validation

Uses proper mocking for external dependencies and follows crackerjack testing patterns.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.mcp.tools.core_tools import (
    _configure_stage_options,
    _detect_errors_and_suggestions,
    _execute_stage,
    _get_error_patterns,
    _get_error_suggestion,
    _parse_stage_args,
    _validate_stage_request,
    register_analyze_errors_tool,
    register_core_tools,
)
from crackerjack.mcp.tools.monitoring_tools import (
    _add_state_manager_stats,
    _build_server_stats,
    _create_error_response,
    _determine_next_action,
    _get_active_jobs,
    _get_comprehensive_status,
    _get_session_info,
    _get_stage_status_dict,
    register_monitoring_tools,
)


class TestCoreToolsValidation:
    """Test core tools validation and parsing functions."""

    @pytest.mark.asyncio
    async def test_validate_stage_request_no_context(self) -> None:
        """Test stage request validation without context."""
        result = await _validate_stage_request(None, None)

        assert result is not None
        assert "error" in result
        assert "Server context not available" in result
        assert "success" in result
        assert "false" in result.lower()

    @pytest.mark.asyncio
    async def test_validate_stage_request_with_rate_limiter(self) -> None:
        """Test stage request validation with rate limiter."""
        mock_context = Mock()
        mock_rate_limiter = AsyncMock()

        # Test rate limit exceeded
        mock_rate_limiter.check_request_allowed.return_value = (
            False,
            {"reason": "too many requests"},
        )

        result = await _validate_stage_request(mock_context, mock_rate_limiter)

        assert result is not None
        assert "error" in result
        assert "Rate limit exceeded" in result
        assert "too many requests" in result

    @pytest.mark.asyncio
    async def test_validate_stage_request_allowed(self) -> None:
        """Test stage request validation when allowed."""
        mock_context = Mock()
        mock_rate_limiter = AsyncMock()

        # Test allowed request
        mock_rate_limiter.check_request_allowed.return_value = (True, {})

        result = await _validate_stage_request(mock_context, mock_rate_limiter)

        assert result is None  # No error when allowed

    @pytest.mark.asyncio
    async def test_validate_stage_request_no_rate_limiter(self) -> None:
        """Test stage request validation without rate limiter."""
        mock_context = Mock()

        result = await _validate_stage_request(mock_context, None)

        assert result is None  # No error when no rate limiter

    def test_parse_stage_args_valid(self) -> None:
        """Test parsing valid stage arguments."""
        result = _parse_stage_args("fast", "{}")

        assert isinstance(result, tuple)
        stage, kwargs = result
        assert stage == "fast"
        assert kwargs == {}

    def test_parse_stage_args_with_kwargs(self) -> None:
        """Test parsing stage arguments with JSON kwargs."""
        kwargs_json = '{"dry_run": true, "verbose": false}'
        result = _parse_stage_args("comprehensive", kwargs_json)

        assert isinstance(result, tuple)
        stage, kwargs = result
        assert stage == "comprehensive"
        assert kwargs == {"dry_run": True, "verbose": False}

    def test_parse_stage_args_invalid_stage(self) -> None:
        """Test parsing invalid stage name."""
        result = _parse_stage_args("invalid_stage", "{}")

        assert isinstance(result, str)
        assert "error" in result
        assert "Invalid stage" in result
        assert "fast" in result  # Should list valid stages

    def test_parse_stage_args_invalid_json(self) -> None:
        """Test parsing with invalid JSON kwargs."""
        result = _parse_stage_args("fast", '{"invalid": json}')

        assert isinstance(result, str)
        assert "error" in result
        assert "Invalid JSON" in result

    def test_configure_stage_options(self) -> None:
        """Test stage options configuration."""
        from crackerjack.models.config import WorkflowOptions

        # Test each stage type
        fast_options = _configure_stage_options("fast")
        assert isinstance(fast_options, WorkflowOptions)
        assert fast_options.skip_hooks is False

        comprehensive_options = _configure_stage_options("comprehensive")
        assert isinstance(comprehensive_options, WorkflowOptions)
        assert comprehensive_options.skip_hooks is False

        tests_options = _configure_stage_options("tests")
        assert isinstance(tests_options, WorkflowOptions)
        assert tests_options.testing.test is True

        cleaning_options = _configure_stage_options("cleaning")
        assert isinstance(cleaning_options, WorkflowOptions)
        assert cleaning_options.cleaning.clean is True

    def test_execute_stage(self) -> None:
        """Test stage execution with mock orchestrator."""
        mock_orchestrator = Mock()
        mock_orchestrator.run_fast_hooks_only.return_value = True
        mock_orchestrator.run_comprehensive_hooks_only.return_value = True
        mock_orchestrator.run_testing_phase.return_value = True
        mock_orchestrator.run_cleaning_phase.return_value = True

        mock_options = Mock()

        # Test each stage execution
        assert _execute_stage(mock_orchestrator, "fast", mock_options) is True
        mock_orchestrator.run_fast_hooks_only.assert_called_once_with(mock_options)

        assert _execute_stage(mock_orchestrator, "comprehensive", mock_options) is True
        mock_orchestrator.run_comprehensive_hooks_only.assert_called_once_with(
            mock_options,
        )

        assert _execute_stage(mock_orchestrator, "tests", mock_options) is True
        mock_orchestrator.run_testing_phase.assert_called_once_with(mock_options)

        assert _execute_stage(mock_orchestrator, "cleaning", mock_options) is True
        mock_orchestrator.run_cleaning_phase.assert_called_once_with(mock_options)

        # Test unknown stage
        assert _execute_stage(mock_orchestrator, "unknown", mock_options) is False


class TestErrorAnalysis:
    """Test error analysis and pattern detection."""

    def test_get_error_patterns(self) -> None:
        """Test getting error patterns."""
        patterns = _get_error_patterns()

        assert isinstance(patterns, list)
        assert len(patterns) > 0

        # Check pattern structure
        for pattern_type, regex in patterns:
            assert isinstance(pattern_type, str)
            assert isinstance(regex, str)
            assert len(pattern_type) > 0
            assert len(regex) > 0

        # Check for expected pattern types
        pattern_types = [p[0] for p in patterns]
        assert "type_error" in pattern_types
        assert "import_error" in pattern_types
        assert "test_failure" in pattern_types

    def test_get_error_suggestion(self) -> None:
        """Test getting error suggestions."""
        # Test known error types
        type_suggestion = _get_error_suggestion("type_error")
        assert "type annotations" in type_suggestion

        import_suggestion = _get_error_suggestion("import_error")
        assert "module" in import_suggestion.lower()

        test_suggestion = _get_error_suggestion("test_failure")
        assert "test" in test_suggestion.lower()

        # Test unknown error type
        unknown_suggestion = _get_error_suggestion("unknown_error")
        assert "No specific suggestion" in unknown_suggestion

    def test_detect_errors_and_suggestions(self) -> None:
        """Test error detection and suggestions."""
        # Test error text with multiple error types
        error_text = """
        TypeError: 'str' object has no attribute 'unknown'
        ImportError: No module named 'nonexistent'
        FAILED test_example.py::test_function - AssertionError: Expected True
        """

        # Test with suggestions
        detected_errors, suggestions = _detect_errors_and_suggestions(error_text, True)

        assert "type_error" in detected_errors
        assert "import_error" in detected_errors
        assert "test_failure" in detected_errors
        assert len(suggestions) == len(detected_errors)
        assert len(suggestions) > 0

        # Test without suggestions
        detected_errors_no_sugg, suggestions_no_sugg = _detect_errors_and_suggestions(
            error_text, False,
        )

        assert detected_errors_no_sugg == detected_errors
        assert suggestions_no_sugg == []

    def test_detect_specific_error_patterns(self) -> None:
        """Test detection of specific error patterns."""
        # Test individual error patterns
        test_cases = [
            ("TypeError: object has no attribute", ["type_error"]),
            ("ModuleNotFoundError: No module named", ["import_error"]),
            ("AttributeError: object has no attribute", ["attribute_error"]),
            ("SyntaxError: invalid syntax", ["syntax_error"]),
            ("FAILED test.py - AssertionError", ["test_failure"]),
            ("hook pre-commit failed", ["hook_failure"]),
        ]

        for error_text, expected_types in test_cases:
            detected_errors, _ = _detect_errors_and_suggestions(error_text, False)

            for expected_type in expected_types:
                assert expected_type in detected_errors, (
                    f"Expected {expected_type} in {detected_errors} for text: {error_text}"
                )


class TestCoreToolsRegistration:
    """Test core tools registration and MCP integration."""

    @pytest.fixture
    def mock_mcp_app(self) -> Mock:
        """Create mock MCP application."""
        mock_app = Mock()
        mock_app.tool = Mock()
        return mock_app

    def test_register_core_tools(self, mock_mcp_app: Mock) -> None:
        """Test core tools registration."""
        register_core_tools(mock_mcp_app)

        # Verify tool decorator was called
        mock_mcp_app.tool.assert_called()

        # Get the registered function
        tool_calls = mock_mcp_app.tool.call_args_list
        assert len(tool_calls) >= 1

    def test_register_analyze_errors_tool(self, mock_mcp_app: Mock) -> None:
        """Test analyze errors tool registration."""
        register_analyze_errors_tool(mock_mcp_app)

        # Verify tool decorator was called
        mock_mcp_app.tool.assert_called()

    @pytest.mark.asyncio
    async def test_run_crackerjack_stage_tool_functionality(self) -> None:
        """Test run_crackerjack_stage tool functionality with mocks."""
        # Create mock context
        mock_context = Mock()
        mock_context.rate_limiter = None
        mock_context.console = Mock()
        mock_context.config.project_path = Path("/test")

        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.run_fast_hooks_only.return_value = True

        with patch(
            "crackerjack.mcp.tools.core_tools.get_context", return_value=mock_context,
        ), patch(
            "crackerjack.mcp.tools.core_tools.WorkflowOrchestrator",
            return_value=mock_orchestrator,
        ):
            # Import the function after patching
            from crackerjack.mcp.tools.core_tools import register_core_tools

            # Create mock app and register tools
            mock_app = Mock()
            registered_functions = []

            def mock_tool_decorator():
                def decorator(func):
                    registered_functions.append(func)
                    return func

                return decorator

            mock_app.tool = mock_tool_decorator
            register_core_tools(mock_app)

            # Find the run_crackerjack_stage function
            stage_function = None
            for func in registered_functions:
                if func.__name__ == "run_crackerjack_stage":
                    stage_function = func
                    break

            assert stage_function is not None

            # Test the function
            result = await stage_function("fast", "{}")

            # Parse and verify result
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data["stage"] == "fast"

    @pytest.mark.asyncio
    async def test_analyze_errors_tool_functionality(self) -> None:
        """Test analyze_errors tool functionality."""
        # Create mock context and debugger
        mock_context = Mock()
        mock_debugger = Mock()
        mock_debugger.enabled = True

        with patch(
            "crackerjack.mcp.tools.core_tools.get_context", return_value=mock_context,
        ), patch(
            "crackerjack.mcp.tools.core_tools.get_ai_agent_debugger",
            return_value=mock_debugger,
        ):
            # Import and register analyze errors tool
            from crackerjack.mcp.tools.core_tools import (
                register_analyze_errors_tool,
            )

            mock_app = Mock()
            registered_functions = []

            def mock_tool_decorator():
                def decorator(func):
                    registered_functions.append(func)
                    return func

                return decorator

            mock_app.tool = mock_tool_decorator
            register_analyze_errors_tool(mock_app)

            # Find the analyze_errors function
            analyze_function = None
            for func in registered_functions:
                if func.__name__ == "analyze_errors":
                    analyze_function = func
                    break

            assert analyze_function is not None

            # Test the function
            error_output = "TypeError: object has no attribute 'test'"
            result = await analyze_function(error_output, True)

            # Parse and verify result
            result_data = json.loads(result)
            assert "analysis" in result_data
            assert "error_types" in result_data
            assert "suggestions" in result_data
            assert isinstance(result_data["error_types"], list)


class TestMonitoringToolsUtilities:
    """Test monitoring tools utility functions."""

    def test_create_error_response(self) -> None:
        """Test error response creation."""
        error_msg = "Test error message"

        # Test default success=False
        response = _create_error_response(error_msg)
        response_data = json.loads(response)

        assert response_data["error"] == error_msg
        assert response_data["success"] is False

        # Test custom success value
        response_success = _create_error_response(error_msg, success=True)
        response_data_success = json.loads(response_success)

        assert response_data_success["error"] == error_msg
        assert response_data_success["success"] is True

    def test_get_stage_status_dict(self) -> None:
        """Test getting stage status dictionary."""
        mock_state_manager = Mock()
        mock_state_manager.get_stage_status = Mock(
            side_effect=lambda stage: f"{stage}_status",
        )

        result = _get_stage_status_dict(mock_state_manager)

        expected_stages = ["fast", "comprehensive", "tests", "cleaning"]
        assert isinstance(result, dict)
        assert len(result) == len(expected_stages)

        for stage in expected_stages:
            assert stage in result
            assert result[stage] == f"{stage}_status"
            mock_state_manager.get_stage_status.assert_any_call(stage)

    def test_get_session_info(self) -> None:
        """Test getting session information."""
        mock_state_manager = Mock()
        mock_state_manager.iteration_count = 5
        mock_state_manager.current_iteration = 3
        mock_state_manager.session_active = True

        result = _get_session_info(mock_state_manager)

        assert result["total_iterations"] == 5
        assert result["current_iteration"] == 3
        assert result["session_active"] is True

    def test_get_session_info_missing_attributes(self) -> None:
        """Test getting session info with missing attributes."""
        mock_state_manager = Mock()
        # Don't set attributes to test defaults
        del mock_state_manager.iteration_count
        del mock_state_manager.current_iteration
        del mock_state_manager.session_active

        result = _get_session_info(mock_state_manager)

        assert result["total_iterations"] == 0
        assert result["current_iteration"] == 0
        assert result["session_active"] is False

    def test_determine_next_action(self) -> None:
        """Test determining next recommended action."""
        mock_state_manager = Mock()

        # Test when fast stage not completed
        mock_state_manager.get_stage_status = Mock(
            side_effect=lambda stage: "pending" if stage == "fast" else "completed",
        )

        result = _determine_next_action(mock_state_manager)

        assert result["recommended_action"] == "run_stage"
        assert result["parameters"]["stage"] == "fast"
        assert "Fast hooks not completed" in result["reason"]

        # Test when tests not completed
        mock_state_manager.get_stage_status = Mock(
            side_effect=lambda stage: "pending" if stage == "tests" else "completed",
        )

        result = _determine_next_action(mock_state_manager)

        assert result["recommended_action"] == "run_stage"
        assert result["parameters"]["stage"] == "tests"
        assert "Tests not completed" in result["reason"]

        # Test when all stages completed
        mock_state_manager.get_stage_status = Mock(return_value="completed")

        result = _determine_next_action(mock_state_manager)

        assert result["recommended_action"] == "complete"
        assert result["parameters"] == {}
        assert "All stages completed" in result["reason"]

    def test_build_server_stats(self) -> None:
        """Test building server statistics."""
        mock_context = Mock()
        mock_context.config.project_path = Path("/test/project")
        mock_context.websocket_server_port = 8675
        mock_context.websocket_server_process = Mock()  # Not None
        mock_context.rate_limiter = Mock()
        mock_context.rate_limiter.config.__dict__ = {"max_requests": 100}

        # Mock progress directory
        mock_progress_dir = Mock()
        mock_progress_dir.exists.return_value = True
        mock_progress_dir.glob.return_value = [Path("file1.json"), Path("file2.json")]
        mock_context.progress_dir = mock_progress_dir

        result = _build_server_stats(mock_context)

        assert "server_info" in result
        assert "rate_limiting" in result
        assert "resource_usage" in result
        assert "timestamp" in result

        assert result["server_info"]["project_path"] == "/test/project"
        assert result["server_info"]["websocket_port"] == 8675
        assert result["server_info"]["websocket_active"] is True

        assert result["rate_limiting"]["enabled"] is True
        assert result["rate_limiting"]["config"]["max_requests"] == 100

        assert result["resource_usage"]["temp_files_count"] == 2

    def test_add_state_manager_stats(self) -> None:
        """Test adding state manager statistics to stats dict."""
        stats = {}
        mock_state_manager = Mock()
        mock_state_manager.iteration_count = 3
        mock_state_manager.session_active = True
        mock_state_manager.issues = ["issue1", "issue2"]

        _add_state_manager_stats(stats, mock_state_manager)

        assert "state_manager" in stats
        assert stats["state_manager"]["iteration_count"] == 3
        assert stats["state_manager"]["session_active"] is True
        assert stats["state_manager"]["issues_count"] == 2

    def test_add_state_manager_stats_no_manager(self) -> None:
        """Test adding state manager stats when no manager available."""
        stats = {}

        _add_state_manager_stats(stats, None)

        assert "state_manager" not in stats

    def test_get_active_jobs(self) -> None:
        """Test getting active jobs from progress files."""
        mock_context = Mock()

        # Mock progress directory with job files
        mock_progress_dir = Mock()
        mock_progress_dir.exists.return_value = True

        # Create mock progress files
        mock_file1 = Mock()
        mock_file1.read_text.return_value = json.dumps(
            {
                "job_id": "job-123",
                "status": "running",
                "iteration": 2,
                "max_iterations": 5,
                "current_stage": "tests",
                "overall_progress": 40,
                "stage_progress": 80,
                "message": "Running tests...",
                "timestamp": "2024-01-01T10:00:00",
                "error_counts": {"errors": 2},
            },
        )

        mock_file2 = Mock()
        mock_file2.read_text.return_value = json.dumps(
            {
                "job_id": "job-456",
                "status": "completed",
                "iteration": 5,
                "max_iterations": 5,
            },
        )

        mock_progress_dir.glob.return_value = [mock_file1, mock_file2]
        mock_context.progress_dir = mock_progress_dir

        result = _get_active_jobs(mock_context)

        assert len(result) == 2

        job1 = result[0]
        assert job1["job_id"] == "job-123"
        assert job1["status"] == "running"
        assert job1["iteration"] == 2
        assert job1["current_stage"] == "tests"

        job2 = result[1]
        assert job2["job_id"] == "job-456"
        assert job2["status"] == "completed"

    def test_get_active_jobs_no_directory(self) -> None:
        """Test getting active jobs when progress directory doesn't exist."""
        mock_context = Mock()
        mock_context.progress_dir.exists.return_value = False

        result = _get_active_jobs(mock_context)

        assert result == []

    def test_get_active_jobs_invalid_json(self) -> None:
        """Test getting active jobs with invalid JSON files."""
        mock_context = Mock()

        mock_progress_dir = Mock()
        mock_progress_dir.exists.return_value = True

        # Mock file with invalid JSON
        mock_file = Mock()
        mock_file.read_text.return_value = "invalid json content"

        mock_progress_dir.glob.return_value = [mock_file]
        mock_context.progress_dir = mock_progress_dir

        result = _get_active_jobs(mock_context)

        # Should skip invalid files and return empty list
        assert result == []


class TestComprehensiveStatus:
    """Test comprehensive status functionality."""

    @pytest.mark.asyncio
    async def test_get_comprehensive_status_no_context(self) -> None:
        """Test comprehensive status when context not available."""
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            side_effect=RuntimeError("No context"),
        ):
            result = await _get_comprehensive_status()

            assert "error" in result
            assert "Server context not available" in result["error"]

    @pytest.mark.asyncio
    async def test_get_comprehensive_status_success(self) -> None:
        """Test successful comprehensive status retrieval."""
        # Mock context
        mock_context = Mock()
        mock_context.config.project_path = Path("/test")
        mock_context.websocket_server_port = 8675
        mock_context.progress_dir.exists.return_value = True
        mock_context.progress_dir.glob.return_value = []
        mock_context.rate_limiter = None
        mock_context.get_websocket_server_status = AsyncMock(
            return_value={"status": "running"},
        )

        # Mock service manager functions
        mock_mcp_processes = [{"pid": 1234, "name": "mcp-server"}]
        mock_websocket_processes = [{"pid": 5678, "name": "websocket-server"}]

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=mock_context,
        ):
            with patch(
                "crackerjack.mcp.tools.monitoring_tools.find_mcp_server_processes",
                return_value=mock_mcp_processes,
            ):
                with patch(
                    "crackerjack.mcp.tools.monitoring_tools.find_websocket_server_processes",
                    return_value=mock_websocket_processes,
                ):
                    result = await _get_comprehensive_status()

        assert "services" in result
        assert "jobs" in result
        assert "server_stats" in result
        assert "timestamp" in result

        # Check services
        assert result["services"]["mcp_server"]["running"] is True
        assert result["services"]["mcp_server"]["processes"] == mock_mcp_processes

        assert result["services"]["websocket_server"]["running"] is True
        assert (
            result["services"]["websocket_server"]["processes"]
            == mock_websocket_processes
        )
        assert result["services"]["websocket_server"]["port"] == 8675

        # Check jobs
        assert "active_count" in result["jobs"]
        assert "completed_count" in result["jobs"]
        assert "failed_count" in result["jobs"]
        assert "details" in result["jobs"]

    @pytest.mark.asyncio
    async def test_get_comprehensive_status_with_exception(self) -> None:
        """Test comprehensive status with exception during retrieval."""
        mock_context = Mock()
        mock_context.config.project_path = Path("/test")

        # Mock an exception during service discovery
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=mock_context,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.find_mcp_server_processes",
            side_effect=Exception("Service error"),
        ):
            result = await _get_comprehensive_status()

        assert "error" in result
        assert "Failed to get comprehensive status" in result["error"]
        assert "Service error" in result["error"]


class TestMonitoringToolsRegistration:
    """Test monitoring tools registration."""

    @pytest.fixture
    def mock_mcp_app(self) -> Mock:
        """Create mock MCP application."""
        mock_app = Mock()
        mock_app.tool = Mock()
        return mock_app

    def test_register_monitoring_tools(self, mock_mcp_app: Mock) -> None:
        """Test monitoring tools registration."""
        register_monitoring_tools(mock_mcp_app)

        # Should register multiple tools
        assert (
            mock_mcp_app.tool.call_count >= 4
        )  # stage_status, next_action, server_stats, comprehensive_status

    @pytest.mark.asyncio
    async def test_monitoring_tool_functions(self) -> None:
        """Test monitoring tool function registration and basic functionality."""
        # Mock context and state manager
        mock_context = Mock()
        mock_state_manager = Mock()
        mock_state_manager.get_stage_status = Mock(return_value="completed")
        mock_state_manager.iteration_count = 5
        mock_state_manager.current_iteration = 3
        mock_state_manager.session_active = True
        mock_context.state_manager = mock_state_manager
        mock_context.config.project_path = Path("/test")
        mock_context.websocket_server_port = 8675
        mock_context.progress_dir.exists.return_value = True
        mock_context.progress_dir.glob.return_value = []
        mock_context.rate_limiter = None

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=mock_context,
        ):
            # Import and register monitoring tools
            from crackerjack.mcp.tools.monitoring_tools import register_monitoring_tools

            mock_app = Mock()
            registered_functions = []

            def mock_tool_decorator():
                def decorator(func):
                    registered_functions.append(func)
                    return func

                return decorator

            mock_app.tool = mock_tool_decorator
            register_monitoring_tools(mock_app)

            # Test that functions were registered
            assert len(registered_functions) >= 4

            # Find and test specific functions
            function_names = [func.__name__ for func in registered_functions]

            assert "get_stage_status" in function_names
            assert "get_next_action" in function_names
            assert "get_server_stats" in function_names
            assert "get_comprehensive_status" in function_names

            # Test stage status function
            stage_status_func = next(
                f for f in registered_functions if f.__name__ == "get_stage_status"
            )
            result = await stage_status_func()
            result_data = json.loads(result)

            assert "stages" in result_data
            assert "session" in result_data
            assert "timestamp" in result_data


class TestToolsIntegration:
    """Test integration between core tools and monitoring tools."""

    @pytest.mark.asyncio
    async def test_tools_error_handling(self) -> None:
        """Test error handling across different tools."""
        # Test with no context available
        with patch(
            "crackerjack.mcp.tools.core_tools.get_context",
            side_effect=RuntimeError("No context"),
        ):
            # This would be called by the actual MCP tool
            from crackerjack.mcp.tools.core_tools import register_core_tools

            mock_app = Mock()
            registered_functions = []

            def mock_tool_decorator():
                def decorator(func):
                    registered_functions.append(func)
                    return func

                return decorator

            mock_app.tool = mock_tool_decorator
            register_core_tools(mock_app)

            # Find stage function and test error handling
            stage_function = next(
                f for f in registered_functions if f.__name__ == "run_crackerjack_stage"
            )
            result = await stage_function("fast", "{}")

            # Should return error response
            assert "error" in result

    def test_tools_consistent_error_format(self) -> None:
        """Test that tools return consistent error formats."""
        # Test core tools error format
        core_error = _create_error_response("Core error", False)
        core_data = json.loads(core_error)

        assert "error" in core_data
        assert "success" in core_data
        assert core_data["success"] is False

        # Test similar format in other places
        parse_error = _parse_stage_args("invalid", "{}")
        assert isinstance(parse_error, str)
        parse_data = json.loads(parse_error)

        assert "error" in parse_data
        assert "success" in parse_data
        assert parse_data["success"] is False

    @pytest.mark.asyncio
    async def test_cross_tool_context_usage(self) -> None:
        """Test that tools properly use shared context."""
        mock_context = Mock()
        mock_context.state_manager = Mock()
        mock_context.config.project_path = Path("/test")
        mock_context.rate_limiter = None

        with patch(
            "crackerjack.mcp.tools.core_tools.get_context", return_value=mock_context,
        ), patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=mock_context,
        ):
            # Both tools should use the same context
            core_validation = await _validate_stage_request(mock_context, None)
            assert core_validation is None  # No error

            # Monitoring tools should also work with same context
            server_stats = _build_server_stats(mock_context)
            assert "server_info" in server_stats
            assert server_stats["server_info"]["project_path"] == "/test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
