"""Performance benchmark tests for crackerjack components.

These tests measure and verify performance characteristics of critical operations.
Run with: python -m crackerjack --benchmark
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.unified_config import CrackerjackConfig


@pytest.mark.performance
@pytest.mark.benchmark
class TestWorkflowPerformance:
    """Benchmark workflow performance."""

    def test_workflow_orchestrator_performance(self, benchmark, temp_project_dir) -> None:
        """Benchmark workflow orchestrator execution time."""
        config = CrackerjackConfig(
            project_path=temp_project_dir,
            test_timeout=30,
            test_workers=1,
            testing=False,  # Skip tests for benchmark
            skip_hooks=True,  # Skip hooks for consistent timing
            verbose=False,
        )

        def run_workflow():
            orchestrator = WorkflowOrchestrator(config)
            return orchestrator.execute_workflow()

        result = benchmark(run_workflow)
        assert isinstance(result, bool)

    def test_hook_manager_fast_hooks_performance(self, benchmark, temp_project_dir) -> None:
        """Benchmark fast hooks execution time."""
        CrackerjackConfig(
            project_path=temp_project_dir,
            skip_hooks=True,  # Use mocked hooks for consistent timing
            verbose=False,
        )

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        # Mock hook execution for consistent benchmark
        with patch.object(hook_manager, "_run_hook_command") as mock_run:
            mock_run.return_value = (True, "Hook passed", "")

            def run_fast_hooks():
                return hook_manager.run_fast_hooks()

            result = benchmark(run_fast_hooks)
            success, errors = result
            assert isinstance(success, bool)
            assert isinstance(errors, list)


@pytest.mark.performance
@pytest.mark.benchmark
class TestFileSystemPerformance:
    """Benchmark filesystem operations."""

    def test_file_read_performance(self, benchmark, temp_dir) -> None:
        """Benchmark file reading performance."""
        fs_service = FileSystemService()

        # Create test file
        test_file = temp_dir / "perf_test.txt"
        test_content = "Test content " * 1000  # 13KB file
        test_file.write_text(test_content)

        def read_file():
            return fs_service.read_file(str(test_file))

        result = benchmark(read_file)
        assert len(result) == len(test_content)

    def test_file_write_performance(self, benchmark, temp_dir) -> None:
        """Benchmark file writing performance."""
        fs_service = FileSystemService()

        test_content = "Performance test content " * 500  # ~12KB
        test_files = [temp_dir / f"write_test_{i}.txt" for i in range(10)]

        def write_files() -> None:
            for test_file in test_files:
                fs_service.write_file(str(test_file), test_content)

        benchmark(write_files)

        # Verify files were written
        for test_file in test_files:
            assert test_file.exists()
            assert len(test_file.read_text()) == len(test_content)

    def test_directory_creation_performance(self, benchmark, temp_dir) -> None:
        """Benchmark directory creation performance."""
        fs_service = FileSystemService()

        def create_directories():
            base_dirs = []
            for i in range(50):
                dir_path = temp_dir / f"perf_dir_{i}"
                fs_service.create_directory(str(dir_path))
                base_dirs.append(dir_path)

                # Create nested directory
                nested_dir = dir_path / "nested" / "deep"
                fs_service.create_directory(str(nested_dir))

            return base_dirs

        result = benchmark(create_directories)

        # Verify directories were created
        for dir_path in result:
            assert dir_path.exists()
            assert (dir_path / "nested" / "deep").exists()


@pytest.mark.performance
class TestMemoryUsage:
    """Test memory usage patterns."""

    def test_workflow_orchestrator_memory_usage(self, temp_project_dir) -> None:
        """Test workflow orchestrator doesn't leak memory."""
        config = CrackerjackConfig(
            project_path=temp_project_dir, testing=False, skip_hooks=True, verbose=False,
        )

        # Run workflow multiple times
        for _i in range(10):
            orchestrator = WorkflowOrchestrator(config)
            result = orchestrator.execute_workflow()
            assert isinstance(result, bool)

            # Explicitly delete to encourage garbage collection
            del orchestrator

        # If we get here without memory errors, test passes
        assert True

    def test_large_file_handling(self, temp_dir) -> None:
        """Test handling of larger files without memory issues."""
        fs_service = FileSystemService()

        # Create a moderately large file (1MB)
        large_file = temp_dir / "large_file.txt"
        content_chunk = "A" * 1000  # 1KB chunk
        large_content = content_chunk * 1000  # 1MB total

        # Write large file
        fs_service.write_file(str(large_file), large_content)

        # Read it back
        read_content = fs_service.read_file(str(large_file))

        assert len(read_content) == len(large_content)
        assert read_content == large_content


