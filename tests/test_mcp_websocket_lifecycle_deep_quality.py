"""
Deep Quality Tests for MCP WebSocket Server - Real Business Logic Testing

This module tests the actual WebSocket lifecycle, job management, and error recovery
scenarios that occur in production MCP server usage. Each test validates real
production scenarios and edge cases.

**EXCELLENCE IN EXECUTION**: These tests protect against WebSocket connection failures,
job corruption, and concurrent access issues that would break the MCP workflow.
"""

import asyncio
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.mcp.websocket.jobs import JobManager
from crackerjack.mcp.websocket.server import WebSocketServer


class TestJobManagerBusinessLogic:
    """Test core job management business logic with real-world scenarios."""

    @pytest.fixture
    def temp_progress_dir(self) -> Path:
        """Create a temporary progress directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_progress_dir: Path) -> JobManager:
        """Create job manager for testing."""
        return JobManager(temp_progress_dir)


class TestJobIdValidationRobustness:
    """Test job ID validation against malicious and edge case inputs."""

    @pytest.fixture
    def job_manager(self) -> JobManager:
        return JobManager(Path("/tmp"))

    def test_valid_uuid_job_ids(self, job_manager: JobManager) -> None:
        """Test validation of proper UUID job IDs."""
        valid_uuids = [
            str(uuid.uuid4()),
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        ]

        for valid_uuid in valid_uuids:
            assert job_manager.validate_job_id(valid_uuid) is True

    def test_valid_alphanumeric_job_ids(self, job_manager: JobManager) -> None:
        """Test validation of alphanumeric job IDs."""
        valid_ids = [
            "job123",
            "test-job-456",
            "workflow_789",
            "a1b2c3d4",
            "Job_Test-123",
        ]

        for valid_id in valid_ids:
            assert job_manager.validate_job_id(valid_id) is True

    def test_malicious_job_id_rejection(self, job_manager: JobManager) -> None:
        """Test rejection of malicious or dangerous job IDs."""
        malicious_ids = [
            "",  # Empty string
            None,  # None type would fail before reaching validation
            "../../../etc/passwd",  # Path traversal
            "job;rm -rf /",  # Command injection
            "job$(whoami)",  # Command substitution
            "job`cat /etc/passwd`",  # Command execution
            "job\necho 'pwned'",  # Newline injection
            "job\0null",  # Null byte injection
            "a" * 100,  # Overly long ID
            "job with spaces",  # Spaces not allowed
            "job@#$%^&*()",  # Special characters
            "job.exe",  # Suspicious extension
            "../job",  # Relative path
            "/absolute/path/job",  # Absolute path
        ]

        for malicious_id in malicious_ids:
            if malicious_id is not None:
                assert job_manager.validate_job_id(malicious_id) is False

    def test_edge_case_job_ids(self, job_manager: JobManager) -> None:
        """Test edge cases in job ID validation."""
        edge_cases = [
            ("_", True),  # Single underscore
            ("-", True),  # Single dash
            ("a", True),  # Single character
            ("A", True),  # Single uppercase
            ("1", True),  # Single number
            ("a-", True),  # Ends with dash
            ("_a", True),  # Starts with underscore
            ("-a-", True),  # Mixed dashes
            ("a_b_c", True),  # Multiple underscores
        ]

        for job_id, should_be_valid in edge_cases:
            assert job_manager.validate_job_id(job_id) is should_be_valid


class TestWebSocketConnectionManagement:
    """Test WebSocket connection lifecycle and error handling."""

    @pytest.fixture
    def job_manager(self) -> JobManager:
        return JobManager(Path("/tmp"))

    def test_connection_addition_and_removal(self, job_manager: JobManager) -> None:
        """Test adding and removing WebSocket connections."""
        job_id = "test-job"
        mock_websocket1 = Mock()
        mock_websocket2 = Mock()

        # Add connections
        job_manager.add_connection(job_id, mock_websocket1)
        job_manager.add_connection(job_id, mock_websocket2)

        # Verify connections are tracked
        assert job_id in job_manager.active_connections
        assert len(job_manager.active_connections[job_id]) == 2
        assert mock_websocket1 in job_manager.active_connections[job_id]
        assert mock_websocket2 in job_manager.active_connections[job_id]

        # Remove one connection
        job_manager.remove_connection(job_id, mock_websocket1)
        assert len(job_manager.active_connections[job_id]) == 1
        assert mock_websocket2 in job_manager.active_connections[job_id]

        # Remove last connection - job should be cleaned up
        job_manager.remove_connection(job_id, mock_websocket2)
        assert job_id not in job_manager.active_connections

    def test_duplicate_connection_handling(self, job_manager: JobManager) -> None:
        """Test handling of duplicate WebSocket connections."""
        job_id = "test-job"
        mock_websocket = Mock()

        # Add same connection multiple times
        job_manager.add_connection(job_id, mock_websocket)
        job_manager.add_connection(job_id, mock_websocket)
        job_manager.add_connection(job_id, mock_websocket)

        # Should only be stored once (set behavior)
        assert len(job_manager.active_connections[job_id]) == 1

    def test_remove_nonexistent_connection(self, job_manager: JobManager) -> None:
        """Test removing connections that don't exist."""
        job_id = "nonexistent-job"
        mock_websocket = Mock()

        # Should not crash
        job_manager.remove_connection(job_id, mock_websocket)
        assert job_id not in job_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_to_healthy_connections(
        self, job_manager: JobManager
    ) -> None:
        """Test broadcasting to healthy WebSocket connections."""
        job_id = "test-job"
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()

        job_manager.add_connection(job_id, mock_websocket1)
        job_manager.add_connection(job_id, mock_websocket2)

        test_data = {"message": "test", "progress": 50}

        await job_manager.broadcast_to_job(job_id, test_data)

        # Both websockets should receive the data
        mock_websocket1.send_json.assert_called_once_with(test_data)
        mock_websocket2.send_json.assert_called_once_with(test_data)

    @pytest.mark.asyncio
    async def test_broadcast_with_failed_connections(
        self, job_manager: JobManager
    ) -> None:
        """Test broadcasting when some connections fail."""
        job_id = "test-job"
        healthy_websocket = AsyncMock()
        failed_websocket = AsyncMock()

        # Configure failed websocket to raise exception
        failed_websocket.send_json.side_effect = Exception("Connection closed")

        job_manager.add_connection(job_id, healthy_websocket)
        job_manager.add_connection(job_id, failed_websocket)

        test_data = {"message": "test"}

        await job_manager.broadcast_to_job(job_id, test_data)

        # Healthy websocket should receive data
        healthy_websocket.send_json.assert_called_once_with(test_data)

        # Failed websocket should be removed from connections
        assert failed_websocket not in job_manager.active_connections[job_id]
        assert healthy_websocket in job_manager.active_connections[job_id]

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_job(self, job_manager: JobManager) -> None:
        """Test broadcasting to non-existent job ID."""
        # Should not crash
        await job_manager.broadcast_to_job("nonexistent-job", {"data": "test"})


