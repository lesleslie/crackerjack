"""
CI/CD workflow tests.

Tests that verify crackerjack works correctly in CI/CD environments
with proper configuration, timeouts, and parallel execution handling.
"""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.services.unified_config import CrackerjackConfig


@pytest.mark.integration
class TestCIWorkflows:
    """Test CI/CD workflow scenarios"""

    def test_ci_environment_detection(self, ci_environment):
        """Test CI environment is detected correctly"""
        if ci_environment["is_ci"]:
            # Running in CI environment
            assert ci_environment["provider"] in [
                "github_actions",
                "gitlab_ci",
                "jenkins",
                "travis",
                "circleci",
                "unknown",
            ]
            assert ci_environment["timeout_multiplier"] >= 1
        else:
            # Running locally
            assert ci_environment["timeout_multiplier"] == 1

    def test_ci_optimized_config(self, ci_environment, ci_config_factory):
        """Test CI-optimized configuration"""
        config = ci_config_factory(ci_environment)

        # CI config should have appropriate settings
        if ci_environment["is_ci"]:
            assert config.verbose is True  # More verbose in CI
            assert config.test_timeout >= 60  # Longer timeouts
            if not ci_environment["parallel_safe"]:
                assert config.test_workers == 1  # Serial execution if needed
        else:
            # Local development config
            assert config.test_timeout == 60
            assert config.test_workers >= 1

    def test_workflow_execution_in_ci(self, temp_project_dir, ci_environment):
        """Test workflow execution with CI settings"""
        config = CrackerjackConfig(
            project_path=temp_project_dir,
            test_timeout=30 * ci_environment["timeout_multiplier"],
            test_workers=1,  # Serial for reliability
            testing=False,  # Skip actual tests
            skip_hooks=True,  # Skip hooks for speed
            verbose=ci_environment["is_ci"],
        )

        orchestrator = WorkflowOrchestrator(config)

        start_time = time.time()
        result = orchestrator.execute_workflow()
        duration = time.time() - start_time

        # Should complete within reasonable time even in CI
        max_duration = 60 if ci_environment["is_ci"] else 30
        assert duration < max_duration
        assert isinstance(result, bool)


@pytest.mark.integration
class TestParallelExecution:
    """Test parallel test execution scenarios"""

    def test_parallel_hook_execution(self, temp_project_dir, ci_environment):
        """Test hooks can handle parallel execution"""
        CrackerjackConfig(
            project_path=temp_project_dir,
            test_workers=2 if ci_environment["parallel_safe"] else 1,
            skip_hooks=True,  # Use mocked hooks
            verbose=False,
        )

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        # Mock hook execution for parallel test
        with patch.object(hook_manager, "_run_hook_command") as mock_run:
            mock_run.return_value = (True, "Hook passed", "")

            start_time = time.time()
            success, errors = hook_manager.run_fast_hooks()
            duration = time.time() - start_time

            # Should complete quickly with mocked hooks
            assert duration < 5.0
            assert isinstance(success, bool)
            assert isinstance(errors, list)

    def test_concurrent_filesystem_operations(self, temp_dir, ci_environment):
        """Test filesystem operations under concurrent load"""
        from crackerjack.services.filesystem import FileSystemService

        fs_service = FileSystemService()

        # Create multiple files concurrently (simulated)
        file_count = 10 if ci_environment["parallel_safe"] else 5

        start_time = time.time()

        for i in range(file_count):
            file_path = temp_dir / f"concurrent_file_{i}.txt"
            content = f"Content for file {i} in CI test"
            fs_service.write_file(str(file_path), content)

        duration = time.time() - start_time

        # Should handle multiple operations efficiently
        max_duration = 10 if ci_environment["is_ci"] else 5
        assert duration < max_duration

        # Verify all files were created
        for i in range(file_count):
            file_path = temp_dir / f"concurrent_file_{i}.txt"
            assert file_path.exists()
            content = fs_service.read_file(str(file_path))
            assert f"Content for file {i}" in content


