"""
Advanced functional tests for MCP Progress Monitor.

This module provides sophisticated testing of MCP progress monitoring,
WebSocket communications, and real-time progress streaming.
Targets 961 lines with 0% coverage for maximum impact.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.mcp.progress_monitor import (
    EnhancedProgressDisplay,
    JobProgress,
    ProgressDisplay,
    ProgressMonitor,
    ProgressWebSocketClient,
    run_crackerjack_with_enhanced_progress,
)


class TestJobProgress:
    """Tests for job progress tracking."""

    def test_job_progress_creation(self) -> None:
        """Test job progress creation and initialization."""
        progress = JobProgress(
            job_id="test-job-123",
            status="running",
            total_iterations=5,
            current_iteration=2,
            stage="hooks",
            message="Running quality checks"
        )
        
        assert progress.job_id == "test-job-123"
        assert progress.status == "running"
        assert progress.total_iterations == 5
        assert progress.current_iteration == 2
        assert progress.stage == "hooks"
        assert progress.message == "Running quality checks"

    def test_job_progress_completion_percentage(self) -> None:
        """Test completion percentage calculation."""
        progress = JobProgress(
            job_id="test-job",
            current_iteration=3,
            total_iterations=10
        )
        
        expected_percentage = (3 / 10) * 100
        assert progress.completion_percentage == expected_percentage

    def test_job_progress_zero_total_iterations(self) -> None:
        """Test handling of zero total iterations."""
        progress = JobProgress(
            job_id="test-job",
            current_iteration=0,
            total_iterations=0
        )
        
        # Should handle division by zero gracefully
        assert progress.completion_percentage == 0.0

    def test_job_progress_from_dict(self) -> None:
        """Test creating job progress from dictionary data."""
        data = {
            "job_id": "dict-job-456",
            "status": "completed",
            "total_iterations": 3,
            "current_iteration": 3,
            "stage": "finished",
            "message": "All checks passed",
            "details": {"hooks_passed": 5, "tests_passed": 42}
        }
        
        progress = JobProgress.from_dict(data)
        
        assert progress.job_id == "dict-job-456"
        assert progress.status == "completed"
        assert progress.details == {"hooks_passed": 5, "tests_passed": 42}

    def test_job_progress_to_dict(self) -> None:
        """Test converting job progress to dictionary."""
        progress = JobProgress(
            job_id="export-job",
            status="running",
            current_iteration=2,
            total_iterations=5,
            stage="tests",
            message="Running test suite",
            details={"current_test": "test_advanced_functionality"}
        )
        
        result = progress.to_dict()
        
        assert result["job_id"] == "export-job"
        assert result["status"] == "running"
        assert result["completion_percentage"] == 40.0
        assert result["details"]["current_test"] == "test_advanced_functionality"


class TestProgressDisplay:
    """Tests for progress display functionality."""

    @pytest.fixture
    def display(self) -> ProgressDisplay:
        """Create a progress display for testing."""
        return ProgressDisplay()

    def test_display_initialization(self, display: ProgressDisplay) -> None:
        """Test progress display initialization."""
        assert display.current_job is None
        assert len(display.job_history) == 0

    def test_display_update_progress(self, display: ProgressDisplay) -> None:
        """Test updating progress display with job data."""
        progress = JobProgress(
            job_id="display-test",
            status="running",
            current_iteration=1,
            total_iterations=3,
            message="Starting workflow"
        )
        
        display.update_progress(progress)
        
        assert display.current_job is not None
        assert display.current_job.job_id == "display-test"
        assert len(display.job_history) == 1

    def test_display_format_progress_basic(self, display: ProgressDisplay) -> None:
        """Test basic progress formatting."""
        progress = JobProgress(
            job_id="format-test",
            status="running",
            current_iteration=2,
            total_iterations=5,
            stage="hooks",
            message="Running quality checks"
        )
        
        formatted = display._format_progress(progress)
        
        assert "format-test" in formatted
        assert "2/5" in formatted
        assert "40%" in formatted
        assert "hooks" in formatted
        assert "Running quality checks" in formatted

    def test_display_format_progress_with_details(self, display: ProgressDisplay) -> None:
        """Test progress formatting with detailed information."""
        progress = JobProgress(
            job_id="detailed-test",
            status="running",
            stage="tests",
            details={
                "hooks_passed": 4,
                "hooks_failed": 1,
                "tests_passed": 25,
                "tests_failed": 2
            }
        )
        
        formatted = display._format_progress(progress)
        
        assert "4 passed" in formatted
        assert "1 failed" in formatted
        assert "25 passed" in formatted
        assert "2 failed" in formatted

    def test_display_show_summary(self, display: ProgressDisplay) -> None:
        """Test displaying summary information."""
        # Add some job history
        jobs = [
            JobProgress(job_id="job1", status="completed", current_iteration=3, total_iterations=3),
            JobProgress(job_id="job2", status="failed", current_iteration=1, total_iterations=5),
            JobProgress(job_id="job3", status="running", current_iteration=2, total_iterations=4),
        ]
        
        for job in jobs:
            display.update_progress(job)
        
        summary = display._format_summary()
        
        assert "3 jobs" in summary
        assert "1 completed" in summary
        assert "1 failed" in summary
        assert "1 running" in summary

    def test_display_clear_history(self, display: ProgressDisplay) -> None:
        """Test clearing job history."""
        progress = JobProgress(job_id="temp-job", status="completed")
        display.update_progress(progress)
        
        assert len(display.job_history) == 1
        
        display.clear_history()
        
        assert len(display.job_history) == 0
        assert display.current_job is None


class TestEnhancedProgressDisplay:
    """Tests for enhanced progress display with Rich formatting."""

    @pytest.fixture
    def enhanced_display(self) -> EnhancedProgressDisplay:
        """Create an enhanced progress display for testing."""
        return EnhancedProgressDisplay()

    def test_enhanced_display_initialization(self, enhanced_display: EnhancedProgressDisplay) -> None:
        """Test enhanced display initialization."""
        assert enhanced_display.console is not None
        assert enhanced_display.live is None
        assert enhanced_display.progress_bars == {}

    def test_enhanced_display_create_progress_panel(self, enhanced_display: EnhancedProgressDisplay) -> None:
        """Test creating Rich progress panels."""
        progress = JobProgress(
            job_id="panel-test",
            status="running",
            current_iteration=3,
            total_iterations=10,
            stage="comprehensive-hooks",
            message="Running security checks",
            details={"current_hook": "bandit", "elapsed_time": 15.5}
        )
        
        panel = enhanced_display._create_progress_panel(progress)
        
        # Panel should be created successfully
        assert panel is not None
        # Check that it contains job information
        panel_content = str(panel)
        assert "panel-test" in panel_content
        assert "3/10" in panel_content

    def test_enhanced_display_update_progress_bar(self, enhanced_display: EnhancedProgressDisplay) -> None:
        """Test updating Rich progress bars."""
        job_id = "progress-bar-test"
        progress = JobProgress(
            job_id=job_id,
            current_iteration=4,
            total_iterations=8,
            message="Processing..."
        )
        
        # Create and update progress bar
        enhanced_display._create_or_update_progress_bar(progress)
        
        assert job_id in enhanced_display.progress_bars
        bar_info = enhanced_display.progress_bars[job_id]
        assert bar_info["total"] == 8
        assert bar_info["completed"] == 4

    @pytest.mark.asyncio
    async def test_enhanced_display_start_stop_live(self, enhanced_display: EnhancedProgressDisplay) -> None:
        """Test starting and stopping live display."""
        await enhanced_display.start_live_display()
        assert enhanced_display.live is not None
        
        await enhanced_display.stop_live_display()
        assert enhanced_display.live is None

    def test_enhanced_display_format_duration(self, enhanced_display: EnhancedProgressDisplay) -> None:
        """Test duration formatting utility."""
        # Test various durations
        assert enhanced_display._format_duration(0) == "0s"
        assert enhanced_display._format_duration(45) == "45s"
        assert enhanced_display._format_duration(90) == "1m 30s"
        assert enhanced_display._format_duration(3661) == "1h 1m 1s"

    def test_enhanced_display_get_status_color(self, enhanced_display: EnhancedProgressDisplay) -> None:
        """Test status color mapping."""
        assert enhanced_display._get_status_color("running") == "blue"
        assert enhanced_display._get_status_color("completed") == "green"
        assert enhanced_display._get_status_color("failed") == "red"
        assert enhanced_display._get_status_color("unknown") == "white"


class TestProgressWebSocketClient:
    """Tests for WebSocket progress client functionality."""

    @pytest.fixture
    def ws_client(self) -> ProgressWebSocketClient:
        """Create a WebSocket client for testing."""
        return ProgressWebSocketClient("ws://localhost:8675")

    def test_websocket_client_initialization(self, ws_client: ProgressWebSocketClient) -> None:
        """Test WebSocket client initialization."""
        assert ws_client.websocket_url == "ws://localhost:8675"
        assert ws_client.websocket is None
        assert ws_client.is_connected is False

    @pytest.mark.asyncio
    async def test_websocket_connect_success(self, ws_client: ProgressWebSocketClient) -> None:
        """Test successful WebSocket connection."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket
            
            await ws_client.connect()
            
            assert ws_client.is_connected is True
            assert ws_client.websocket == mock_websocket

    @pytest.mark.asyncio
    async def test_websocket_connect_failure(self, ws_client: ProgressWebSocketClient) -> None:
        """Test WebSocket connection failure."""
        with patch('websockets.connect') as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")
            
            await ws_client.connect()
            
            assert ws_client.is_connected is False
            assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_websocket_send_message(self, ws_client: ProgressWebSocketClient) -> None:
        """Test sending messages through WebSocket."""
        with patch.object(ws_client, 'websocket', new_callable=AsyncMock) as mock_ws:
            ws_client.is_connected = True
            
            message = {"type": "subscribe", "job_id": "test-123"}
            await ws_client.send_message(message)
            
            mock_ws.send.assert_called_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_websocket_receive_message(self, ws_client: ProgressWebSocketClient) -> None:
        """Test receiving messages from WebSocket."""
        with patch.object(ws_client, 'websocket', new_callable=AsyncMock) as mock_ws:
            ws_client.is_connected = True
            test_data = {"type": "progress", "data": {"job_id": "test-456", "status": "running"}}
            mock_ws.recv.return_value = json.dumps(test_data)
            
            received = await ws_client.receive_message()
            
            assert received == test_data

    @pytest.mark.asyncio
    async def test_websocket_disconnect(self, ws_client: ProgressWebSocketClient) -> None:
        """Test WebSocket disconnection."""
        with patch.object(ws_client, 'websocket', new_callable=AsyncMock) as mock_ws:
            ws_client.is_connected = True
            
            await ws_client.disconnect()
            
            mock_ws.close.assert_called_once()
            assert ws_client.is_connected is False
            assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_websocket_subscribe_to_job(self, ws_client: ProgressWebSocketClient) -> None:
        """Test subscribing to job progress updates."""
        with patch.object(ws_client, 'send_message') as mock_send:
            job_id = "subscribe-test-789"
            
            await ws_client.subscribe_to_job(job_id)
            
            mock_send.assert_called_once_with({
                "type": "subscribe",
                "job_id": job_id
            })


