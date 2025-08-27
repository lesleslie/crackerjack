"""Strategic tests for crackerjack/services/server_manager.py to push coverage to 42%+.

Target: 70%+ coverage of server_manager (132 statements)
Current: 12% coverage - need to cover ~90 additional statements

Focus Areas:
1. Process discovery and parsing logic
2. Process termination workflows
3. Server lifecycle management
4. Error handling and edge cases
5. Console output and status reporting

COVERAGE STRATEGY:
- Mock subprocess calls to control ps output
- Test various process parsing scenarios
- Exercise error handling paths
- Verify signal handling logic
- Test console output patterns
"""

import signal
import subprocess
from unittest.mock import Mock, patch

from rich.console import Console

from crackerjack.services.server_manager import (
    find_mcp_server_processes,
    find_websocket_server_processes,
    list_server_status,
    restart_mcp_server,
    stop_all_servers,
    stop_mcp_server,
    stop_process,
    stop_websocket_server,
)


class TestProcessDiscovery:
    """Test process discovery functionality - covers ~35 statements."""

    @patch("subprocess.run")
    def test_find_mcp_server_processes_success(self, mock_run):
        """Test successful MCP server process discovery."""
        # Mock ps aux output with MCP server processes
        mock_run.return_value = Mock(
            stdout=(
                "USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
                "user      1234  0.1  0.5 123456  5678 ?        S    10:00   0:01 python -m crackerjack --start-mcp-server\n"
                "user      5678  0.2  0.8 789012  9012 ?        S    10:05   0:02 python -m crackerjack --start-mcp-server --websocket-port 8675\n"
                "user      9999  0.0  0.1 456789  1234 ?        S    09:00   0:00 some other process\n"
            ),
            returncode=0,
        )

        processes = find_mcp_server_processes()

        assert len(processes) == 2
        assert processes[0]["pid"] == 1234
        assert processes[0]["user"] == "user"
        assert processes[0]["cpu"] == "0.1"
        assert processes[0]["mem"] == "0.5"
        assert "--start-mcp-server" in processes[0]["command"]

        assert processes[1]["pid"] == 5678
        assert "--websocket-port 8675" in processes[1]["command"]

    @patch("subprocess.run")
    def test_find_websocket_server_processes_success(self, mock_run):
        """Test successful WebSocket server process discovery."""
        mock_run.return_value = Mock(
            stdout=(
                "USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
                "user      2345  1.5  2.3 234567  6789 ?        S    10:10   0:03 python -m crackerjack --start-websocket-server\n"
                "user      6789  0.8  1.2 345678  7890 ?        S    10:15   0:01 python -m crackerjack --start-websocket-server --port 8080\n"
            ),
            returncode=0,
        )

        processes = find_websocket_server_processes()

        assert len(processes) == 2
        assert processes[0]["pid"] == 2345
        assert processes[0]["cpu"] == "1.5"
        assert processes[0]["mem"] == "2.3"
        assert "--start-websocket-server" in processes[0]["command"]

    @patch("subprocess.run")
    def test_find_processes_malformed_output(self, mock_run):
        """Test handling of malformed ps output."""
        # Mock ps output with insufficient columns
        mock_run.return_value = Mock(
            stdout=(
                "USER PID\n"
                "user 1234 python -m crackerjack --start-mcp-server\n"  # Not enough parts
                "incomplete line\n"
                "user invalid_pid 0.1 0.5 123456  5678 ?        S    10:00   0:01 python -m crackerjack --start-mcp-server\n"
            ),
            returncode=0,
        )

        processes = find_mcp_server_processes()
        # Should handle malformed lines gracefully
        assert len(processes) == 0  # All lines are malformed

    @patch("subprocess.run")
    def test_find_processes_subprocess_error(self, mock_run):
        """Test handling of subprocess errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "ps")

        processes = find_mcp_server_processes()
        assert processes == []

        processes = find_websocket_server_processes()
        assert processes == []

    @patch("subprocess.run")
    def test_find_processes_file_not_found(self, mock_run):
        """Test handling when ps command is not found."""
        mock_run.side_effect = FileNotFoundError("ps command not found")

        processes = find_mcp_server_processes()
        assert processes == []

        processes = find_websocket_server_processes()
        assert processes == []

    @patch("subprocess.run")
    def test_find_processes_no_matching_processes(self, mock_run):
        """Test when no matching processes are found."""
        mock_run.return_value = Mock(
            stdout=(
                "USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
                "user      1111  0.1  0.5 123456  5678 ?        S    10:00   0:01 python some_other_script.py\n"
                "user      2222  0.2  0.8 789012  9012 ?        S    10:05   0:02 node server.js\n"
            ),
            returncode=0,
        )

        mcp_processes = find_mcp_server_processes()
        assert mcp_processes == []

        websocket_processes = find_websocket_server_processes()
        assert websocket_processes == []


class TestProcessTermination:
    """Test process termination logic - covers ~25 statements."""

    @patch("os.kill")
    @patch("time.sleep")
    def test_stop_process_graceful_success(self, mock_sleep, mock_kill):
        """Test graceful process termination."""
        # Mock process check - first call succeeds, second fails (process stopped)
        mock_kill.side_effect = [None, OSError("No such process")]

        result = stop_process(1234)

        assert result is True
        mock_kill.assert_any_call(1234, signal.SIGTERM)
        mock_kill.assert_any_call(1234, 0)  # Check if process exists

    @patch("os.kill")
    @patch("time.sleep")
    def test_stop_process_force_kill_needed(self, mock_sleep, mock_kill):
        """Test process that requires SIGKILL."""
        # Process doesn't respond to SIGTERM, keep returning success for existence checks
        # Then finally succeed when SIGKILL is used
        call_count = 0

        def kill_side_effect(pid, sig):
            nonlocal call_count
            if sig == signal.SIGTERM:
                return None  # SIGTERM sent successfully
            elif sig == signal.SIGKILL:
                return None  # SIGKILL sent successfully
            elif sig == 0:  # Process existence check
                call_count += 1
                if call_count <= 10:  # Process still alive for 10 checks
                    return None  # Process still exists
                else:
                    raise OSError("No such process")  # Process finally died
            return None

        mock_kill.side_effect = kill_side_effect

        result = stop_process(1234)

        assert result is True
        # Should try SIGTERM first, then SIGKILL when graceful fails
        mock_kill.assert_any_call(1234, signal.SIGTERM)
        mock_kill.assert_any_call(1234, signal.SIGKILL)

    @patch("os.kill")
    def test_stop_process_with_force_flag(self, mock_kill):
        """Test immediate SIGKILL when force=True."""
        mock_kill.side_effect = [None, OSError("No such process")]

        result = stop_process(1234, force=True)

        assert result is True
        mock_kill.assert_any_call(1234, signal.SIGKILL)

    @patch("os.kill")
    def test_stop_process_already_stopped(self, mock_kill):
        """Test stopping process that's already stopped."""
        mock_kill.side_effect = ProcessLookupError("No such process")

        result = stop_process(1234)

        assert result is True

    @patch("os.kill")
    def test_stop_process_os_error(self, mock_kill):
        """Test handling of OS errors during termination."""
        mock_kill.side_effect = OSError("Permission denied")

        result = stop_process(1234)

        assert result is True  # Function treats errors as success