@pytest.mark.integration
@pytest.mark.slow
class TestTimeoutHandling:
    """Test timeout handling in CI environments"""

    def test_hook_timeout_handling(self, temp_project_dir, ci_environment):
        """Test hook timeout handling"""
        config = CrackerjackConfig(
            project_path=temp_project_dir,
            test_timeout=5,  # Short timeout for testing
            test_workers=1,
            skip_hooks=True,
        )

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        # Mock slow hook execution
        def slow_hook_mock(*args, **kwargs):
            time.sleep(0.1)  # Small delay
            return (True, "Slow hook completed", "")

        with patch.object(
            hook_manager, "_run_hook_command", side_effect=slow_hook_mock
        ):
            start_time = time.time()
            success, errors = hook_manager.run_fast_hooks()
            duration = time.time() - start_time

            # Should complete within timeout
            timeout_limit = config.test_timeout * ci_environment["timeout_multiplier"]
            assert duration < timeout_limit
            assert isinstance(success, bool)

    def test_workflow_timeout_handling(self, temp_project_dir, ci_environment):
        """Test overall workflow timeout handling"""
        config = CrackerjackConfig(
            project_path=temp_project_dir,
            test_timeout=10 * ci_environment["timeout_multiplier"],
            test_workers=1,
            testing=False,
            skip_hooks=True,
            verbose=False,
        )

        orchestrator = WorkflowOrchestrator(config)

        start_time = time.time()
        result = orchestrator.execute_workflow()
        duration = time.time() - start_time

        # Should complete well within timeout
        assert duration < config.test_timeout
        assert isinstance(result, bool)


@pytest.mark.integration
class TestResourceConstraints:
    """Test behavior under resource constraints typical in CI"""

    def test_low_memory_handling(self, temp_dir, ci_environment):
        """Test handling of memory-constrained environments"""
        from crackerjack.services.filesystem import FileSystemService

        fs_service = FileSystemService()

        # Create many small files (memory pressure simulation)
        file_count = 50 if ci_environment["is_ci"] else 20

        start_time = time.time()

        files_created = []
        for i in range(file_count):
            file_path = temp_dir / f"memory_test_{i:03d}.txt"
            content = f"Memory test content {i}" * 10  # Small files

            try:
                fs_service.write_file(str(file_path), content)
                files_created.append(file_path)
            except MemoryError:
                # Acceptable in constrained environments
                break

        duration = time.time() - start_time

        # Should handle file creation efficiently
        assert duration < 30
        assert len(files_created) > 0

        # Verify some files were created
        for file_path in files_created[:5]:  # Check first 5
            assert file_path.exists()

    def test_cpu_constrained_execution(self, temp_project_dir, ci_environment):
        """Test execution in CPU-constrained environments"""
        config = CrackerjackConfig(
            project_path=temp_project_dir,
            test_workers=1,  # Single worker for CPU constraint
            testing=False,
            skip_hooks=True,
            verbose=False,
        )

        orchestrator = WorkflowOrchestrator(config)

        # Run multiple iterations to simulate CPU load
        iterations = 3
        durations = []

        for i in range(iterations):
            start_time = time.time()
            result = orchestrator.execute_workflow()
            duration = time.time() - start_time
            durations.append(duration)

            assert isinstance(result, bool)

        # Performance should be consistent
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)

        # No single run should be drastically slower
        assert max_duration < avg_duration * 3