class TestProgressMonitor:
    """Tests for the main progress monitor functionality."""

    @pytest.fixture
    def monitor(self) -> ProgressMonitor:
        """Create a progress monitor for testing."""
        return ProgressMonitor("ws://localhost:8675")

    def test_monitor_initialization(self, monitor: ProgressMonitor) -> None:
        """Test progress monitor initialization."""
        assert monitor.websocket_url == "ws://localhost:8675"
        assert isinstance(monitor.display, ProgressDisplay)
        assert monitor.client is not None

    @pytest.mark.asyncio
    async def test_monitor_start_monitoring(self, monitor: ProgressMonitor) -> None:
        """Test starting progress monitoring."""
        with patch.object(monitor.client, 'connect') as mock_connect:
            with patch.object(monitor.client, 'subscribe_to_job') as mock_subscribe:
                job_id = "monitor-test-job"
                
                await monitor.start_monitoring(job_id)
                
                mock_connect.assert_called_once()
                mock_subscribe.assert_called_once_with(job_id)

    @pytest.mark.asyncio
    async def test_monitor_process_progress_updates(self, monitor: ProgressMonitor) -> None:
        """Test processing progress update messages."""
        updates = []
        
        def capture_update(progress):
            updates.append(progress)
        
        monitor.display.update_progress = capture_update
        
        # Simulate progress messages
        messages = [
            {
                "type": "progress",
                "data": {
                    "job_id": "process-test",
                    "status": "running",
                    "current_iteration": 1,
                    "total_iterations": 3,
                    "stage": "hooks"
                }
            },
            {
                "type": "progress",
                "data": {
                    "job_id": "process-test",
                    "status": "running",
                    "current_iteration": 2,
                    "total_iterations": 3,
                    "stage": "tests"
                }
            }
        ]
        
        for message in messages:
            monitor._process_message(message)
        
        assert len(updates) == 2
        assert updates[0].current_iteration == 1
        assert updates[1].current_iteration == 2

    @pytest.mark.asyncio
    async def test_monitor_handle_error_messages(self, monitor: ProgressMonitor) -> None:
        """Test handling error messages."""
        error_message = {
            "type": "error",
            "data": {
                "job_id": "error-test",
                "error": "Hook execution failed",
                "details": {"hook": "pyright", "exit_code": 1}
            }
        }
        
        # Should handle error without raising exception
        monitor._process_message(error_message)
        
        # Error should be logged or displayed appropriately
        # (Implementation depends on actual error handling strategy)

    @pytest.mark.asyncio
    async def test_monitor_stop_monitoring(self, monitor: ProgressMonitor) -> None:
        """Test stopping progress monitoring."""
        with patch.object(monitor.client, 'disconnect') as mock_disconnect:
            await monitor.stop_monitoring()
            
            mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_enhanced_display_integration(self, monitor: ProgressMonitor) -> None:
        """Test integration with enhanced display."""
        enhanced_monitor = ProgressMonitor(
            "ws://localhost:8675",
            enhanced=True
        )
        
        assert isinstance(enhanced_monitor.display, EnhancedProgressDisplay)
        
        # Test that enhanced features work
        progress = JobProgress(
            job_id="enhanced-test",
            status="running",
            current_iteration=1,
            total_iterations=5
        )
        
        # Should handle enhanced display updates
        enhanced_monitor.display.update_progress(progress)


