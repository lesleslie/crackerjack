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
    @pytest.fixture
    def temp_progress_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_progress_dir: Path) -> JobManager:
        return JobManager(temp_progress_dir)


class TestJobIdValidationRobustness:
    @pytest.fixture
    def job_manager(self) -> JobManager:
        return JobManager(Path("/ tmp"))

    def test_valid_uuid_job_ids(self, job_manager: JobManager) -> None:
        valid_uuids = [
            str(uuid.uuid4()),
            "550e8400 - e29b - 41d4 - a716 - 446655440000",
            "6ba7b810 - 9dad - 11d1 - 80b4 - 00c04fd430c8",
        ]

        for valid_uuid in valid_uuids:
            assert job_manager.validate_job_id(valid_uuid) is True

    def test_valid_alphanumeric_job_ids(self, job_manager: JobManager) -> None:
        valid_ids = [
            "job123",
            "test - job - 456",
            "workflow_789",
            "a1b2c3d4",
            "Job_Test - 123",
        ]

        for valid_id in valid_ids:
            assert job_manager.validate_job_id(valid_id) is True

    def test_malicious_job_id_rejection(self, job_manager: JobManager) -> None:
        malicious_ids = [
            "",
            None,
            "../../../ etc / passwd",
            "job;rm - rf /",
            "job$(whoami)",
            "job`cat / etc / passwd`",
            "job\necho 'pwned'",
            "job\0null",
            "a" * 100,
            "job with spaces",
            "job@#$% ^& *()",
            "job.exe",
            "../ job",
            "/ absolute / path / job",
        ]

        for malicious_id in malicious_ids:
            if malicious_id is not None:
                assert job_manager.validate_job_id(malicious_id) is False

    def test_edge_case_job_ids(self, job_manager: JobManager) -> None:
        edge_cases = [
            ("_", True),
            ("-", True),
            ("a", True),
            ("A", True),
            ("1", True),
            ("a -", True),
            ("_a", True),
            ("- a -", True),
            ("a_b_c", True),
        ]

        for job_id, should_be_valid in edge_cases:
            assert job_manager.validate_job_id(job_id) is should_be_valid


class TestWebSocketConnectionManagement:
    @pytest.fixture
    def job_manager(self) -> JobManager:
        return JobManager(Path("/ tmp"))

    def test_connection_addition_and_removal(self, job_manager: JobManager) -> None:
        job_id = "test - job"
        mock_websocket1 = Mock()
        mock_websocket2 = Mock()

        job_manager.add_connection(job_id, mock_websocket1)
        job_manager.add_connection(job_id, mock_websocket2)

        assert job_id in job_manager.active_connections
        assert len(job_manager.active_connections[job_id]) == 2
        assert mock_websocket1 in job_manager.active_connections[job_id]
        assert mock_websocket2 in job_manager.active_connections[job_id]

        job_manager.remove_connection(job_id, mock_websocket1)
        assert len(job_manager.active_connections[job_id]) == 1
        assert mock_websocket2 in job_manager.active_connections[job_id]

        job_manager.remove_connection(job_id, mock_websocket2)
        assert job_id not in job_manager.active_connections

    def test_duplicate_connection_handling(self, job_manager: JobManager) -> None:
        job_id = "test - job"
        mock_websocket = Mock()

        job_manager.add_connection(job_id, mock_websocket)
        job_manager.add_connection(job_id, mock_websocket)
        job_manager.add_connection(job_id, mock_websocket)

        assert len(job_manager.active_connections[job_id]) == 1

    def test_remove_nonexistent_connection(self, job_manager: JobManager) -> None:
        job_id = "nonexistent - job"
        mock_websocket = Mock()

        job_manager.remove_connection(job_id, mock_websocket)
        assert job_id not in job_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_to_healthy_connections(
        self, job_manager: JobManager
    ) -> None:
        job_id = "test - job"
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()

        job_manager.add_connection(job_id, mock_websocket1)
        job_manager.add_connection(job_id, mock_websocket2)

        test_data = {"message": "test", "progress": 50}

        await job_manager.broadcast_to_job(job_id, test_data)

        mock_websocket1.send_json.assert_called_once_with(test_data)
        mock_websocket2.send_json.assert_called_once_with(test_data)

    @pytest.mark.asyncio
    async def test_broadcast_with_failed_connections(
        self, job_manager: JobManager
    ) -> None:
        job_id = "test - job"
        healthy_websocket = AsyncMock()
        failed_websocket = AsyncMock()

        failed_websocket.send_json.side_effect = Exception("Connection closed")

        job_manager.add_connection(job_id, healthy_websocket)
        job_manager.add_connection(job_id, failed_websocket)

        test_data = {"message": "test"}

        await job_manager.broadcast_to_job(job_id, test_data)

        healthy_websocket.send_json.assert_called_once_with(test_data)

        assert failed_websocket not in job_manager.active_connections[job_id]
        assert healthy_websocket in job_manager.active_connections[job_id]

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_job(self, job_manager: JobManager) -> None:
        await job_manager.broadcast_to_job("nonexistent - job", {"data": "test"})


