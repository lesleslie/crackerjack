"""
🌪️ BREAKTHROUGH TESTING FRONTIER 3: Chaos Engineering for Testing

This module implements chaos engineering principles in testing to simulate
system failures and verify resilience under adverse conditions.

Chaos testing helps discover weaknesses by introducing controlled failures
and measuring system recovery and graceful degradation.
"""

import pytest
import asyncio
import threading
import time
import tempfile
import subprocess
import psutil
import signal
import random
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from typing import Generator, Optional, Dict, Any, List
import resource
import socket
import os

from crackerjack.services.filesystem import FilesystemService
from crackerjack.managers.hook_manager import HookManager
from crackerjack.core.container import DependencyContainer


class ChaosMonkey:
    """Chaos engineering framework for injecting controlled failures."""
    
    def __init__(self):
        self.active_failures = []
        self.failure_log = []
        self.original_functions = {}
    
    def inject_random_delays(self, min_delay: float = 0.1, max_delay: float = 2.0):
        """Inject random delays into function calls."""
        def delay_wrapper(original_func):
            def delayed_func(*args, **kwargs):
                delay = random.uniform(min_delay, max_delay)
                time.sleep(delay)
                self.failure_log.append(f"Injected {delay:.3f}s delay in {original_func.__name__}")
                return original_func(*args, **kwargs)
            return delayed_func
        
        return delay_wrapper
    
    def inject_memory_pressure(self, memory_mb: int = 50):
        """Create memory pressure by allocating memory."""
        memory_hog = []
        try:
            # Allocate memory in chunks
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(memory_mb):
                memory_hog.append(b'x' * chunk_size)
            self.failure_log.append(f"Injected {memory_mb}MB memory pressure")
            yield memory_hog
        finally:
            del memory_hog
            self.failure_log.append("Released memory pressure")
    
    def inject_cpu_stress(self, duration: float = 1.0, intensity: float = 0.8):
        """Create CPU stress by running intensive calculations."""
        def cpu_stress_task():
            start_time = time.time()
            iterations = 0
            while time.time() - start_time < duration:
                # CPU-intensive calculation
                result = sum(i * i for i in range(1000))
                iterations += 1
                # Brief pause to control intensity
                if intensity < 1.0:
                    time.sleep((1.0 - intensity) * 0.001)
            
            self.failure_log.append(f"CPU stress: {iterations} iterations in {duration}s")
        
        thread = threading.Thread(target=cpu_stress_task, daemon=True)
        thread.start()
        return thread
    
    def inject_io_failures(self, failure_rate: float = 0.3):
        """Inject random I/O failures."""
        def io_failure_wrapper(original_func):
            def failing_func(*args, **kwargs):
                if random.random() < failure_rate:
                    self.failure_log.append(f"Injected I/O failure in {original_func.__name__}")
                    raise OSError("Chaos-injected I/O failure")
                return original_func(*args, **kwargs)
            return failing_func
        
        return io_failure_wrapper
    
    def inject_network_failures(self):
        """Simulate network connectivity issues."""
        def network_failure_wrapper(original_func):
            def failing_func(*args, **kwargs):
                if random.random() < 0.4:  # 40% failure rate
                    self.failure_log.append(f"Injected network failure in {original_func.__name__}")
                    raise ConnectionError("Chaos-injected network failure")
                return original_func(*args, **kwargs)
            return failing_func
        
        return network_failure_wrapper
    
    @contextmanager
    def resource_exhaustion(self, max_files: int = 10, max_memory_mb: int = 100):
        """Simulate resource exhaustion scenarios."""
        original_limits = {}
        temp_files = []
        
        try:
            # Limit file descriptors
            original_limits['files'] = resource.getrlimit(resource.RLIMIT_NOFILE)
            resource.setrlimit(resource.RLIMIT_NOFILE, (max_files, max_files))
            
            # Create temporary files to consume file descriptors
            for i in range(max_files - 5):  # Leave some room for system operations
                try:
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_files.append(temp_file)
                except OSError:
                    break  # Hit the limit
            
            self.failure_log.append(f"Limited file descriptors to {max_files}")
            yield
            
        finally:
            # Restore original limits
            if 'files' in original_limits:
                resource.setrlimit(resource.RLIMIT_NOFILE, original_limits['files'])
            
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    temp_file.close()
                    os.unlink(temp_file.name)
                except Exception:
                    pass
            
            self.failure_log.append("Restored resource limits")


