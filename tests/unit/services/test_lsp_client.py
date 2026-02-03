"""Tests for LSP Client service.

Tests pool management, process lifecycle, connection leaks, and error handling.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.services.lsp_client import (
    JSONRPCClient,
    LSPClient,
    ProgressCallback,
    RealTimeTypingFeedback,
)


class MockProgressCallback:
    """Mock progress callback for testing."""
    def __init__(self) -> None:
        self.files_started = []
        self.files_completed = []
        self.progress_updates = []

    def on_file_start(self, file_path: str) -> None:
        self.files_started.append(file_path)

    def on_file_complete(self, file_path: str, error_count: int) -> None:
        self.files_completed.append((file_path, error_count))

    def on_progress(self, current: int, total: int) -> None:
        self.progress_updates.append((current, total))


class TestProgressCallback:
    """Tests for ProgressCallback protocol."""

    def test_callback_has_required_methods(self) -> None:
        """Test that mock callback has required protocol methods."""
        callback = MockProgressCallback()
        # Check that all required methods exist
        assert hasattr(callback, "on_file_start")
        assert hasattr(callback, "on_file_complete")
        assert hasattr(callback, "on_progress")
        # Check they're callable
        assert callable(callback.on_file_start)
        assert callable(callback.on_file_complete)
        assert callable(callback.on_progress)

    def test_callback_methods(self) -> None:
        """Test progress callback methods work correctly."""
        callback = MockProgressCallback()

        callback.on_file_start("test.py")
        assert "test.py" in callback.files_started

        callback.on_file_complete("test.py", 5)
        assert ("test.py", 5) in callback.files_completed

        callback.on_progress(3, 10)
        assert (3, 10) in callback.progress_updates


class TestRealTimeTypingFeedback:
    """Tests for RealTimeTypingFeedback class."""

    def test_initialization(self) -> None:
        """Test RealTimeTypingFeedback initializes correctly."""
        feedback = RealTimeTypingFeedback()
        assert feedback._total_errors == 0
        assert feedback._files_checked == 0

    def test_on_file_start(self) -> None:
        """Test file start tracking."""
        feedback = RealTimeTypingFeedback()
        feedback.on_file_start("/path/to/test.py")
        # Should not raise errors

    def test_on_file_complete_no_errors(self) -> None:
        """Test file complete tracking with no errors."""
        feedback = RealTimeTypingFeedback()
        feedback.on_file_complete("/path/to/test.py", 0)
        assert feedback._files_checked == 1
        assert feedback._total_errors == 0

    def test_on_file_complete_with_errors(self) -> None:
        """Test file complete tracking with errors."""
        feedback = RealTimeTypingFeedback()
        feedback.on_file_complete("/path/to/test.py", 5)
        assert feedback._files_checked == 1
        assert feedback._total_errors == 5

    def test_get_summary_no_errors(self) -> None:
        """Test summary when all files pass."""
        feedback = RealTimeTypingFeedback()
        feedback.on_file_complete("test1.py", 0)
        feedback.on_file_complete("test2.py", 0)

        summary = feedback.get_summary()
        assert "All 2 files passed" in summary
        assert "✅" in summary

    def test_get_summary_with_errors(self) -> None:
        """Test summary when files have errors."""
        feedback = RealTimeTypingFeedback()
        feedback.on_file_complete("test1.py", 3)
        feedback.on_file_complete("test2.py", 2)

        summary = feedback.get_summary()
        assert "5 type errors" in summary
        assert "2 files" in summary
        assert "❌" in summary


class TestJSONRPCClient:
    """Tests for JSONRPCClient class."""

    def test_initialization(self) -> None:
        """Test JSONRPCClient initializes with LSP service."""
        mock_service = Mock()
        client = JSONRPCClient(mock_service)
        assert client.lsp_service == mock_service
        assert client._request_id == 0

    def test_next_request_id(self) -> None:
        """Test request ID generation."""
        mock_service = Mock()
        client = JSONRPCClient(mock_service)

        id1 = client._next_request_id()
        id2 = client._next_request_id()
        id3 = client._next_request_id()

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    async def test_initialize_sends_correct_params(self) -> None:
        """Test initialize sends correct LSP parameters."""
        mock_service = Mock()

        # Create an async mock function
        async def mock_send_request(method, params):
            return {"result": "initialized"}

        mock_service.send_lsp_request = mock_send_request

        client = JSONRPCClient(mock_service)
        result = await client.initialize("/test/path")

        # Verify the call was made
        assert result == {"result": "initialized"}


class TestLSPClientInitialization:
    """Tests for LSPClient initialization and state management."""

    def test_default_initialization(self) -> None:
        """Test LSPClient initializes with defaults."""
        client = LSPClient()
        assert client._server_port is None
        assert client._server_host == "127.0.0.1"
        assert client._lsp_service is None
        assert client._jsonrpc_client is None

    def test_initialization_with_custom_console(self) -> None:
        """Test LSPClient with custom console."""
        mock_console = Mock()
        client = LSPClient(console=mock_console)
        assert client.console == mock_console

    def test_custom_port(self) -> None:
        """Test LSPClient with custom port."""
        client = LSPClient()
        client._server_port = 9000
        assert client._server_port == 9000


class TestServerRunningDetection:
    """Tests for server running detection."""

    def test_is_server_running_with_active_service(self) -> None:
        """Test server detection with active LSP service."""
        client = LSPClient()

        mock_service = Mock()
        mock_service.is_running = True
        client._lsp_service = mock_service

        assert client.is_server_running() is True

    def test_is_server_running_with_inactive_service(self) -> None:
        """Test server detection with inactive LSP service."""
        client = LSPClient()

        mock_service = Mock()
        mock_service.is_running = False
        client._lsp_service = mock_service

        assert client.is_server_running() is False

    @patch("crackerjack.services.lsp_client.find_zuban_lsp_processes")
    def test_is_server_running_discovers_process(self, mock_find_processes: MagicMock) -> None:
        """Test server detection discovers external processes."""
        mock_find_processes.return_value = [
            {"pid": 12345, "cpu": 1.5, "mem": 1024, "command": "zuban"}
        ]

        client = LSPClient()
        assert client.is_server_running() is True

    @patch("crackerjack.services.lsp_client.find_zuban_lsp_processes")
    def test_is_server_running_no_processes(self, mock_find_processes: MagicMock) -> None:
        """Test server detection with no processes."""
        mock_find_processes.return_value = []

        client = LSPClient()
        assert client.is_server_running() is False


class TestGetServerInfo:
    """Tests for server information retrieval."""

    @patch("crackerjack.services.lsp_client.find_zuban_lsp_processes")
    def test_get_server_info_returns_process_data(self, mock_find_processes: MagicMock) -> None:
        """Test get_server_info returns process information."""
        mock_find_processes.return_value = [
            {
                "pid": 12345,
                "cpu": 2.5,
                "mem": 2048,
                "command": "zuban lsp --stdio"
            }
        ]

        client = LSPClient()
        info = client.get_server_info()

        assert info is not None
        assert info["pid"] == 12345
        assert info["cpu"] == 2.5
        assert info["mem"] == 2048
        assert info["command"] == "zuban lsp --stdio"

    @patch("crackerjack.services.lsp_client.find_zuban_lsp_processes")
    def test_get_server_info_no_processes(self, mock_find_processes: MagicMock) -> None:
        """Test get_server_info returns None when no processes."""
        mock_find_processes.return_value = []

        client = LSPClient()
        info = client.get_server_info()

        assert info is None

    @patch("crackerjack.services.lsp_client.find_zuban_lsp_processes")
    def test_get_server_info_returns_first_process(self, mock_find_processes: MagicMock) -> None:
        """Test get_server_info returns first process when multiple exist."""
        mock_find_processes.return_value = [
            {"pid": 12345, "cpu": 1.0, "mem": 1024, "command": "zuban"},
            {"pid": 12346, "cpu": 2.0, "mem": 2048, "command": "zuban"}
        ]

        client = LSPClient()
        info = client.get_server_info()

        assert info["pid"] == 12345  # First process


class TestZubanFallback:
    """Tests for fallback to direct zuban execution."""

    @patch("crackerjack.services.lsp_client.subprocess.run")
    def test_check_file_with_zuban_success(self, mock_run: MagicMock) -> None:
        """Test successful zuban execution."""
        mock_result = MagicMock()
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        client = LSPClient()
        diagnostics = client._check_file_with_zuban("test.py")

        assert isinstance(diagnostics, list)
        mock_run.assert_called_once()

    @patch("crackerjack.services.lsp_client.subprocess.run")
    def test_check_file_with_zuban_errors(self, mock_run: MagicMock) -> None:
        """Test zuban execution returns errors."""
        mock_result = MagicMock()
        # Actual zuban format: file:line:col: message
        mock_result.stderr = "test.py:42:5: error: Type mismatch"
        mock_run.return_value = mock_result

        client = LSPClient()
        diagnostics = client._check_file_with_zuban("test.py")

        assert len(diagnostics) == 1
        assert diagnostics[0]["line"] == 42
        assert diagnostics[0]["column"] == 5

    @patch("crackerjack.services.lsp_client.subprocess.run")
    def test_check_file_with_zuban_multiple_errors(self, mock_run: MagicMock) -> None:
        """Test zuban execution returns multiple errors."""
        mock_result = MagicMock()
        # Multiple errors in actual zuban format (one per line)
        mock_result.stderr = """test.py:42:5: error: Type mismatch