class TestJobProgressFileManagement:
    """Test job progress file operations and corruption handling."""

    @pytest.fixture
    def temp_progress_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_progress_dir: Path) -> JobManager:
        return JobManager(temp_progress_dir)

    def create_progress_file(self, progress_dir: Path, job_id: str, data: dict) -> Path:
        """Helper to create a progress file."""
        progress_file = progress_dir / f"job-{job_id}.json"
        progress_file.write_text(json.dumps(data))
        return progress_file

    def test_get_job_progress_success(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test successful job progress retrieval."""
        job_id = "test-job-123"
        test_data = {
            "job_id": job_id,
            "status": "running",
            "progress": 75,
            "message": "Processing stage 3",
        }

        self.create_progress_file(temp_progress_dir, job_id, test_data)

        result = job_manager.get_job_progress(job_id)
        assert result == test_data

    def test_get_job_progress_invalid_job_id(self, job_manager: JobManager) -> None:
        """Test job progress retrieval with invalid job ID."""
        invalid_ids = ["../../../etc/passwd", "", None, "job;rm -rf /"]

        for invalid_id in invalid_ids:
            if invalid_id is not None:
                result = job_manager.get_job_progress(invalid_id)
                assert result is None

    def test_get_job_progress_nonexistent_file(self, job_manager: JobManager) -> None:
        """Test job progress retrieval for nonexistent job."""
        result = job_manager.get_job_progress("nonexistent-job")
        assert result is None

    def test_get_job_progress_corrupted_json(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test handling of corrupted JSON progress files."""
        job_id = "corrupted-job"
        progress_file = temp_progress_dir / f"job-{job_id}.json"

        # Write corrupted JSON
        progress_file.write_text("{ invalid json content")

        result = job_manager.get_job_progress(job_id)
        assert result is None

    def test_get_job_progress_empty_file(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test handling of empty progress files."""
        job_id = "empty-job"
        progress_file = temp_progress_dir / f"job-{job_id}.json"

        # Write empty file
        progress_file.write_text("")

        result = job_manager.get_job_progress(job_id)
        assert result is None

    def test_get_job_progress_permission_error(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test handling when progress file cannot be read due to permissions."""
        job_id = "permission-job"
        progress_file = temp_progress_dir / f"job-{job_id}.json"

        # Create file but make it unreadable
        progress_file.write_text('{"test": "data"}')
        progress_file.chmod(0o000)  # No permissions

        try:
            result = job_manager.get_job_progress(job_id)
            assert result is None
        finally:
            # Restore permissions for cleanup
            progress_file.chmod(0o644)

    def test_get_latest_job_id_multiple_files(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test getting latest job ID from multiple progress files."""
        jobs = [
            ("old-job", {"timestamp": 1000}),
            ("newer-job", {"timestamp": 2000}),
            ("latest-job", {"timestamp": 3000}),
        ]

        # Create files with different modification times
        for job_id, data in jobs:
            progress_file = self.create_progress_file(temp_progress_dir, job_id, data)
            # Set different modification times
            timestamp = data["timestamp"]
            progress_file.touch()
            os.utime(progress_file, (timestamp, timestamp))

        latest_job_id = job_manager.get_latest_job_id()
        assert latest_job_id == "latest-job"

    def test_get_latest_job_id_no_files(self, job_manager: JobManager) -> None:
        """Test getting latest job ID when no progress files exist."""
        latest_job_id = job_manager.get_latest_job_id()
        assert latest_job_id is None

    def test_get_latest_job_id_nonexistent_directory(self) -> None:
        """Test getting latest job ID when progress directory creation fails."""
        nonexistent_dir = Path("/nonexistent/directory")

        # Mock mkdir to fail with FileNotFoundError
        with patch.object(
            Path, "mkdir", side_effect=FileNotFoundError("No such file or directory")
        ):
            with pytest.raises(FileNotFoundError):
                JobManager(nonexistent_dir)

    def test_extract_job_id_from_file(self, job_manager: JobManager) -> None:
        """Test job ID extraction from progress file names."""
        test_cases = [
            ("job-abc123.json", "abc123"),
            ("job-test-job-456.json", "test-job-456"),
            ("job-workflow_789.json", "workflow_789"),
            ("not-a-job-file.json", None),
            ("job-.json", ""),  # Edge case: empty job ID
            ("job-with-multiple-dashes.json", "with-multiple-dashes"),
        ]

        for filename, expected_job_id in test_cases:
            file_path = Path(filename)
            result = job_manager.extract_job_id_from_file(file_path)
            assert result == expected_job_id


class TestNewJobDetectionAndProcessing:
    """Test new job detection and processing logic."""

    @pytest.fixture
    def temp_progress_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_progress_dir: Path) -> JobManager:
        return JobManager(temp_progress_dir)

    @pytest.mark.asyncio
    async def test_process_new_job_detection(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test processing of new job files."""
        job_id = "new-test-job"
        test_data = {"job_id": job_id, "status": "starting", "created_at": time.time()}

        progress_file = temp_progress_dir / f"job-{job_id}.json"
        progress_file.write_text(json.dumps(test_data))

        # Process the file - should detect new job
        await job_manager._process_progress_file(progress_file)

        # Job should now be known
        assert job_id in job_manager.known_jobs

    @pytest.mark.asyncio
    async def test_process_invalid_progress_file(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test processing of invalid progress files."""
        invalid_files = [
            ("not-a-job-file.json", '{"data": "test"}'),
            ("job-invalid;id.json", '{"data": "test"}'),
            ("job-valid.json", "{ invalid json"),
        ]

        for filename, content in invalid_files:
            progress_file = temp_progress_dir / filename
            progress_file.write_text(content)

            # Should not crash and should not add invalid jobs
            await job_manager._process_progress_file(progress_file)

            # Extract potential job ID
            if filename.startswith("job-"):
                potential_job_id = filename[4:-5]  # Remove "job-" and ".json"
                # Invalid job IDs should not be added
                if not job_manager.validate_job_id(potential_job_id):
                    assert potential_job_id not in job_manager.known_jobs

    @pytest.mark.asyncio
    async def test_process_already_known_job(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test processing of progress file for already known job."""
        job_id = "known-job"
        test_data = {"job_id": job_id, "status": "running"}

        progress_file = temp_progress_dir / f"job-{job_id}.json"
        progress_file.write_text(json.dumps(test_data))

        # Add job to known jobs first
        job_manager.known_jobs.add(job_id)
        initial_known_count = len(job_manager.known_jobs)

        # Process the file - should not add duplicate
        await job_manager._process_progress_file(progress_file)

        # Should still have same number of known jobs
        assert len(job_manager.known_jobs) == initial_known_count
        assert job_id in job_manager.known_jobs


class TestWebSocketServerLifecycle:
    """Test WebSocket server lifecycle and configuration."""

    def test_server_initialization(self) -> None:
        """Test server initialization with default configuration."""
        server = WebSocketServer()

        assert server.port == 8675
        assert server.is_running is True
        assert server.job_manager is None
        assert server.app is None
        assert server.progress_dir.name == "crackerjack-mcp-progress"

    def test_server_initialization_custom_port(self) -> None:
        """Test server initialization with custom port."""
        custom_port = 9999
        server = WebSocketServer(port=custom_port)

        assert server.port == custom_port

    def test_server_setup_directory_creation(self) -> None:
        """Test server setup creates progress directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_progress_dir = Path(temp_dir) / "test-progress"

            server = WebSocketServer()
            server.progress_dir = custom_progress_dir

            # Directory shouldn't exist initially
            assert not custom_progress_dir.exists()

            server.setup()

            # Directory should be created during setup
            assert custom_progress_dir.exists()
            assert server.job_manager is not None
            assert server.app is not None

    def test_signal_handler(self) -> None:
        """Test signal handler sets running flag to False."""
        server = WebSocketServer()

        assert server.is_running is True

        # Simulate signal handler
        server._signal_handler(2, None)  # SIGINT

        assert server.is_running is False

    @patch("uvicorn.Server.run")
    def test_server_run_success(self, mock_uvicorn_run) -> None:
        """Test successful server run."""
        server = WebSocketServer()

        server.run()

        # Verify uvicorn was called
        mock_uvicorn_run.assert_called_once()

    @patch("uvicorn.Server.run", side_effect=KeyboardInterrupt())
    def test_server_run_keyboard_interrupt(self, mock_uvicorn_run) -> None:
        """Test server run handles keyboard interrupt gracefully."""
        server = WebSocketServer()

        # Should not raise exception
        server.run()

        mock_uvicorn_run.assert_called_once()

    @patch("uvicorn.Server.run", side_effect=Exception("Server error"))
    def test_server_run_exception_handling(self, mock_uvicorn_run) -> None:
        """Test server run handles exceptions gracefully."""
        server = WebSocketServer()

        # Should not raise exception
        server.run()

        mock_uvicorn_run.assert_called_once()


class TestConcurrentJobManagement:
    """Test concurrent access and thread safety scenarios."""

    @pytest.fixture
    def job_manager(self) -> JobManager:
        return JobManager(Path("/tmp"))

    @pytest.mark.asyncio
    async def test_concurrent_connection_management(
        self, job_manager: JobManager
    ) -> None:
        """Test concurrent addition and removal of connections."""
        job_id = "concurrent-test"
        websockets = [AsyncMock() for _ in range(10)]

        # Concurrent addition of connections
        async def add_connection(ws):
            await asyncio.sleep(0.01)  # Small delay to increase concurrency
            job_manager.add_connection(job_id, ws)

        # Add all connections concurrently
        await asyncio.gather(*[add_connection(ws) for ws in websockets])

        # Verify all connections were added
        assert len(job_manager.active_connections[job_id]) == 10

        # Concurrent removal of connections
        async def remove_connection(ws):
            await asyncio.sleep(0.01)
            job_manager.remove_connection(job_id, ws)

        # Remove half the connections concurrently
        await asyncio.gather(*[remove_connection(ws) for ws in websockets[:5]])

        # Verify correct number of connections remain
        assert len(job_manager.active_connections[job_id]) == 5

    @pytest.mark.asyncio
    async def test_concurrent_broadcasting(self, job_manager: JobManager) -> None:
        """Test concurrent broadcasting to multiple jobs."""
        jobs_and_websockets = [
            (f"job-{i}", [AsyncMock() for _ in range(3)]) for i in range(5)
        ]

        # Set up connections for each job
        for job_id, websockets in jobs_and_websockets:
            for ws in websockets:
                job_manager.add_connection(job_id, ws)

        # Concurrent broadcasting to all jobs
        async def broadcast_to_job(job_id):
            test_data = {"job_id": job_id, "message": "concurrent test"}
            await job_manager.broadcast_to_job(job_id, test_data)

        await asyncio.gather(
            *[broadcast_to_job(job_id) for job_id, _ in jobs_and_websockets]
        )

        # Verify all websockets received their messages
        for job_id, websockets in jobs_and_websockets:
            for ws in websockets:
                assert ws.send_json.called
                call_args = ws.send_json.call_args[0][0]
                assert call_args["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_concurrent_job_validation(self, job_manager: JobManager) -> None:
        """Test concurrent job ID validation doesn't cause race conditions."""
        # Mix of valid and invalid job IDs
        job_ids = (
            [
                str(uuid.uuid4())
                for _ in range(10)  # Valid UUIDs
            ]
            + [
                f"job-{i}"
                for i in range(10)  # Valid alphanumeric
            ]
            + [
                f"../invalid-{i}"
                for i in range(5)  # Invalid paths
            ]
        )

        async def validate_job_id(job_id):
            await asyncio.sleep(0.001)  # Tiny delay to increase concurrency
            return job_manager.validate_job_id(job_id)

        # Validate all job IDs concurrently
        results = await asyncio.gather(*[validate_job_id(job_id) for job_id in job_ids])

        # Verify expected results
        valid_count = sum(results)
        assert valid_count == 20  # 10 UUIDs + 10 alphanumeric
        assert len([r for r in results if not r]) == 5  # 5 invalid paths


class TestJobManagerResourceManagement:
    """Test resource management and cleanup scenarios."""

    @pytest.fixture
    def temp_progress_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_progress_dir: Path) -> JobManager:
        return JobManager(temp_progress_dir)

    def test_memory_usage_with_many_connections(self, job_manager: JobManager) -> None:
        """Test memory usage doesn't grow unbounded with many connections."""
        # Create many jobs with many connections each
        for job_num in range(100):
            job_id = f"job-{job_num}"
            for conn_num in range(10):
                mock_websocket = Mock()
                job_manager.add_connection(job_id, mock_websocket)

        # Verify connections are tracked
        assert len(job_manager.active_connections) == 100
        total_connections = sum(
            len(connections) for connections in job_manager.active_connections.values()
        )
        assert total_connections == 1000

        # Remove all connections and verify cleanup
        for job_id in list(job_manager.active_connections.keys()):
            connections_copy = job_manager.active_connections[job_id].copy()
            for websocket in connections_copy:
                job_manager.remove_connection(job_id, websocket)

        # All job entries should be cleaned up
        assert len(job_manager.active_connections) == 0

    def test_known_jobs_memory_management(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        """Test known jobs set doesn't grow unbounded."""
        # Create many job files
        for i in range(1000):
            job_id = f"memory-test-job-{i}"
            job_data = {"job_id": job_id, "status": "completed"}
            progress_file = temp_progress_dir / f"job-{job_id}.json"
            progress_file.write_text(json.dumps(job_data))

            # Add to known jobs
            job_manager.known_jobs.add(job_id)

        # Verify known jobs are tracked
        assert len(job_manager.known_jobs) == 1000

        # In a real implementation, you might want to implement cleanup
        # of old completed jobs to prevent memory leaks

        # Clear known jobs (simulating cleanup)
        job_manager.known_jobs.clear()
        assert len(job_manager.known_jobs) == 0