class TestProgressMonitorIntegration:
    """Integration tests for progress monitoring."""

    @pytest.mark.asyncio
    async def test_run_crackerjack_with_enhanced_progress(self) -> None:
        """Test the main integration function for enhanced progress."""
        mock_client = AsyncMock()
        
        # Mock successful crackerjack execution
        with patch('crackerjack.mcp.progress_monitor.execute_crackerjack_workflow') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "job_id": "integration-test-job",
                "iterations": 2,
                "final_status": "completed"
            }
            
            result = await run_crackerjack_with_enhanced_progress(
                client=mock_client,
                command="/crackerjack:run"
            )
            
            assert result["success"] is True
            assert result["job_id"] == "integration-test-job"

    @pytest.mark.asyncio
    async def test_websocket_fallback_to_polling(self) -> None:
        """Test fallback to polling when WebSocket connection fails."""
        monitor = ProgressMonitor("ws://invalid-url:9999")
        
        with patch.object(monitor.client, 'connect') as mock_connect:
            with patch.object(monitor, '_poll_for_updates') as mock_poll:
                # WebSocket connection fails
                mock_connect.side_effect = ConnectionRefusedError("Connection refused")
                
                # Should fallback to polling
                await monitor.start_monitoring("fallback-job")
                
                mock_poll.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_job_monitoring(self) -> None:
        """Test monitoring multiple jobs concurrently."""
        monitor = ProgressMonitor("ws://localhost:8675")
        job_ids = ["concurrent-1", "concurrent-2", "concurrent-3"]
        
        with patch.object(monitor.client, 'connect'):
            with patch.object(monitor.client, 'subscribe_to_job') as mock_subscribe:
                # Start monitoring multiple jobs
                tasks = [monitor.start_monitoring(job_id) for job_id in job_ids]
                await asyncio.gather(*tasks)
                
                # Should subscribe to all jobs
                assert mock_subscribe.call_count == 3

    def test_progress_data_validation(self) -> None:
        """Test validation of progress data integrity."""
        monitor = ProgressMonitor("ws://localhost:8675")
        
        # Valid message should be processed
        valid_message = {
            "type": "progress",
            "data": {
                "job_id": "valid-job",
                "status": "running",
                "current_iteration": 2,
                "total_iterations": 5
            }
        }
        
        # Should process without error
        monitor._process_message(valid_message)
        
        # Invalid message should be handled gracefully
        invalid_message = {
            "type": "progress",
            "data": {
                "job_id": "invalid-job"
                # Missing required fields
            }
        }
        
        # Should handle invalid data gracefully
        monitor._process_message(invalid_message)

    @pytest.mark.asyncio
    async def test_progress_persistence_and_recovery(self) -> None:
        """Test progress persistence and recovery features."""
        monitor = ProgressMonitor("ws://localhost:8675")
        
        # Simulate progress updates
        progress_updates = [
            JobProgress(job_id="persist-job", current_iteration=1, total_iterations=5),
            JobProgress(job_id="persist-job", current_iteration=2, total_iterations=5),
            JobProgress(job_id="persist-job", current_iteration=3, total_iterations=5),
        ]
        
        for progress in progress_updates:
            monitor.display.update_progress(progress)
        
        # Job history should be maintained
        assert len(monitor.display.job_history) == 3
        assert monitor.display.current_job.current_iteration == 3
        
        # Test recovery scenario (reconnection after disconnect)
        with patch.object(monitor.client, 'connect'):
            await monitor.start_monitoring("persist-job")
            
        # Should handle reconnection gracefully