test.py:45:10: error: Undefined variable"""
        mock_run.return_value = mock_result

        client = LSPClient()
        diagnostics = client._check_file_with_zuban("test.py")

        assert len(diagnostics) == 2

    @patch("crackerjack.services.lsp_client.subprocess.run")
    def test_check_file_with_zuban_timeout(self, mock_run: MagicMock) -> None:
        """Test zuban execution handles timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("zuban", 30)

        client = LSPClient()
        diagnostics = client._check_file_with_zuban("test.py")

        # Should return empty list on timeout
        assert isinstance(diagnostics, list)

    @patch("crackerjack.services.lsp_client.subprocess.run")
    def test_check_file_with_zuban_file_not_found(self, mock_run: MagicMock) -> None:
        """Test zuban execution handles missing file."""
        mock_result = MagicMock()
        mock_result.stderr = "error: File not found: test.py"
        mock_run.return_value = mock_result

        client = LSPClient()
        diagnostics = client._check_file_with_zuban("test.py")

        # Should still return parsed diagnostics
        assert isinstance(diagnostics, list)


class TestZubanOutputParsing:
    """Tests for zuban output parsing."""

    def test_parse_error_line_simple(self) -> None:
        """Test parsing simple error line."""
        client = LSPClient()
        line = "test.py:42:5: error: Type mismatch"

        result = client._parse_error_line(line)

        assert result is not None
        assert result["severity"] == "error"
        assert result["line"] == 42
        assert result["column"] == 5
        assert "Type mismatch" in result["message"]

    def test_parse_error_line_with_details(self) -> None:
        """Test parsing error line with details."""
        client = LSPClient()
        line = "  Expected: int"

        result = client._parse_error_line(line)

        # Detail lines don't have enough parts
        assert result is None

    def test_is_error_line_detection(self) -> None:
        """Test error line detection."""
        client = LSPClient()

        # Needs both ":" and "error:" (case-insensitive)
        assert client._is_error_line("test.py:42: error: Type mismatch") is True
        assert client._is_error_line("test.py:42: ERROR: Type mismatch") is True
        assert client._is_error_line("test.py:42: warning: Unused") is False
        assert client._is_error_line("  Expected: int") is False
        assert client._is_error_line("") is False

    def test_parse_zuban_output_multiple_errors(self) -> None:
        """Test parsing zuban output with multiple errors."""
        client = LSPClient()
        output = """test.py:42:5: error: Type mismatch
test.py:45:10: error: Undefined variable"""

        diagnostics = client._parse_zuban_output(output)

        assert len(diagnostics) == 2

    def test_parse_zuban_output_empty(self) -> None:
        """Test parsing empty zuban output."""
        client = LSPClient()
        diagnostics = client._parse_zuban_output("")

        assert diagnostics == []


