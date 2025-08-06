"""Tests for verification toolkit module."""

import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

from crackerjack.verification_toolkit import (
    WorkflowError,
    VerificationToolkit,
    get_toolkit,
    capture_state,
    verify_location,
    take_screenshot
)


class TestWorkflowError:
    """Test WorkflowError exception."""

    def test_workflow_error(self):
        """Test WorkflowError exception creation."""
        error = WorkflowError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestVerificationToolkit:
    """Test VerificationToolkit functionality."""

    def test_init_default(self):
        """Test VerificationToolkit initialization with defaults."""
        toolkit = VerificationToolkit()
        
        assert toolkit.log_dir.name == "crackerjack-verification"
        assert toolkit.workflow_id is None
        assert toolkit.log_file is None

    def test_init_custom_log_dir(self):
        """Test VerificationToolkit initialization with custom log dir."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "custom_verification"
            toolkit = VerificationToolkit(log_dir=log_dir)
            
            assert toolkit.log_dir == log_dir

    def test_init_workflow_log(self):
        """Test initializing workflow logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            toolkit = VerificationToolkit(log_dir=Path(temp_dir))
            
            log_file = toolkit.init_workflow_log("test_workflow")
            
            assert toolkit.workflow_id == "test_workflow"
            assert toolkit.log_file == log_file
            assert log_file.exists()
            
            content = log_file.read_text()
            assert "=== Workflow test_workflow ===" in content
            assert "Started:" in content

    def test_log_event_no_log_file(self):
        """Test logging event when no log file is set."""
        toolkit = VerificationToolkit()
        
        # Should not raise an exception
        toolkit.log_event("TEST", {"data": "value"})

    def test_log_event_with_log_file(self):
        """Test logging event with active log file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            toolkit = VerificationToolkit(log_dir=Path(temp_dir))
            toolkit.init_workflow_log("test_workflow")
            
            toolkit.log_event("TEST_EVENT", {"key": "value", "number": 42})
            
            content = toolkit.log_file.read_text()
            assert "TEST_EVENT" in content
            assert '"key": "value"' in content
            assert '"number": 42' in content

    @patch.object(VerificationToolkit, 'get_location_info')
    @patch.object(VerificationToolkit, 'get_process_info')
    @patch.object(VerificationToolkit, 'get_network_info')
    @patch.object(VerificationToolkit, 'get_file_info')
    @patch.object(VerificationToolkit, 'take_screenshot')
    def test_capture_system_state(self, mock_screenshot, mock_file_info, mock_network_info, mock_process_info, mock_location_info):
        """Test capturing complete system state."""
        toolkit = VerificationToolkit()
        
        # Mock return values
        mock_location_info.return_value = {"app_name": "TestApp"}
        mock_process_info.return_value = {"mcp_server": True}
        mock_network_info.return_value = {"websocket_port_8675": True}
        mock_file_info.return_value = {"progress_dir_exists": True}
        mock_screenshot.return_value = Path("/test/screenshot.png")
        
        state = toolkit.capture_system_state()
        
        assert "timestamp" in state
        assert "datetime" in state
        assert state["location"] == {"app_name": "TestApp"}
        assert state["processes"] == {"mcp_server": True}
        assert state["network"] == {"websocket_port_8675": True}
        assert state["files"] == {"progress_dir_exists": True}
        assert "screenshots" in state

    @patch('subprocess.run')
    def test_get_location_info_success(self, mock_run):
        """Test getting location info successfully."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="TestApp|Test Window|2"
        )
        
        location = toolkit.get_location_info()
        
        assert location["app_name"] == "TestApp"
        assert location["window_title"] == "Test Window"
        assert location["window_count"] == 2
        assert location["is_iterm"] is False
        assert location["iterm_info"] is None

    @patch('subprocess.run')
    @patch.object(VerificationToolkit, 'get_iterm_info')
    def test_get_location_info_iterm(self, mock_iterm_info, mock_run):
        """Test getting location info for iTerm2."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="iTerm2|Terminal|1"
        )
        mock_iterm_info.return_value = {"current_window": 1, "current_tab": 2}
        
        location = toolkit.get_location_info()
        
        assert location["app_name"] == "iTerm2"
        assert location["is_iterm"] is True
        assert location["iterm_info"] == {"current_window": 1, "current_tab": 2}

    @patch('subprocess.run')
    def test_get_location_info_failure(self, mock_run):
        """Test getting location info when script fails."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(returncode=1)
        
        location = toolkit.get_location_info()
        
        assert location["app_name"] == "Error"
        assert location["window_title"] == "Could not determine"

    @patch('subprocess.run')
    def test_get_location_info_exception(self, mock_run):
        """Test getting location info when exception occurs."""
        toolkit = VerificationToolkit()
        
        mock_run.side_effect = Exception("Test error")
        
        with patch.object(toolkit, 'log_event') as mock_log:
            location = toolkit.get_location_info()
        
        assert location["app_name"] == "Error"
        mock_log.assert_called_once()

    @patch('subprocess.run')
    def test_get_iterm_info_success(self, mock_run):
        """Test getting iTerm2 info successfully."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="1|2|3|4"
        )
        
        iterm_info = toolkit.get_iterm_info()
        
        assert iterm_info["current_window"] == 1
        assert iterm_info["current_tab"] == 2
        assert iterm_info["total_windows"] == 3
        assert iterm_info["total_tabs"] == 4

    @patch('subprocess.run')
    def test_get_iterm_info_failure(self, mock_run):
        """Test getting iTerm2 info when script fails."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(returncode=1)
        
        iterm_info = toolkit.get_iterm_info()
        
        assert iterm_info is None

    @patch.object(VerificationToolkit, 'check_process_pattern')
    @patch.object(VerificationToolkit, 'get_matching_processes')
    def test_get_process_info(self, mock_matching_processes, mock_check_pattern):
        """Test getting process information."""
        toolkit = VerificationToolkit()
        
        mock_check_pattern.side_effect = lambda pattern: pattern == "crackerjack.*mcp"
        mock_matching_processes.side_effect = lambda pattern: [{"pid": 123}] if "python" in pattern else []
        
        processes = toolkit.get_process_info()
        
        assert processes["mcp_server"] is True
        assert processes["websocket_server"] is False
        assert processes["all_python"] == 1

    @patch('crackerjack.verification_toolkit.PSUTIL_AVAILABLE', True)
    def test_check_process_pattern_psutil(self):
        """Test checking process pattern with psutil."""
        toolkit = VerificationToolkit()
        
        # Mock psutil
        mock_proc = Mock()
        mock_proc.info = {"pid": 123, "name": "python", "cmdline": ["python", "-m", "crackerjack", "--mcp"]}
        
        with patch('psutil.process_iter', return_value=[mock_proc]):
            result = toolkit.check_process_pattern("crackerjack.*mcp")
        
        assert result is True

    @patch('crackerjack.verification_toolkit.PSUTIL_AVAILABLE', False)
    @patch('subprocess.run')
    def test_check_process_pattern_fallback(self, mock_run):
        """Test checking process pattern with pgrep fallback."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(returncode=0)
        
        result = toolkit.check_process_pattern("test_pattern")
        
        assert result is True
        mock_run.assert_called_once_with(
            ["pgrep", "-f", "test_pattern"], 
            capture_output=True, 
            text=True, 
            timeout=5
        )

    @patch('crackerjack.verification_toolkit.PSUTIL_AVAILABLE', True)
    def test_get_matching_processes_psutil(self):
        """Test getting matching processes with psutil."""
        toolkit = VerificationToolkit()
        
        # Mock psutil
        mock_proc = Mock()
        mock_proc.info = {
            "pid": 123,
            "name": "python",
            "cmdline": ["python", "-m", "test"],
            "cpu_percent": 1.5,
            "memory_percent": 2.0
        }
        
        with patch('psutil.process_iter', return_value=[mock_proc]):
            processes = toolkit.get_matching_processes("python")
        
        assert len(processes) == 1
        assert processes[0]["pid"] == 123
        assert processes[0]["name"] == "python"

    @patch('crackerjack.verification_toolkit.PSUTIL_AVAILABLE', False)
    @patch('subprocess.run')
    def test_get_matching_processes_fallback(self, mock_run):
        """Test getting matching processes with ps fallback."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="USER  PID %CPU %MEM    VSZ   RSS TTY STAT START TIME COMMAND\n"
                   "user  123  1.0  2.0  12345  6789 ?   S   10:00  0:01 python -m test"
        )
        
        processes = toolkit.get_matching_processes("python")
        
        assert len(processes) == 1
        assert processes[0]["pid"] == 123

    @patch.object(VerificationToolkit, 'check_port_listening')
    @patch.object(VerificationToolkit, 'test_localhost_connection')
    @patch.object(VerificationToolkit, 'get_listening_ports')
    def test_get_network_info(self, mock_listening_ports, mock_localhost, mock_port_check):
        """Test getting network information."""
        toolkit = VerificationToolkit()
        
        mock_port_check.return_value = True
        mock_localhost.return_value = True
        mock_listening_ports.return_value = [8675, 8080]
        
        with patch('crackerjack.verification_toolkit.WEBSOCKETS_AVAILABLE', False):
            network_info = toolkit.get_network_info()
        
        assert network_info["websocket_port_8675"] is True
        assert network_info["localhost_accessible"] is True
        assert network_info["open_ports"] == [8675, 8080]
        assert network_info["websocket_responsive"] == "websockets_module_unavailable"

    def test_check_port_listening_success(self):
        """Test checking if port is listening successfully."""
        toolkit = VerificationToolkit()
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value.__enter__.return_value = mock_sock
            
            result = toolkit.check_port_listening(8675)
        
        assert result is True

    def test_check_port_listening_failure(self):
        """Test checking if port is listening when it fails."""
        toolkit = VerificationToolkit()
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 1
            mock_socket.return_value.__enter__.return_value = mock_sock
            
            result = toolkit.check_port_listening(8675)
        
        assert result is False

    @patch('crackerjack.verification_toolkit.WEBSOCKETS_AVAILABLE', True)
    async def test_websocket_connection_success(self):
        """Test WebSocket connection test success."""
        toolkit = VerificationToolkit()
        
        with patch('websockets.connect') as mock_connect:
            mock_ws = Mock()
            mock_ws.send = Mock()
            mock_ws.recv = Mock(return_value='{"response": "pong"}')
            mock_connect.return_value.__aenter__.return_value = mock_ws
            
            result = await toolkit.test_websocket_connection()
        
        assert result is True

    @patch('crackerjack.verification_toolkit.WEBSOCKETS_AVAILABLE', False)
    async def test_websocket_connection_unavailable(self):
        """Test WebSocket connection when module unavailable."""
        toolkit = VerificationToolkit()
        
        result = await toolkit.test_websocket_connection()
        
        assert result is False

    def test_test_localhost_connection_success(self):
        """Test localhost connection success."""
        toolkit = VerificationToolkit()
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            
            result = toolkit.test_localhost_connection()
        
        assert result is True

    def test_test_localhost_connection_fallback(self):
        """Test localhost connection with ping fallback."""
        toolkit = VerificationToolkit()
        
        with patch('socket.socket', side_effect=Exception("Socket error")):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                
                result = toolkit.test_localhost_connection()
        
        assert result is True

    @patch('crackerjack.verification_toolkit.PSUTIL_AVAILABLE', True)
    def test_get_listening_ports_psutil(self):
        """Test getting listening ports with psutil."""
        toolkit = VerificationToolkit()
        
        mock_conn = Mock()
        mock_conn.status = 'LISTEN'  # This will need to match psutil.CONN_LISTEN
        mock_conn.laddr = Mock()
        mock_conn.laddr.port = 8675
        
        with patch('psutil.net_connections', return_value=[mock_conn]):
            with patch('psutil.CONN_LISTEN', 'LISTEN'):
                ports = toolkit.get_listening_ports()
        
        assert 8675 in ports

    @patch('crackerjack.verification_toolkit.PSUTIL_AVAILABLE', False)
    @patch('subprocess.run')
    def test_get_listening_ports_fallback(self, mock_run):
        """Test getting listening ports with netstat fallback."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="tcp4  0  0  127.0.0.1:8675  *.*  LISTEN\ntcp4  0  0  *:8080  *.*  LISTEN"
        )
        
        ports = toolkit.get_listening_ports()
        
        assert 8675 in ports
        assert 8080 in ports

    @patch.object(VerificationToolkit, 'list_progress_files')
    @patch.object(VerificationToolkit, 'get_active_job_ids')
    @patch.object(VerificationToolkit, 'test_temp_dir_writable')
    def test_get_file_info(self, mock_writable, mock_job_ids, mock_progress_files):
        """Test getting file information."""
        toolkit = VerificationToolkit()
        
        mock_progress_files.return_value = ["job-123.json", "job-456.json"]
        mock_job_ids.return_value = ["123", "456"]
        mock_writable.return_value = True
        
        file_info = toolkit.get_file_info()
        
        assert file_info["progress_files"] == ["job-123.json", "job-456.json"]
        assert file_info["active_job_ids"] == ["123", "456"]
        assert file_info["temp_dir_writeable"] is True

    def test_list_progress_files_no_dir(self):
        """Test listing progress files when directory doesn't exist."""
        toolkit = VerificationToolkit()
        
        files = toolkit.list_progress_files()
        
        assert files == []

    def test_list_progress_files_with_files(self):
        """Test listing progress files with existing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            progress_dir = Path(temp_dir) / "crackerjack-mcp-progress"
            progress_dir.mkdir()
            
            # Create test files
            (progress_dir / "job-123.json").write_text("{}")
            (progress_dir / "job-456.json").write_text("{}")
            (progress_dir / "other.txt").write_text("not a job file")
            
            toolkit = VerificationToolkit()
            
            with patch('tempfile.gettempdir', return_value=temp_dir):
                files = toolkit.list_progress_files()
        
        assert len(files) == 2
        assert "job-123.json" in files
        assert "job-456.json" in files

    def test_get_active_job_ids(self):
        """Test extracting active job IDs from filenames."""
        toolkit = VerificationToolkit()
        
        with patch.object(toolkit, 'list_progress_files', return_value=["job-abc123.json", "job-def456.json", "other.txt"]):
            job_ids = toolkit.get_active_job_ids()
        
        assert job_ids == ["abc123", "def456"]

    def test_test_temp_dir_writable_success(self):
        """Test temp directory writability check success."""
        toolkit = VerificationToolkit()
        
        result = toolkit.test_temp_dir_writable()
        
        # Should be True on most systems
        assert isinstance(result, bool)

    def test_test_temp_dir_writable_failure(self):
        """Test temp directory writability check failure."""
        toolkit = VerificationToolkit()
        
        with patch('pathlib.Path.write_text', side_effect=PermissionError("Permission denied")):
            result = toolkit.test_temp_dir_writable()
        
        assert result is False

    @patch('subprocess.run')
    def test_take_screenshot_success(self, mock_run):
        """Test taking screenshot successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            toolkit = VerificationToolkit(log_dir=Path(temp_dir))
            
            mock_run.return_value = Mock(returncode=0)
            
            # Create a fake screenshot file
            expected_path = None
            def create_screenshot_file(*args, **kwargs):
                nonlocal expected_path
                expected_path = Path(args[0][2])  # screencapture -x <path>
                expected_path.write_text("fake screenshot")
                return Mock(returncode=0)
            
            mock_run.side_effect = create_screenshot_file
            
            result = toolkit.take_screenshot("test")
        
        assert result is not None
        assert result == expected_path
        assert "screenshot_test_" in result.name

    @patch('subprocess.run')
    def test_take_screenshot_failure(self, mock_run):
        """Test taking screenshot failure."""
        toolkit = VerificationToolkit()
        
        mock_run.return_value = Mock(returncode=1)
        
        with patch.object(toolkit, 'log_event') as mock_log:
            result = toolkit.take_screenshot("test")
        
        assert result is None
        mock_log.assert_called_once()

    @patch.object(VerificationToolkit, 'get_location_info')
    def test_verify_window_switch_not_iterm(self, mock_location):
        """Test verifying window switch when not in iTerm2."""
        toolkit = VerificationToolkit()
        
        mock_location.return_value = {
            "is_iterm": False,
            "app_name": "TestApp"
        }
        
        result = toolkit.verify_window_switch(1, 2)
        
        assert result["success"] is False
        assert result["reason"] == "Not in iTerm2"
        assert result["current_app"] == "TestApp"

    @patch.object(VerificationToolkit, 'get_location_info')
    def test_verify_window_switch_success(self, mock_location):
        """Test successful window switch verification."""
        toolkit = VerificationToolkit()
        
        mock_location.return_value = {
            "is_iterm": True,
            "iterm_info": {
                "current_window": 1,
                "current_tab": 2
            }
        }
        
        result = toolkit.verify_window_switch(1, 2)
        
        assert result["success"] is True
        assert result["reason"] == "Success"

    @patch.object(VerificationToolkit, 'get_location_info')
    def test_verify_window_switch_mismatch(self, mock_location):
        """Test window switch verification with mismatch."""
        toolkit = VerificationToolkit()
        
        mock_location.return_value = {
            "is_iterm": True,
            "iterm_info": {
                "current_window": 2,
                "current_tab": 3
            }
        }
        
        result = toolkit.verify_window_switch(1, 2)
        
        assert result["success"] is False
        assert result["reason"] == "Window/tab mismatch"

    @patch.object(VerificationToolkit, 'capture_system_state')
    @patch.object(VerificationToolkit, 'log_event')
    def test_execute_with_verification_success(self, mock_log, mock_capture):
        """Test executing action with verification successfully."""
        toolkit = VerificationToolkit()
        
        mock_capture.side_effect = [{"state": "pre"}, {"state": "post"}]
        
        def test_action(x, y):
            return x + y
        
        result = toolkit.execute_with_verification("test_action", test_action, 5, y=10)
        
        assert result["success"] is True
        assert result["result"] == 15
        assert result["error"] is None
        assert result["pre_state"] == {"state": "pre"}
        assert result["post_state"] == {"state": "post"}
        assert mock_log.call_count == 2

    @patch.object(VerificationToolkit, 'capture_system_state')
    @patch.object(VerificationToolkit, 'log_event')
    def test_execute_with_verification_failure(self, mock_log, mock_capture):
        """Test executing action with verification when action fails."""
        toolkit = VerificationToolkit()
        
        mock_capture.side_effect = [{"state": "pre"}, {"state": "post"}]
        
        def failing_action():
            raise ValueError("Test error")
        
        result = toolkit.execute_with_verification("failing_action", failing_action)
        
        assert result["success"] is False
        assert result["result"] is None
        assert "Test error" in result["error"]

    def test_generate_verification_report(self):
        """Test generating verification report."""
        toolkit = VerificationToolkit()
        
        action_result = {
            "action_id": "test_123",
            "success": True,
            "error": None,
            "execution_time": 1.5,
            "pre_state": {
                "location": {
                    "app_name": "App1",
                    "window_title": "Window1",
                    "is_iterm": False
                },
                "processes": {"mcp_server": False}
            },
            "post_state": {
                "location": {
                    "app_name": "App2",
                    "window_title": "Window2",
                    "is_iterm": False
                },
                "processes": {"mcp_server": True}
            }
        }
        
        report = toolkit.generate_verification_report(action_result)
        
        assert "Action ID: test_123" in report
        assert "Success: ✅" in report
        assert "Execution Time: 1.50s" in report
        assert "Before: App1 - Window1" in report
        assert "After:  App2 - Window2" in report
        assert "mcp_server: Started" in report