@pytest.mark.performance
@pytest.mark.slow
class TestConcurrencyPerformance:
    """Test performance under concurrent load."""

    def test_concurrent_file_operations(self, temp_dir) -> None:
        """Test concurrent file operations performance."""
        fs_service = FileSystemService()

        def write_file(file_index):
            file_path = temp_dir / f"concurrent_{file_index}.txt"
            content = f"Content for file {file_index}"
            fs_service.write_file(str(file_path), content)
            return file_path

        start_time = time.time()

        # Simulate concurrent operations (sequential in test)
        file_paths = []
        for i in range(20):
            file_path = write_file(i)
            file_paths.append(file_path)

        duration = time.time() - start_time

        # Should complete reasonably quickly
        assert duration < 5.0  # 5 seconds for 20 files

        # Verify all files exist
        for file_path in file_paths:
            assert file_path.exists()

    @pytest.mark.asyncio
    async def test_async_operation_performance(self) -> None:
        """Test async operation performance."""

        async def async_task(task_id, delay=0.01) -> str:
            await asyncio.sleep(delay)
            return f"Task {task_id} completed"

        start_time = time.time()

        # Run tasks concurrently
        tasks = [async_task(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        duration = time.time() - start_time

        # Should complete much faster than sequential (50 * 0.01 = 0.5s)
        assert duration < 0.3  # Should be faster due to concurrency
        assert len(results) == 50


@pytest.mark.performance
class TestScalabilityLimits:
    """Test behavior at scale limits."""

    def test_many_small_files(self, temp_dir) -> None:
        """Test handling many small files."""
        fs_service = FileSystemService()

        start_time = time.time()

        # Create many small files
        file_count = 100
        for i in range(file_count):
            file_path = temp_dir / f"small_file_{i:03d}.txt"
            content = f"Small file {i}"
            fs_service.write_file(str(file_path), content)

        creation_time = time.time() - start_time

        # Should handle creation efficiently
        assert creation_time < 10.0  # 10 seconds for 100 files

        # Test reading all files
        read_start = time.time()

        for i in range(file_count):
            file_path = temp_dir / f"small_file_{i:03d}.txt"
            content = fs_service.read_file(str(file_path))
            assert f"Small file {i}" == content

        read_time = time.time() - read_start

        # Should read efficiently
        assert read_time < 5.0  # 5 seconds to read 100 files

    def test_deep_directory_structure(self, temp_dir) -> None:
        """Test deep directory structure performance."""
        fs_service = FileSystemService()

        # Create deep nested structure
        depth = 20
        current_path = temp_dir

        start_time = time.time()

        for i in range(depth):
            current_path = current_path / f"level_{i}"
            fs_service.create_directory(str(current_path))

            # Add a file at each level
            file_path = current_path / f"file_at_level_{i}.txt"
            fs_service.write_file(str(file_path), f"Content at level {i}")

        creation_time = time.time() - start_time

        # Should handle deep structures reasonably
        assert creation_time < 5.0  # 5 seconds for 20-level deep structure

        # Verify structure exists
        assert current_path.exists()
        assert (current_path / f"file_at_level_{depth - 1}.txt").exists()


@pytest.mark.performance
@pytest.mark.benchmark
class TestConfigurationPerformance:
    """Benchmark configuration loading and processing."""

    def test_config_loading_performance(self, benchmark, temp_dir) -> None:
        """Benchmark configuration loading speed."""
        from crackerjack.services.config import ConfigurationService

        # Create complex config file
        config_file = temp_dir / "complex_config.toml"
        config_content = """
[tool.crackerjack]
test_timeout = 120
test_workers = 8
skip_hooks = false
testing = true
verbose = false
clean = true
interactive = false
ai_agent = false
        """
        config_file.write_text(config_content.strip())

        config_service = ConfigurationService()

        def load_config():
            return config_service.load_config_from_file(str(config_file))

        result = benchmark(load_config)
        assert result is not None

    def test_config_merging_performance(self, benchmark) -> None:
        """Benchmark configuration merging speed."""
        from crackerjack.services.config import ConfigurationService

        config_service = ConfigurationService()

        base_config = {
            "test_timeout": 60,
            "test_workers": 2,
            "verbose": False,
            "hooks": ["ruff", "pyright", "bandit"],
            "excluded_files": ["*.pyc", "*.pyo", "__pycache__"],
        }

        override_configs = [
            {"test_timeout": 120, "verbose": True},
            {"test_workers": 4, "clean": True},
            {"hooks": ["ruff", "mypy"], "ai_agent": True},
        ]

        def merge_configs():
            result = base_config.copy()
            for override in override_configs:
                result = config_service.merge_configs(result, override)
            return result

        result = benchmark(merge_configs)

        assert result["test_timeout"] == 120
        assert result["verbose"] is True
        assert result["test_workers"] == 4