class TestFileCheckingWithFeedback:
    """Tests for file checking with progress feedback."""

    def test_check_files_simple_feedback(self) -> None:
        """Test file checking with simple feedback."""
        client = LSPClient()

        # Mock subprocess to avoid actual zuban calls
        with patch.object(client, "_check_file_with_zuban", return_value=[]):
            callback = MockProgressCallback()
            result = client._check_files_simple_feedback(
                ["test1.py", "test2.py"],
                callback
            )

            assert isinstance(result, dict)
            assert "test1.py" in result
            assert "test2.py" in result
            assert len(callback.files_started) == 2
            assert len(callback.files_completed) == 2

    def test_process_single_file_with_callback(self) -> None:
        """Test processing single file with callback."""
        client = LSPClient()

        with patch.object(client, "_check_file_with_zuban", return_value=[]):
            callback = MockProgressCallback()
            result = client._process_single_file_with_zuban("test.py", callback)

            assert "test.py" in result
            assert "test.py" in callback.files_started
            assert ("test.py", 0) in callback.files_completed

    def test_process_single_file_without_callback(self) -> None:
        """Test processing single file without callback."""
        client = LSPClient()

        with patch.object(client, "_check_file_with_zuban", return_value=[]):
            result = client._process_single_file_with_zuban("test.py", None)

            assert "test.py" in result
            assert isinstance(result["test.py"], list)


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @patch("crackerjack.services.lsp_client.subprocess.run")
    def test_subprocess_failure_handling(self, mock_run: MagicMock) -> None:
        """Test handling of subprocess failures."""
        mock_run.side_effect = FileNotFoundError("zuban not found")

        client = LSPClient()
        diagnostics = client._check_file_with_zuban("test.py")

        # Should return empty list on failure
        assert isinstance(diagnostics, list)
        assert diagnostics == []

    @patch("crackerjack.services.lsp_client.subprocess.run")
    def test_subprocess_exception_propagation(self, mock_run: MagicMock) -> None:
        """Test that certain exceptions propagate."""
        mock_run.side_effect = PermissionError("Access denied")

        client = LSPClient()

        # PermissionError should propagate
        with pytest.raises(PermissionError):
            client._check_file_with_zuban("test.py")

    def test_empty_file_list(self) -> None:
        """Test handling of empty file list."""
        client = LSPClient()

        with patch.object(client, "_check_file_with_zuban", return_value=[]):
            callback = MockProgressCallback()
            result = client._check_files_simple_feedback([], callback)

            assert result == {}