class TestConvenienceFunctions:
    """Test global convenience functions."""

    @patch('crackerjack.verification_toolkit._default_toolkit', None)
    def test_get_toolkit_creates_instance(self):
        """Test that get_toolkit creates a new instance."""
        toolkit = get_toolkit()
        
        assert isinstance(toolkit, VerificationToolkit)
        
        # Should return the same instance on second call
        toolkit2 = get_toolkit()
        assert toolkit is toolkit2

    @patch.object(VerificationToolkit, 'capture_system_state')
    def test_capture_state(self, mock_capture):
        """Test global capture_state function."""
        mock_capture.return_value = {"test": "state"}
        
        result = capture_state()
        
        assert result == {"test": "state"}

    @patch.object(VerificationToolkit, 'verify_window_switch')
    def test_verify_location(self, mock_verify):
        """Test global verify_location function."""
        mock_verify.return_value = {"success": True}
        
        result = verify_location(1, 2)
        
        assert result is True
        mock_verify.assert_called_once_with(1, 2)

    @patch.object(VerificationToolkit, 'take_screenshot')
    def test_take_screenshot(self, mock_screenshot):
        """Test global take_screenshot function."""
        mock_screenshot.return_value = Path("/test/screenshot.png")
        
        result = take_screenshot("test")
        
        assert result == Path("/test/screenshot.png")
        mock_screenshot.assert_called_once_with("test")