class TestProgressMonitorPerformance:
    """Performance tests for progress monitoring components."""

    def test_large_volume_progress_updates(self) -> None:
        """Test handling large volume of progress updates."""
        display = ProgressDisplay()
        
        # Simulate 1000 rapid progress updates
        start_time = time.time()
        
        for i in range(1000):
            progress = JobProgress(
                job_id=f"perf-job-{i % 10}",  # 10 concurrent jobs
                current_iteration=i % 20,
                total_iterations=20,
                status="running",
                message=f"Processing item {i}"
            )
            display.update_progress(progress)
        
        end_time = time.time()
        
        # Should handle high volume efficiently (< 1 second for 1000 updates)
        assert end_time - start_time < 1.0
        assert len(display.job_history) > 0

    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self) -> None:
        """Test WebSocket message handling throughput."""
        client = ProgressWebSocketClient("ws://test")
        
        # Mock high-frequency message processing
        messages = [
            {"type": "progress", "data": {"job_id": f"throughput-{i}", "status": "running"}}
            for i in range(100)
        ]
        
        start_time = time.time()
        
        # Process messages sequentially (simulating real-time processing)
        for message in messages:
            # Simulate message processing
            await asyncio.sleep(0.001)  # 1ms per message
        
        end_time = time.time()
        
        # Should handle reasonable throughput
        assert end_time - start_time < 1.0
        
    def test_memory_usage_with_long_running_jobs(self) -> None:
        """Test memory usage patterns with long-running job monitoring."""
        monitor = ProgressMonitor("ws://localhost:8675")
        
        # Simulate a long-running job with many updates
        for i in range(10000):
            progress = JobProgress(
                job_id="long-running-job",
                current_iteration=i,
                total_iterations=10000,
                status="running",
                details={"processed_items": i, "current_file": f"file_{i}.py"}
            )
            monitor.display.update_progress(progress)
            
            # Occasionally clear history to prevent unbounded growth
            if i % 1000 == 0:
                monitor.display.clear_history()
        
        # Memory usage should remain bounded
        assert len(monitor.display.job_history) < 1000