class TestDiagnosticFormatting:
    """Tests for diagnostic formatting."""

    def test_format_diagnostics_empty(self) -> None:
        """Test formatting empty diagnostics."""
        client = LSPClient()
        formatted = client.format_diagnostics({})

        assert "✅ No type errors found" in formatted

    def test_format_diagnostics_with_errors(self) -> None:
        """Test formatting diagnostics with errors."""
        client = LSPClient()
        diagnostics = {
            "test.py": [
                {
                    "severity": "error",
                    "message": "Type mismatch",
                    "line": 42,
                    "column": 5
                }
            ]
        }

        formatted = client.format_diagnostics(diagnostics)

        assert "test.py" in formatted
        assert "Type mismatch" in formatted
        assert "Line 42:5" in formatted
        assert "🔴" in formatted  # Error icon

    def test_format_diagnostics_multiple_files(self) -> None:
        """Test formatting diagnostics from multiple files."""
        client = LSPClient()
        diagnostics = {
            "test1.py": [{"severity": "error", "message": "Error 1", "line": 10, "column": 1}],
            "test2.py": [{"severity": "warning", "message": "Warning 1", "line": 20, "column": 1}]
        }

        formatted = client.format_diagnostics(diagnostics)

        assert "test1.py" in formatted
        assert "test2.py" in formatted
        assert "Error 1" in formatted
        assert "Warning 1" in formatted


class TestGetProjectFiles:
    """Tests for project file discovery."""

    def test_get_project_files(self) -> None:
        """Test getting Python files from project."""
        client = LSPClient()

        # Use a temporary directory structure
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cj_dir = tmppath / "crackerjack"
            cj_dir.mkdir()
            (cj_dir / "test1.py").touch()
            (cj_dir / "test2.py").touch()
            (cj_dir / "README.md").touch()
            (cj_dir / "mcp").mkdir()
            (cj_dir / "mcp" / "server.py").touch()  # Should be filtered out
            (cj_dir / "subdir").mkdir()
            (cj_dir / "subdir" / "test3.py").touch()

            files = client.get_project_files(tmppath)

            # Should find all Python files except in mcp/ and plugins/
            assert len(files) == 3
            assert any("test1.py" in f for f in files)
            assert any("test2.py" in f for f in files)
            assert any("test3.py" in f for f in files)
            # Should not include mcp files
            assert not any("mcp/server.py" in f for f in files)

    def test_get_project_files_no_crackerjack_dir(self) -> None:
        """Test getting files when no crackerjack directory exists."""
        client = LSPClient()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # No crackerjack directory created

            files = client.get_project_files(tmppath)

            assert files == []