class TestIntegration:
    """Integration tests for verification toolkit."""

    def test_full_verification_cycle(self):
        """Test a complete verification cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            toolkit = VerificationToolkit(log_dir=Path(temp_dir))
            toolkit.init_workflow_log("integration_test")
            
            def test_operation(value):
                return value * 2
            
            # Mock system state capture to avoid actual system calls
            with patch.object(toolkit, 'capture_system_state') as mock_capture:
                mock_capture.side_effect = [
                    {"location": {"app_name": "Before"}, "processes": {"test": False}},
                    {"location": {"app_name": "After"}, "processes": {"test": True}}
                ]
                
                result = toolkit.execute_with_verification("test_op", test_operation, 5)
            
            # Verify the operation succeeded
            assert result["success"] is True
            assert result["result"] == 10
            
            # Verify states were captured
            assert result["pre_state"]["location"]["app_name"] == "Before"
            assert result["post_state"]["location"]["app_name"] == "After"
            
            # Verify log file was created and contains events
            assert toolkit.log_file.exists()
            log_content = toolkit.log_file.read_text()
            assert "PRE_ACTION" in log_content
            assert "POST_ACTION" in log_content
            
            # Generate and verify report
            report = toolkit.generate_verification_report(result)
            assert "Success: ✅" in report
            assert "test: Started" in report

    def test_error_handling_robustness(self):
        """Test error handling in various failure scenarios."""
        toolkit = VerificationToolkit()
        
        # Test with invalid operation
        def invalid_operation():
            raise RuntimeError("Simulated failure")
        
        with patch.object(toolkit, 'capture_system_state') as mock_capture:
            mock_capture.return_value = {"test": "state"}
            
            result = toolkit.execute_with_verification("invalid_op", invalid_operation)
        
        assert result["success"] is False
        assert "Simulated failure" in result["error"]
        assert result["result"] is None

    def test_screenshot_integration(self):
        """Test screenshot functionality integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            toolkit = VerificationToolkit(log_dir=Path(temp_dir))
            
            # Mock successful screencapture
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                
                # Create mock screenshot file
                def create_mock_file(*args, **kwargs):
                    Path(args[0][2]).write_text("mock screenshot data")
                    return Mock(returncode=0)
                
                mock_run.side_effect = create_mock_file
                
                screenshot_path = toolkit.take_screenshot("integration_test")
            
            assert screenshot_path is not None
            assert screenshot_path.exists()
            assert "screenshot_integration_test_" in screenshot_path.name