class TestJobProgressFileManagement:
    @pytest.fixture
    def temp_progress_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_progress_dir: Path) -> JobManager:
        return JobManager(temp_progress_dir)

    def create_progress_file(self, progress_dir: Path, job_id: str, data: dict) -> Path:
        progress_file = progress_dir / f"job -{job_id}.json"
        progress_file.write_text(json.dumps(data))
        return progress_file

    def test_get_job_progress_success(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        job_id = "test - job - 123"
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
        invalid_ids = ["../../../ etc / passwd", "", None, "job;rm - rf /"]

        for invalid_id in invalid_ids:
            if invalid_id is not None:
                result = job_manager.get_job_progress(invalid_id)
                assert result is None

    def test_get_job_progress_nonexistent_file(self, job_manager: JobManager) -> None:
        result = job_manager.get_job_progress("nonexistent - job")
        assert result is None

    def test_get_job_progress_corrupted_json(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        job_id = "corrupted - job"
        progress_file = temp_progress_dir / f"job -{job_id}.json"

        progress_file.write_text("{ invalid json content")

        result = job_manager.get_job_progress(job_id)
        assert result is None

    def test_get_job_progress_empty_file(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        job_id = "empty - job"
        progress_file = temp_progress_dir / f"job -{job_id}.json"

        progress_file.write_text("")

        result = job_manager.get_job_progress(job_id)
        assert result is None

    def test_get_job_progress_permission_error(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        job_id = "permission - job"
        progress_file = temp_progress_dir / f"job -{job_id}.json"

        progress_file.write_text('{"test": "data"}')
        progress_file.chmod(0o000)

        try:
            result = job_manager.get_job_progress(job_id)
            assert result is None
        finally:
            progress_file.chmod(0o644)

    def test_get_latest_job_id_multiple_files(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        jobs = [
            ("old - job", {"timestamp": 1000}),
            ("newer - job", {"timestamp": 2000}),
            ("latest - job", {"timestamp": 3000}),
        ]

        for job_id, data in jobs:
            progress_file = self.create_progress_file(temp_progress_dir, job_id, data)

            timestamp = data["timestamp"]
            progress_file.touch()
            os.utime(progress_file, (timestamp, timestamp))

        latest_job_id = job_manager.get_latest_job_id()
        assert latest_job_id == "latest - job"

    def test_get_latest_job_id_no_files(self, job_manager: JobManager) -> None:
        latest_job_id = job_manager.get_latest_job_id()
        assert latest_job_id is None

    def test_get_latest_job_id_nonexistent_directory(self) -> None:
        nonexistent_dir = Path("/ nonexistent / directory")

        with patch.object(
            Path, "mkdir", side_effect=FileNotFoundError("No such file or directory")
        ):
            with pytest.raises(FileNotFoundError):
                JobManager(nonexistent_dir)

    def test_extract_job_id_from_file(self, job_manager: JobManager) -> None:
        test_cases = [
            ("job - abc123.json", "abc123"),
            ("job - test - job - 456.json", "test - job - 456"),
            ("job - workflow_789.json", "workflow_789"),
            ("not - a - job - file.json", None),
            ("job -.json", ""),
            ("job - with - multiple - dashes.json", "with - multiple - dashes"),
        ]

        for filename, expected_job_id in test_cases:
            file_path = Path(filename)
            result = job_manager.extract_job_id_from_file(file_path)
            assert result == expected_job_id


class TestNewJobDetectionAndProcessing:
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
        job_id = "new - test - job"
        test_data = {"job_id": job_id, "status": "starting", "created_at": time.time()}

        progress_file = temp_progress_dir / f"job -{job_id}.json"
        progress_file.write_text(json.dumps(test_data))

        await job_manager._process_progress_file(progress_file)

        assert job_id in job_manager.known_jobs

    @pytest.mark.asyncio
    async def test_process_invalid_progress_file(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        invalid_files = [
            ("not - a - job - file.json", '{"data": "test"}'),
            ("job - invalid;id.json", '{"data": "test"}'),
            ("job - valid.json", "{ invalid json"),
        ]

        for filename, content in invalid_files:
            progress_file = temp_progress_dir / filename
            progress_file.write_text(content)

            await job_manager._process_progress_file(progress_file)

            if filename.startswith("job -"):
                potential_job_id = filename[4:-5]

                if not job_manager.validate_job_id(potential_job_id):
                    assert potential_job_id not in job_manager.known_jobs

    @pytest.mark.asyncio
    async def test_process_already_known_job(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        job_id = "known - job"
        test_data = {"job_id": job_id, "status": "running"}

        progress_file = temp_progress_dir / f"job -{job_id}.json"
        progress_file.write_text(json.dumps(test_data))

        job_manager.known_jobs.add(job_id)
        initial_known_count = len(job_manager.known_jobs)

        await job_manager._process_progress_file(progress_file)

        assert len(job_manager.known_jobs) == initial_known_count
        assert job_id in job_manager.known_jobs


class TestWebSocketServerLifecycle:
    def test_server_initialization(self) -> None:
        server = WebSocketServer()

        assert server.port == 8675
        assert server.is_running is True
        assert server.job_manager is None
        assert server.app is None
        assert server.progress_dir.name == "crackerjack - mcp - progress"

    def test_server_initialization_custom_port(self) -> None:
        custom_port = 9999
        server = WebSocketServer(port=custom_port)

        assert server.port == custom_port

    def test_server_setup_directory_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_progress_dir = Path(temp_dir) / "test - progress"

            server = WebSocketServer()
            server.progress_dir = custom_progress_dir

            assert not custom_progress_dir.exists()

            server.setup()

            assert custom_progress_dir.exists()
            assert server.job_manager is not None
            assert server.app is not None

    def test_signal_handler(self) -> None:
        server = WebSocketServer()

        assert server.is_running is True

        server._signal_handler(2, None)

        assert server.is_running is False

    @patch("uvicorn.Server.run")
    def test_server_run_success(self, mock_uvicorn_run) -> None:
        server = WebSocketServer()

        server.run()

        mock_uvicorn_run.assert_called_once()

    @patch("uvicorn.Server.run", side_effect=KeyboardInterrupt())
    def test_server_run_keyboard_interrupt(self, mock_uvicorn_run) -> None:
        server = WebSocketServer()

        server.run()

        mock_uvicorn_run.assert_called_once()

    @patch("uvicorn.Server.run", side_effect=Exception("Server error"))
    def test_server_run_exception_handling(self, mock_uvicorn_run) -> None:
        server = WebSocketServer()

        server.run()

        mock_uvicorn_run.assert_called_once()


class TestConcurrentJobManagement:
    @pytest.fixture
    def job_manager(self) -> JobManager:
        return JobManager(Path("/ tmp"))

    @pytest.mark.asyncio
    async def test_concurrent_connection_management(
        self, job_manager: JobManager
    ) -> None:
        job_id = "concurrent - test"
        websockets = [AsyncMock() for _ in range(10)]

        async def add_connection(ws):
            await asyncio.sleep(0.01)
            job_manager.add_connection(job_id, ws)

        await asyncio.gather(*[add_connection(ws) for ws in websockets])

        assert len(job_manager.active_connections[job_id]) == 10

        async def remove_connection(ws):
            await asyncio.sleep(0.01)
            job_manager.remove_connection(job_id, ws)

        await asyncio.gather(*[remove_connection(ws) for ws in websockets[:5]])

        assert len(job_manager.active_connections[job_id]) == 5

    @pytest.mark.asyncio
    async def test_concurrent_broadcasting(self, job_manager: JobManager) -> None:
        jobs_and_websockets = [
            (f"job -{i}", [AsyncMock() for _ in range(3)]) for i in range(5)
        ]

        for job_id, websockets in jobs_and_websockets:
            for ws in websockets:
                job_manager.add_connection(job_id, ws)

        async def broadcast_to_job(job_id):
            test_data = {"job_id": job_id, "message": "concurrent test"}
            await job_manager.broadcast_to_job(job_id, test_data)

        await asyncio.gather(
            *[broadcast_to_job(job_id) for job_id, _ in jobs_and_websockets]
        )

        for job_id, websockets in jobs_and_websockets:
            for ws in websockets:
                assert ws.send_json.called
                call_args = ws.send_json.call_args[0][0]
                assert call_args["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_concurrent_job_validation(self, job_manager: JobManager) -> None:
        job_ids = (
            [str(uuid.uuid4()) for _ in range(10)]
            + [f"job -{i}" for i in range(10)]
            + [f"../ invalid -{i}" for i in range(5)]
        )

        async def validate_job_id(job_id):
            await asyncio.sleep(0.001)
            return job_manager.validate_job_id(job_id)

        results = await asyncio.gather(*[validate_job_id(job_id) for job_id in job_ids])

        valid_count = sum(results)
        assert valid_count == 20
        assert len([r for r in results if not r]) == 5


class TestJobManagerResourceManagement:
    @pytest.fixture
    def temp_progress_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_progress_dir: Path) -> JobManager:
        return JobManager(temp_progress_dir)

    def test_memory_usage_with_many_connections(self, job_manager: JobManager) -> None:
        for job_num in range(100):
            job_id = f"job -{job_num}"
            for conn_num in range(10):
                mock_websocket = Mock()
                job_manager.add_connection(job_id, mock_websocket)

        assert len(job_manager.active_connections) == 100
        total_connections = sum(
            len(connections) for connections in job_manager.active_connections.values()
        )
        assert total_connections == 1000

        for job_id in list(job_manager.active_connections.keys()):
            connections_copy = job_manager.active_connections[job_id].copy()
            for websocket in connections_copy:
                job_manager.remove_connection(job_id, websocket)

        assert len(job_manager.active_connections) == 0

    def test_known_jobs_memory_management(
        self, job_manager: JobManager, temp_progress_dir: Path
    ) -> None:
        for i in range(1000):
            job_id = f"memory - test - job -{i}"
            job_data = {"job_id": job_id, "status": "completed"}
            progress_file = temp_progress_dir / f"job -{job_id}.json"
            progress_file.write_text(json.dumps(job_data))

            job_manager.known_jobs.add(job_id)

        assert len(job_manager.known_jobs) == 1000

        job_manager.known_jobs.clear()
        assert len(job_manager.known_jobs) == 0