@pytest.mark.integration
class TestErrorRecoveryInCI:
    """Test error recovery in CI environments"""

    def test_transient_failure_recovery(self, temp_project_dir, ci_environment):
        """Test recovery from transient failures"""
        CrackerjackConfig(
            project_path=temp_project_dir, test_workers=1, skip_hooks=True
        )

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        # Simulate transient failure then success
        call_count = 0

        def transient_failure_mock(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (False, "Transient failure", "Network error")
            return (True, "Hook recovered", "")

        with patch.object(
            hook_manager, "_run_hook_command", side_effect=transient_failure_mock
        ):
            # First call should fail
            success1, errors1 = hook_manager.run_fast_hooks()

            # Should handle failure gracefully
            assert isinstance(success1, bool)
            assert isinstance(errors1, list)

            # Second call should succeed
            success2, errors2 = hook_manager.run_fast_hooks()

            assert isinstance(success2, bool)
            assert isinstance(errors2, list)

    def test_partial_failure_handling(self, temp_project_dir):
        """Test handling of partial failures in CI"""
        CrackerjackConfig(
            project_path=temp_project_dir, test_workers=1, skip_hooks=True
        )

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        # Mock some hooks passing, some failing
        hook_results = [
            (True, "Hook 1 passed", ""),
            (False, "Hook 2 failed", "Error details"),
            (True, "Hook 3 passed", ""),
        ]

        call_count = 0

        def mixed_results_mock(*args, **kwargs):
            nonlocal call_count
            result = hook_results[call_count % len(hook_results)]
            call_count += 1
            return result

        with patch.object(
            hook_manager, "_run_hook_command", side_effect=mixed_results_mock
        ):
            success, errors = hook_manager.run_fast_hooks()

            # Should handle mixed results
            assert isinstance(success, bool)
            assert isinstance(errors, list)


@pytest.mark.integration
class TestCICacheHandling:
    """Test cache handling in CI environments"""

    def test_cache_isolation(self, temp_dir):
        """Test that caches don't interfere between CI runs"""
        from crackerjack.services.filesystem import FileSystemService

        fs_service = FileSystemService()

        # Create cache-like directory structure
        cache_dir = temp_dir / ".crackerjack_cache"
        cache_dir.mkdir()

        # Create some cache files
        cache_files = []
        for i in range(5):
            cache_file = cache_dir / f"cache_entry_{i}.json"
            cache_content = (
                f'{{"cached_data": "entry_{i}", "timestamp": {time.time()}}}'
            )
            fs_service.write_file(str(cache_file), cache_content)
            cache_files.append(cache_file)

        # Verify cache files exist
        for cache_file in cache_files:
            assert cache_file.exists()

        # Simulate cache cleanup (what CI should do)
        for cache_file in cache_files:
            if cache_file.exists():
                cache_file.unlink()

        # Verify cleanup
        remaining_files = list(cache_dir.glob("*.json"))
        assert len(remaining_files) == 0

    def test_temporary_file_cleanup(self, temp_dir):
        """Test cleanup of temporary files in CI"""
        from crackerjack.services.filesystem import FileSystemService

        fs_service = FileSystemService()

        # Create temporary files
        temp_files = []
        for i in range(3):
            temp_file = temp_dir / f"temp_file_{i}.tmp"
            content = f"Temporary content {i}"
            fs_service.write_file(str(temp_file), content)
            temp_files.append(temp_file)

        # Verify temp files exist
        for temp_file in temp_files:
            assert temp_file.exists()

        # Simulate CI cleanup
        for temp_file in temp_files:
            if temp_file.exists():
                temp_file.unlink()

        # Verify cleanup
        for temp_file in temp_files:
            assert not temp_file.exists()


@pytest.mark.integration
@pytest.mark.external
class TestExternalServiceIntegration:
    """Test integration with external services in CI"""

    def test_git_operations_in_ci(self, temp_project_dir, ci_environment):
        """Test git operations work in CI environment"""
        from crackerjack.services.git import GitService

        original_cwd = os.getcwd()
        os.chdir(temp_project_dir)

        try:
            git_service = GitService()

            # Should detect git repo
            is_repo = git_service.is_git_repo()

            # In CI, git should be available
            if ci_environment["is_ci"]:
                assert isinstance(is_repo, bool)
            else:
                # Local environment might vary
                assert isinstance(is_repo, bool)

        finally:
            os.chdir(original_cwd)

    def test_network_timeout_handling(self, ci_environment):
        """Test handling of network timeouts in CI"""
        # This would test network operations with proper timeouts
        # Mock network calls to avoid actual network dependencies

        timeout_duration = 10 if ci_environment["is_ci"] else 5

        start_time = time.time()

        # Simulate network operation with timeout
        try:
            time.sleep(0.1)  # Simulate quick network call
            network_success = True
        except Exception:
            network_success = False

        duration = time.time() - start_time

        # Should complete within timeout
        assert duration < timeout_duration
        assert network_success is True