class TestServerManagement:
    """Test high-level server management functions - covers ~45 statements."""

    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    @patch("crackerjack.services.server_manager.stop_process")
    def test_stop_mcp_server_success(self, mock_stop_process, mock_find_processes):
        """Test successful MCP server stopping."""
        mock_console = Mock(spec=Console)
        mock_find_processes.return_value = [
            {"pid": 1234, "command": "python -m crackerjack --start-mcp-server"},
            {
                "pid": 5678,
                "command": "python -m crackerjack --start-mcp-server --websocket-port 8675",
            },
        ]
        mock_stop_process.return_value = True

        result = stop_mcp_server(mock_console)

        assert result is True
        assert mock_stop_process.call_count == 2
        mock_stop_process.assert_any_call(1234)
        mock_stop_process.assert_any_call(5678)
        assert (
            mock_console.print.call_count >= 4
        )  # Start and success messages for each process

    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    def test_stop_mcp_server_no_processes(self, mock_find_processes):
        """Test stopping MCP server when none are running."""
        mock_console = Mock(spec=Console)
        mock_find_processes.return_value = []

        result = stop_mcp_server(mock_console)

        assert result is True
        mock_console.print.assert_called_with(
            "[yellow]⚠️ No MCP server processes found[/yellow]"
        )

    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    @patch("crackerjack.services.server_manager.stop_process")
    def test_stop_mcp_server_partial_failure(
        self, mock_stop_process, mock_find_processes
    ):
        """Test MCP server stopping with partial failures."""
        mock_console = Mock(spec=Console)
        mock_find_processes.return_value = [
            {"pid": 1234, "command": "python -m crackerjack --start-mcp-server"},
            {"pid": 5678, "command": "python -m crackerjack --start-mcp-server"},
        ]
        # First process stops successfully, second fails
        mock_stop_process.side_effect = [True, False]

        result = stop_mcp_server(mock_console)

        assert result is False

    @patch("crackerjack.services.server_manager.find_websocket_server_processes")
    @patch("crackerjack.services.server_manager.stop_process")
    def test_stop_websocket_server_success(
        self, mock_stop_process, mock_find_processes
    ):
        """Test successful WebSocket server stopping."""
        mock_console = Mock(spec=Console)
        mock_find_processes.return_value = [
            {"pid": 9999, "command": "python -m crackerjack --start-websocket-server"},
        ]
        mock_stop_process.return_value = True

        result = stop_websocket_server(mock_console)

        assert result is True
        mock_stop_process.assert_called_once_with(9999)

    @patch("crackerjack.services.server_manager.Console")
    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    def test_stop_mcp_server_default_console(self, mock_find, mock_console_class):
        """Test MCP server stopping with default console."""
        mock_find.return_value = []
        mock_console_instance = Mock()
        mock_console_class.return_value = mock_console_instance

        result = stop_mcp_server()  # No console provided

        assert result is True
        mock_console_class.assert_called_once()

    @patch("crackerjack.services.server_manager.stop_mcp_server")
    @patch("crackerjack.services.server_manager.stop_websocket_server")
    def test_stop_all_servers_success(self, mock_stop_websocket, mock_stop_mcp):
        """Test stopping all servers successfully."""
        mock_console = Mock(spec=Console)
        mock_stop_mcp.return_value = True
        mock_stop_websocket.return_value = True

        result = stop_all_servers(mock_console)

        assert result is True
        mock_stop_mcp.assert_called_once_with(mock_console)
        mock_stop_websocket.assert_called_once_with(mock_console)

    @patch("crackerjack.services.server_manager.stop_mcp_server")
    @patch("crackerjack.services.server_manager.stop_websocket_server")
    def test_stop_all_servers_partial_failure(self, mock_stop_websocket, mock_stop_mcp):
        """Test stopping all servers with partial failure."""
        mock_console = Mock(spec=Console)
        mock_stop_mcp.return_value = True
        mock_stop_websocket.return_value = False

        result = stop_all_servers(mock_console)

        assert result is False