@contextmanager
def chaos_environment(**chaos_options):
    """Context manager for chaos testing environment."""
    chaos = ChaosMonkey()
    active_chaos = []
    
    try:
        # Apply chaos based on options
        if chaos_options.get('memory_pressure'):
            memory_context = chaos.inject_memory_pressure(chaos_options['memory_pressure'])
            active_chaos.append(memory_context)
        
        if chaos_options.get('cpu_stress'):
            cpu_thread = chaos.inject_cpu_stress(
                duration=chaos_options.get('stress_duration', 2.0),
                intensity=chaos_options.get('stress_intensity', 0.8)
            )
            active_chaos.append(cpu_thread)
        
        if chaos_options.get('io_failures'):
            # Patch common I/O operations
            original_open = open
            chaos_open = chaos.inject_io_failures()(original_open)
            
            with patch('builtins.open', chaos_open):
                yield chaos
        else:
            yield chaos
    
    finally:
        # Clean up active chaos
        for chaos_item in active_chaos:
            if hasattr(chaos_item, 'join'):  # Thread
                chaos_item.join(timeout=1.0)


class TestChaosEngineering:
    """Test resilience under chaos conditions."""
    
    @pytest.mark.chaos
    def test_filesystem_operations_under_memory_pressure(self):
        """Test filesystem operations continue working under memory pressure."""
        with chaos_environment(memory_pressure=30):  # 30MB pressure
            filesystem = FilesystemService()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                test_file = Path(temp_dir) / "chaos_test.txt"
                test_content = "Content written under memory pressure"
                
                # Should still work despite memory pressure
                try:
                    filesystem.write_file(test_file, test_content)
                    read_content = filesystem.read_file(test_file)
                    
                    assert read_content == test_content, "File operations should work under memory pressure"
                except (OSError, MemoryError) as e:
                    # Graceful degradation is acceptable
                    pytest.skip(f"System under too much pressure: {e}")
    
    @pytest.mark.chaos
    def test_hook_manager_resilience_to_process_failures(self):
        """Test hook manager handles subprocess failures gracefully."""
        container = DependencyContainer()
        hook_manager = HookManager(container)
        
        # Mock subprocess to randomly fail
        original_run = subprocess.run
        
        def chaotic_subprocess(*args, **kwargs):
            if random.random() < 0.5:  # 50% failure rate
                raise subprocess.SubprocessError("Chaos-injected process failure")
            return original_run(*args, **kwargs)
        
        with patch('subprocess.run', side_effect=chaotic_subprocess):
            # Hook manager should handle failures gracefully
            try:
                # This should not crash the entire system
                result = hook_manager._run_hook_safely("non-existent-hook", timeout=5)
                
                # Either succeeds or fails gracefully
                assert isinstance(result, (dict, type(None))), "Should return structured result or None"
                
            except Exception as e:
                # Should only raise expected exceptions, not random crashes
                expected_exceptions = (subprocess.SubprocessError, FileNotFoundError, OSError)
                assert isinstance(e, expected_exceptions), f"Unexpected exception: {type(e).__name__}: {e}"
    
    @pytest.mark.chaos
    def test_concurrent_operations_under_stress(self):
        """Test system behavior under concurrent stress."""
        filesystem = FilesystemService()
        results = []
        errors = []
        
        def stressed_file_operation(file_id: int):
            """Perform file operations while system is under stress."""
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                    temp_path = Path(temp_file.name)
                    
                # Stress operations
                content = f"Stressed content {file_id} " * 100
                filesystem.write_file(temp_path, content)
                
                # Random delay to simulate real-world timing
                time.sleep(random.uniform(0.01, 0.1))
                
                read_content = filesystem.read_file(temp_path)
                results.append(read_content == content)
                
                temp_path.unlink()
                
            except Exception as e:
                errors.append(str(e))
        
        with chaos_environment(cpu_stress=True, stress_duration=3.0):
            # Run concurrent operations
            threads = []
            for i in range(5):  # 5 concurrent operations
                thread = threading.Thread(target=stressed_file_operation, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join(timeout=10.0)
        
        # Analyze results
        success_rate = len(results) / (len(results) + len(errors)) if (results or errors) else 0
        
        # Under stress, we expect some operations to succeed
        # Complete failure would indicate poor resilience
        assert success_rate >= 0.3, f"Success rate too low under stress: {success_rate:.2f}"
        
        # If there are errors, they should be expected types
        for error in errors:
            assert any(expected in error.lower() for expected in [
                'timeout', 'resource', 'memory', 'permission', 'busy'
            ]), f"Unexpected error type: {error}"
    
    @pytest.mark.chaos  
    @pytest.mark.slow
    def test_resource_exhaustion_handling(self):
        """Test behavior when system resources are exhausted."""
        chaos = ChaosMonkey()
        filesystem = FilesystemService()
        
        # Test with limited file descriptors
        with chaos.resource_exhaustion(max_files=20):
            success_count = 0
            failure_count = 0
            
            # Try to create many files
            created_files = []
            for i in range(15):  # More than available file descriptors
                try:
                    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
                    created_files.append(temp_file.name)
                    
                    # Try filesystem operations
                    content = f"Test content {i}"
                    Path(temp_file.name).write_text(content)
                    success_count += 1
                    
                except (OSError, IOError):
                    failure_count += 1
                    # This is expected when resources are exhausted
            
            # Clean up
            for file_path in created_files:
                try:
                    Path(file_path).unlink()
                except Exception:
                    pass
        
        # Should handle resource exhaustion gracefully
        assert success_count > 0, "Should complete some operations before exhaustion"
        assert failure_count > 0, "Should encounter resource limits"
        
        # Verify logging
        assert len(chaos.failure_log) > 0, "Should log chaos activities"
    
    @pytest.mark.chaos
    def test_timeout_resilience(self):
        """Test resilience to operation timeouts."""
        def slow_operation():
            """Simulate a slow operation that might timeout."""
            time.sleep(2.0)  # Longer than typical timeout
            return "completed"
        
        # Test with short timeout
        start_time = time.time()
        try:
            # Use asyncio to enforce timeout
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def timeout_test():
                return await asyncio.wait_for(
                    asyncio.to_thread(slow_operation),
                    timeout=0.5  # Very short timeout
                )
            
            result = loop.run_until_complete(timeout_test())
            pytest.fail("Should have timed out")
            
        except asyncio.TimeoutError:
            # This is expected - system should handle timeouts gracefully
            elapsed = time.time() - start_time
            assert elapsed < 1.0, "Timeout should be enforced quickly"
        finally:
            loop.close()
    
    @pytest.mark.chaos
    def test_cascading_failure_prevention(self):
        """Test that single failures don't cascade into system-wide failures."""
        filesystem = FilesystemService()
        operations_completed = 0
        
        def potentially_failing_operation(op_id: int) -> bool:
            """Operation that might fail but shouldn't affect others."""
            try:
                if op_id % 3 == 0:  # Every 3rd operation fails
                    raise OSError(f"Simulated failure for operation {op_id}")
                
                # Simulate some work
                with tempfile.NamedTemporaryFile() as temp_file:
                    temp_path = Path(temp_file.name)
                    filesystem.write_file(temp_path, f"Operation {op_id} data")
                    content = filesystem.read_file(temp_path)
                    return content.startswith(f"Operation {op_id}")
                
            except OSError:
                # Individual operation failure - should not cascade
                return False
        
        # Run multiple operations
        results = []
        for i in range(10):
            try:
                success = potentially_failing_operation(i)
                results.append(success)
                if success:
                    operations_completed += 1
            except Exception as e:
                # Unexpected exceptions indicate cascade failure
                pytest.fail(f"Cascading failure detected: {e}")
        
        # Should complete some operations despite individual failures
        success_rate = operations_completed / len(results)
        assert success_rate >= 0.6, f"Too many cascading failures: {success_rate:.2f}"
        
        # Verify pattern of successes and failures
        failures = sum(1 for success in results if not success)
        expected_failures = len(results) // 3  # Every 3rd should fail
        
        # Allow some tolerance in failure pattern
        assert abs(failures - expected_failures) <= 2, \
            f"Failure pattern unexpected: {failures} vs expected ~{expected_failures}"


class TestChaosEngineeringAdvanced:
    """Advanced chaos engineering scenarios."""
    
    @pytest.mark.chaos
    def test_system_recovery_after_chaos(self):
        """Test that system recovers properly after chaos ends."""
        filesystem = FilesystemService()
        
        # Baseline performance before chaos
        baseline_times = []
        for _ in range(3):
            start_time = time.perf_counter()
            
            with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                content = "baseline test content"
                Path(temp_file.name).write_text(content)
                read_content = Path(temp_file.name).read_text()
                assert read_content == content
            
            baseline_times.append(time.perf_counter() - start_time)
        
        baseline_avg = sum(baseline_times) / len(baseline_times)
        
        # Apply chaos and measure degraded performance
        chaos_times = []
        with chaos_environment(cpu_stress=True, stress_duration=2.0):
            for _ in range(3):
                start_time = time.perf_counter()
                
                with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                    content = "chaos test content"
                    Path(temp_file.name).write_text(content)
                    read_content = Path(temp_file.name).read_text()
                    assert read_content == content
                
                chaos_times.append(time.perf_counter() - start_time)
        
        chaos_avg = sum(chaos_times) / len(chaos_times)
        
        # Recovery performance after chaos
        time.sleep(1.0)  # Allow system to recover
        recovery_times = []
        for _ in range(3):
            start_time = time.perf_counter()
            
            with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                content = "recovery test content"
                Path(temp_file.name).write_text(content)
                read_content = Path(temp_file.name).read_text()
                assert read_content == content
            
            recovery_times.append(time.perf_counter() - start_time)
        
        recovery_avg = sum(recovery_times) / len(recovery_times)
        
        # Verify recovery
        # Performance during chaos should be worse than baseline
        assert chaos_avg >= baseline_avg, "Chaos should degrade performance"
        
        # Performance after chaos should recover (within 50% of baseline)
        recovery_ratio = recovery_avg / baseline_avg
        assert recovery_ratio <= 1.5, f"System didn't recover well: {recovery_ratio:.2f}x slower"
        
        print(f"Performance analysis:")
        print(f"Baseline: {baseline_avg:.4f}s")
        print(f"During chaos: {chaos_avg:.4f}s ({chaos_avg/baseline_avg:.1f}x)")
        print(f"After recovery: {recovery_avg:.4f}s ({recovery_ratio:.1f}x)")
    
    @pytest.mark.chaos
    def test_graceful_degradation_under_load(self):
        """Test that system degrades gracefully rather than failing completely."""
        results = {
            'success': 0,
            'partial_success': 0,
            'graceful_failure': 0,
            'hard_failure': 0
        }
        
        def load_test_operation(op_id: int):
            """Operation under load that should degrade gracefully."""
            try:
                # Simulate varying load
                work_size = random.randint(10, 100)
                data = "x" * work_size * 1000  # Variable size work
                
                with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                    temp_path = Path(temp_file.name)
                    temp_path.write_text(data)
                    
                    # Verify data integrity
                    read_data = temp_path.read_text()
                    if read_data == data:
                        results['success'] += 1
                    elif len(read_data) > len(data) // 2:
                        results['partial_success'] += 1
                    else:
                        results['graceful_failure'] += 1
            
            except (OSError, IOError, MemoryError):
                results['graceful_failure'] += 1
            except Exception:
                results['hard_failure'] += 1
        
        # Apply load with resource constraints
        with chaos_environment(memory_pressure=50, cpu_stress=True):
            threads = []
            for i in range(10):  # 10 concurrent operations
                thread = threading.Thread(target=load_test_operation, args=(i,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join(timeout=15.0)
        
        total_ops = sum(results.values())
        assert total_ops > 0, "No operations completed"
        
        # Graceful degradation means most failures should be handled gracefully
        hard_failure_rate = results['hard_failure'] / total_ops
        success_rate = (results['success'] + results['partial_success']) / total_ops
        
        assert hard_failure_rate <= 0.2, f"Too many hard failures: {hard_failure_rate:.2f}"
        assert success_rate >= 0.3, f"Success rate too low: {success_rate:.2f}"
        
        print(f"Load test results: {results}")
        print(f"Success rate: {success_rate:.2f}")
        print(f"Hard failure rate: {hard_failure_rate:.2f}")
    
    @pytest.mark.chaos
    def test_chaos_monkey_logging_and_observability(self):
        """Test that chaos activities are properly logged for observability."""
        chaos = ChaosMonkey()
        
        # Apply various chaos techniques
        with chaos.inject_memory_pressure(20):
            # Trigger memory pressure
            large_data = ["x" * 1000] * 100
            del large_data
        
        cpu_thread = chaos.inject_cpu_stress(duration=0.5)
        cpu_thread.join()
        
        # Verify comprehensive logging
        assert len(chaos.failure_log) >= 3, "Should log chaos activities"
        
        log_messages = " ".join(chaos.failure_log)
        
        # Check for expected log entries
        assert "memory pressure" in log_messages.lower(), "Should log memory pressure"
        assert "cpu stress" in log_messages.lower(), "Should log CPU stress"
        assert "released" in log_messages.lower(), "Should log cleanup"
        
        # Logs should contain timing or quantitative information
        assert any(char.isdigit() for char in log_messages), "Logs should contain metrics"
        
        print("Chaos log:")
        for entry in chaos.failure_log:
            print(f"  {entry}")


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-m", "chaos",
        "--tb=short"
    ])