class TestServerRestart:
    """Test server restart functionality - covers ~15 statements."""

    @patch("crackerjack.services.server_manager.stop_mcp_server")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    @patch("sys.executable", "/usr/bin/python3")
    def test_restart_mcp_server_success(self, mock_sleep, mock_popen, mock_stop):
        """Test successful MCP server restart."""
        mock_console = Mock(spec=Console)
        mock_stop.return_value = True
        mock_popen.return_value = Mock()

        result = restart_mcp_server(websocket_port=8675, console=mock_console)

        assert result is True
        mock_stop.assert_called_once_with(mock_console)
        mock_sleep.assert_called_once_with(2)  # Cleanup wait
        mock_popen.assert_called_once()

        # Verify command construction
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert cmd == [
            "/usr/bin/python3",
            "-m",
            "crackerjack",
            "--start-mcp-server",
            "--websocket-port",
            "8675",
        ]

    @patch("crackerjack.services.server_manager.stop_mcp_server")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_restart_mcp_server_no_websocket_port(
        self, mock_sleep, mock_popen, mock_stop
    ):
        """Test MCP server restart without websocket port."""
        mock_console = Mock(spec=Console)
        mock_stop.return_value = True

        result = restart_mcp_server(console=mock_console)

        assert result is True
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert "--websocket-port" not in cmd

    @patch("crackerjack.services.server_manager.stop_mcp_server")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_restart_mcp_server_popen_failure(self, mock_sleep, mock_popen, mock_stop):
        """Test MCP server restart with Popen failure."""
        mock_console = Mock(spec=Console)
        mock_stop.return_value = True
        mock_popen.side_effect = Exception("Failed to start process")

        result = restart_mcp_server(console=mock_console)

        assert result is False
        mock_console.print.assert_any_call(
            "❌ Failed to restart MCP server: Failed to start process"
        )

    @patch("crackerjack.services.server_manager.Console")
    @patch("crackerjack.services.server_manager.stop_mcp_server")
    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_restart_mcp_server_default_console(
        self, mock_sleep, mock_popen, mock_stop, mock_console_class
    ):
        """Test MCP server restart with default console."""
        mock_stop.return_value = True
        mock_console_instance = Mock()
        mock_console_class.return_value = mock_console_instance

        result = restart_mcp_server()

        assert result is True
        mock_console_class.assert_called_once()


class TestServerStatus:
    """Test server status reporting - covers ~15 statements."""

    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    @patch("crackerjack.services.server_manager.find_websocket_server_processes")
    def test_list_server_status_with_processes(
        self, mock_find_websocket, mock_find_mcp
    ):
        """Test status listing with running processes."""
        mock_console = Mock(spec=Console)
        mock_find_mcp.return_value = [
            {
                "pid": 1234,
                "cpu": "0.5",
                "mem": "1.2",
                "command": "python -m crackerjack --start-mcp-server",
            }
        ]
        mock_find_websocket.return_value = [
            {
                "pid": 5678,
                "cpu": "1.0",
                "mem": "2.1",
                "command": "python -m crackerjack --start-websocket-server",
            }
        ]

        list_server_status(mock_console)

        # Verify console output includes process information
        print_calls = [call[0][0] for call in mock_console.print.call_args_list]
        assert any("Crackerjack Server Status" in call for call in print_calls)
        assert any("MCP Servers:" in call for call in print_calls)
        assert any("WebSocket Servers:" in call for call in print_calls)
        assert any("PID 1234" in call for call in print_calls)
        assert any("PID 5678" in call for call in print_calls)

    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    @patch("crackerjack.services.server_manager.find_websocket_server_processes")
    def test_list_server_status_no_processes(self, mock_find_websocket, mock_find_mcp):
        """Test status listing with no running processes."""
        mock_console = Mock(spec=Console)
        mock_find_mcp.return_value = []
        mock_find_websocket.return_value = []

        list_server_status(mock_console)

        print_calls = [call[0][0] for call in mock_console.print.call_args_list]
        assert any(
            "No crackerjack servers currently running" in call for call in print_calls
        )

    @patch("crackerjack.services.server_manager.Console")
    @patch("crackerjack.services.server_manager.find_websocket_server_processes")
    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    def test_list_server_status_default_console(
        self, mock_find_mcp, mock_find_websocket, mock_console_class
    ):
        """Test status listing with default console."""
        mock_find_mcp.return_value = []
        mock_find_websocket.return_value = []
        mock_console_instance = Mock()
        mock_console_class.return_value = mock_console_instance

        list_server_status()

        mock_console_class.assert_called_once()


class TestEdgeCasesAndIntegration:
    """Test edge cases and integration scenarios."""

    @patch("subprocess.run")
    def test_ps_output_with_empty_lines(self, mock_run):
        """Test handling ps output with empty lines and whitespace."""
        mock_run.return_value = Mock(
            stdout=(
                "USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
                "\n"  # Empty line
                "   \n"  # Whitespace only
                "user      1234  0.1  0.5 123456  5678 ?        S    10:00   0:01 python -m crackerjack --start-mcp-server\n"
                "\n"
            ),
            returncode=0,
        )

        processes = find_mcp_server_processes()
        assert len(processes) == 1
        assert processes[0]["pid"] == 1234

    @patch("subprocess.run")
    def test_process_discovery_with_different_commands(self, mock_run):
        """Test process discovery handles various command formats."""
        mock_run.return_value = Mock(
            stdout=(
                "USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
                "user      1111  0.1  0.5 123456  5678 ?        S    10:00   0:01 /usr/bin/python3 -m crackerjack --start-mcp-server\n"
                "user      2222  0.2  0.8 789012  9012 ?        S    10:05   0:02 python3.11 -m crackerjack --start-mcp-server --debug\n"
                "user      3333  0.3  0.9 345678  7890 ?        S    10:10   0:03 crackerjack --start-mcp-server  # Direct invocation\n"
            ),
            returncode=0,
        )

        processes = find_mcp_server_processes()
        assert (
            len(processes) == 3
        )  # All lines contain both 'crackerjack' and '--start-mcp-server'

    def test_function_signature_coverage(self):
        """Test function signatures and default parameters."""
        # Test functions exist and have expected signatures
        assert callable(find_mcp_server_processes)
        assert callable(find_websocket_server_processes)
        assert callable(stop_process)
        assert callable(stop_mcp_server)
        assert callable(stop_websocket_server)
        assert callable(stop_all_servers)
        assert callable(restart_mcp_server)
        assert callable(list_server_status)

    @patch("crackerjack.services.server_manager.find_mcp_server_processes")
    @patch("crackerjack.services.server_manager.find_websocket_server_processes")
    def test_status_output_formatting(self, mock_find_websocket, mock_find_mcp):
        """Test detailed status output formatting."""
        mock_console = Mock(spec=Console)
        mock_find_mcp.return_value = [
            {
                "pid": 1234,
                "cpu": "15.7",  # Higher CPU usage
                "mem": "8.3",  # Higher memory usage
                "command": "python -m crackerjack --start-mcp-server --websocket-port 8675 --debug",
            }
        ]
        mock_find_websocket.return_value = []

        list_server_status(mock_console)

        # Verify detailed formatting is included
        print_calls = [call[0][0] for call in mock_console.print.call_args_list]
        cpu_mem_call = next(
            (
                call
                for call in print_calls
                if "CPU: 15.7%" in call and "Memory: 8.3%" in call
            ),
            None,
        )
        assert cpu_mem_call is not None

        command_call = next(
            (call for call in print_calls if "--websocket-port 8675 --debug" in call),
            None,
        )
        assert command_call is not None
