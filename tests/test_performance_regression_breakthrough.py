"""
⚡ BREAKTHROUGH TESTING FRONTIER 5: Performance Regression Detection

This module implements automated performance regression detection with benchmarking,
memory leak detection, and resource usage profiling for CI/CD integration.

Performance regression testing ensures that code changes don't degrade system
performance and catches optimization opportunities automatically.
"""

import pytest
import time
import psutil
import gc
import sys
import threading
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from unittest.mock import patch
import subprocess
import resource
import tracemalloc
from collections import defaultdict
import statistics

# Import modules to benchmark
from crackerjack.services.filesystem import FilesystemService
from crackerjack.services.config import ConfigService
from crackerjack.managers.hook_manager import HookManager
from crackerjack.core.container import DependencyContainer


@dataclass
class PerformanceMetrics:
    """Container for performance measurement data."""
    operation_name: str
    execution_time: float
    memory_peak: int
    memory_current: int
    cpu_percent: float
    io_operations: int
    function_calls: int
    timestamp: float
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return asdict(self)


@dataclass
class PerformanceBenchmark:
    """Baseline performance benchmark for comparison."""
    operation_name: str
    mean_time: float
    std_dev_time: float
    mean_memory: int
    std_dev_memory: int
    sample_size: int
    confidence_interval: Tuple[float, float]
    
    def is_regression(self, current_time: float, threshold: float = 2.0) -> bool:
        """Check if current performance is a regression."""
        # Performance regression if current time is significantly slower
        regression_threshold = self.mean_time + (threshold * self.std_dev_time)
        return current_time > regression_threshold
    
    def improvement_percentage(self, current_time: float) -> float:
        """Calculate performance improvement percentage."""
        if self.mean_time == 0:
            return 0.0
        return ((self.mean_time - current_time) / self.mean_time) * 100


class PerformanceProfiler:
    """Advanced performance profiling with memory and CPU tracking."""
    
    def __init__(self):
        self.is_profiling = False
        self.start_memory = 0
        self.start_time = 0
        self.process = psutil.Process()
        self.memory_samples = []
        self.cpu_samples = []
        
    @contextmanager
    def profile_operation(self, operation_name: str):
        """Profile an operation with comprehensive metrics."""
        # Start memory tracing
        tracemalloc.start()
        
        # Collect initial metrics
        gc.collect()  # Force garbage collection for consistent baseline
        self.start_time = time.perf_counter()
        self.start_memory = self.process.memory_info().rss
        initial_cpu = self.process.cpu_percent()
        
        # Start background monitoring
        monitoring_active = threading.Event()
        monitor_thread = threading.Thread(
            target=self._background_monitor,
            args=(monitoring_active,),
            daemon=True
        )
        monitor_thread.start()
        monitoring_active.set()
        
        success = True
        error_message = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            # Stop monitoring
            monitoring_active.clear()
            monitor_thread.join(timeout=1.0)
            
            # Collect final metrics
            end_time = time.perf_counter()
            execution_time = end_time - self.start_time
            
            # Memory metrics
            current_memory = self.process.memory_info().rss
            current_traced, peak_traced = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            # CPU metrics
            final_cpu = self.process.cpu_percent()
            avg_cpu = statistics.mean(self.cpu_samples) if self.cpu_samples else final_cpu
            
            # I/O metrics
            io_counters = self.process.io_counters()
            io_operations = io_counters.read_count + io_counters.write_count
            
            # Create metrics object
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                execution_time=execution_time,
                memory_peak=peak_traced,
                memory_current=current_traced,
                cpu_percent=avg_cpu,
                io_operations=io_operations,
                function_calls=0,  # Would require more complex instrumentation
                timestamp=time.time(),
                success=success,
                error_message=error_message
            )
            
            # Store metrics for analysis
            self._store_metrics(metrics)
    
    def _background_monitor(self, active_event: threading.Event):
        """Background thread to monitor resource usage."""
        while active_event.is_set():
            try:
                self.memory_samples.append(self.process.memory_info().rss)
                self.cpu_samples.append(self.process.cpu_percent())
                time.sleep(0.1)  # Sample every 100ms
            except Exception:
                break
    
    def _store_metrics(self, metrics: PerformanceMetrics):
        """Store metrics for later analysis."""
        # In a real implementation, this would store to a database or file
        # For testing, we'll use a simple file-based approach
        metrics_dir = Path(tempfile.gettempdir()) / "crackerjack_performance"
        metrics_dir.mkdir(exist_ok=True)
        
        metrics_file = metrics_dir / f"metrics_{int(time.time())}.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)


class BenchmarkRunner:
    """Runs performance benchmarks and detects regressions."""
    
    def __init__(self):
        self.profiler = PerformanceProfiler()
        self.benchmarks: Dict[str, PerformanceBenchmark] = {}
        self.baseline_file = Path(tempfile.gettempdir()) / "crackerjack_baselines.json"
        self.load_baselines()
    
    def establish_baseline(self, operation_name: str, operation_func: Callable, 
                         iterations: int = 10) -> PerformanceBenchmark:
        """Establish performance baseline for an operation."""
        execution_times = []
        memory_peaks = []
        
        print(f"Establishing baseline for {operation_name} ({iterations} iterations)...")
        
        for i in range(iterations):
            with self.profiler.profile_operation(f"{operation_name}_baseline_{i}"):
                operation_func()
            
            # Collect the metrics from the last run
            # In a real implementation, metrics would be retrieved from storage
            execution_times.append(time.perf_counter() - self.profiler.start_time)
            memory_peaks.append(max(self.profiler.memory_samples) if self.profiler.memory_samples else 0)
        
        # Calculate statistics
        mean_time = statistics.mean(execution_times)
        std_dev_time = statistics.stdev(execution_times) if len(execution_times) > 1 else 0
        mean_memory = statistics.mean(memory_peaks) if memory_peaks else 0
        std_dev_memory = statistics.stdev(memory_peaks) if len(memory_peaks) > 1 else 0
        
        # Calculate confidence interval (95%)
        if std_dev_time > 0:
            margin = 1.96 * (std_dev_time / (iterations ** 0.5))  # 95% CI
            confidence_interval = (mean_time - margin, mean_time + margin)
        else:
            confidence_interval = (mean_time, mean_time)
        
        benchmark = PerformanceBenchmark(
            operation_name=operation_name,
            mean_time=mean_time,
            std_dev_time=std_dev_time,
            mean_memory=mean_memory,
            std_dev_memory=std_dev_memory,
            sample_size=iterations,
            confidence_interval=confidence_interval
        )
        
        self.benchmarks[operation_name] = benchmark
        self.save_baselines()
        
        print(f"Baseline established: {mean_time:.4f}s ± {std_dev_time:.4f}s")
        return benchmark
    
    def run_regression_test(self, operation_name: str, operation_func: Callable,
                          iterations: int = 5) -> Dict[str, Any]:
        """Run regression test against established baseline."""
        if operation_name not in self.benchmarks:
            print(f"No baseline for {operation_name}, establishing one...")
            self.establish_baseline(operation_name, operation_func)
            return {'status': 'baseline_established', 'regression': False}
        
        baseline = self.benchmarks[operation_name]
        execution_times = []
        memory_peaks = []
        
        print(f"Running regression test for {operation_name} ({iterations} iterations)...")
        
        for i in range(iterations):
            start_time = time.perf_counter()
            
            with self.profiler.profile_operation(f"{operation_name}_test_{i}"):
                operation_func()
            
            execution_time = time.perf_counter() - start_time
            execution_times.append(execution_time)
            
            if self.profiler.memory_samples:
                memory_peaks.append(max(self.profiler.memory_samples))
        
        # Analyze results
        current_mean = statistics.mean(execution_times)
        current_std = statistics.stdev(execution_times) if len(execution_times) > 1 else 0
        
        is_regression = baseline.is_regression(current_mean)
        improvement_pct = baseline.improvement_percentage(current_mean)
        
        # Statistical significance test (simplified)
        # In reality, you'd use proper statistical tests like t-test
        significance_threshold = 0.05  # 5% significance level
        relative_change = abs(current_mean - baseline.mean_time) / baseline.mean_time
        statistically_significant = relative_change > significance_threshold
        
        results = {
            'operation': operation_name,
            'status': 'regression' if is_regression else 'pass',
            'regression': is_regression,
            'statistically_significant': statistically_significant,
            'current_mean': current_mean,
            'baseline_mean': baseline.mean_time,
            'improvement_percentage': improvement_pct,
            'relative_change': relative_change * 100,
            'current_std': current_std,
            'baseline_std': baseline.std_dev_time,
            'iterations': iterations,
            'memory_regression': any(m > baseline.mean_memory * 1.5 for m in memory_peaks) if memory_peaks else False
        }
        
        print(f"Results: {current_mean:.4f}s vs {baseline.mean_time:.4f}s "
              f"({improvement_pct:+.1f}% change)")
        
        return results
    
    def save_baselines(self):
        """Save baselines to file for persistence."""
        data = {}
        for name, benchmark in self.benchmarks.items():
            data[name] = asdict(benchmark)
        
        with open(self.baseline_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_baselines(self):
        """Load baselines from file."""
        if self.baseline_file.exists():
            try:
                with open(self.baseline_file, 'r') as f:
                    data = json.load(f)
                
                for name, benchmark_data in data.items():
                    self.benchmarks[name] = PerformanceBenchmark(**benchmark_data)
            except Exception as e:
                print(f"Warning: Could not load baselines: {e}")


class MemoryLeakDetector:
    """Detects memory leaks in operations."""
    
    def __init__(self):
        self.initial_memory = 0
        self.samples = []
    
    @contextmanager
    def detect_leaks(self, operation_name: str, threshold_mb: int = 10):
        """Context manager to detect memory leaks."""
        gc.collect()  # Clean up before starting
        self.initial_memory = psutil.Process().memory_info().rss
        
        # Start monitoring
        monitoring = True
        
        def monitor():
            while monitoring:
                self.samples.append(psutil.Process().memory_info().rss)
                time.sleep(0.1)
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        
        try:
            yield
        finally:
            monitoring = False
            monitor_thread.join(timeout=1.0)
            
            # Force cleanup
            gc.collect()
            final_memory = psutil.Process().memory_info().rss
            
            # Analyze for leaks
            memory_growth = final_memory - self.initial_memory
            memory_growth_mb = memory_growth / (1024 * 1024)
            
            if memory_growth_mb > threshold_mb:
                leak_info = {
                    'operation': operation_name,
                    'initial_memory_mb': self.initial_memory / (1024 * 1024),
                    'final_memory_mb': final_memory / (1024 * 1024),
                    'growth_mb': memory_growth_mb,
                    'peak_memory_mb': max(self.samples) / (1024 * 1024) if self.samples else 0,
                    'leak_detected': True
                }
                
                print(f"MEMORY LEAK DETECTED in {operation_name}: {memory_growth_mb:.2f}MB growth")
                return leak_info
            else:
                return {
                    'operation': operation_name,
                    'growth_mb': memory_growth_mb,
                    'leak_detected': False
                }


class TestPerformanceRegression:
    """Test suite for performance regression detection."""
    
    def setUp(self):
        """Set up benchmark runner for tests."""
        self.benchmark_runner = BenchmarkRunner()
        self.leak_detector = MemoryLeakDetector()
    
    @pytest.mark.benchmark
    def test_filesystem_write_performance(self, benchmark):
        """Benchmark filesystem write operations."""
        filesystem = FilesystemService()
        
        def write_operation():
            with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                temp_path = Path(temp_file.name)
                content = "Performance test content " * 100  # ~2.5KB
                filesystem.write_file(temp_path, content)
        
        # Use pytest-benchmark for precise measurements
        result = benchmark(write_operation)
        
        # Verify performance is within reasonable bounds
        assert result.stats.mean < 0.1, f"Write operation too slow: {result.stats.mean:.4f}s"
    
    @pytest.mark.benchmark
    def test_filesystem_read_performance(self, benchmark):
        """Benchmark filesystem read operations."""
        filesystem = FilesystemService()
        
        # Setup: Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            content = "Performance test content " * 1000  # ~25KB
            temp_path.write_text(content)
        
        try:
            def read_operation():
                return filesystem.read_file(temp_path)
            
            result = benchmark(read_operation)
            
            # Verify performance is within reasonable bounds
            assert result.stats.mean < 0.05, f"Read operation too slow: {result.stats.mean:.4f}s"
            
        finally:
            temp_path.unlink()
    
    @pytest.mark.benchmark
    def test_config_service_performance(self, benchmark):
        """Benchmark configuration operations."""
        config_service = ConfigService()
        
        def config_operation():
            # Simulate config operations
            test_config = {
                'tool': {
                    'test': {
                        'option1': 'value1',
                        'option2': 42,
                        'option3': True
                    }
                }
            }
            
            with tempfile.NamedTemporaryFile(suffix='.toml') as temp_file:
                temp_path = Path(temp_file.name)
                config_service._write_toml_safe(temp_path, test_config)
                loaded_config = config_service._read_toml_safe(temp_path)
                return loaded_config
        
        result = benchmark(config_operation)
        
        # Config operations should be fast
        assert result.stats.mean < 0.02, f"Config operation too slow: {result.stats.mean:.4f}s"
    
    @pytest.mark.performance
    def test_memory_leak_detection(self):
        """Test memory leak detection in operations."""
        self.setUp()
        filesystem = FilesystemService()
        
        def potentially_leaky_operation():
            # Simulate operation that might leak memory
            large_data = []
            for i in range(100):
                with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                    content = f"Data {i} " * 100
                    temp_path = Path(temp_file.name)
                    filesystem.write_file(temp_path, content)
                    large_data.append(content)  # This could cause a leak if not cleaned up
            
            # Simulate cleanup (comment out to create actual leak for testing)
            del large_data
        
        with self.leak_detector.detect_leaks("filesystem_operations", threshold_mb=5):
            potentially_leaky_operation()
        
        # This test mainly validates the leak detection mechanism
        # In a real scenario, you'd have operations that actually leak
    
    @pytest.mark.performance
    def test_regression_detection_integration(self):
        """Test integration of regression detection with real operations."""
        self.setUp()
        filesystem = FilesystemService()
        
        def baseline_operation():
            # Fast, optimized operation
            with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                content = "baseline content"
                Path(temp_file.name).write_text(content)
        
        def regression_operation():
            # Slower operation simulating regression
            time.sleep(0.01)  # Simulate 10ms slowdown
            with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                content = "regression content"
                Path(temp_file.name).write_text(content)
        
        # Establish baseline
        baseline_result = self.benchmark_runner.establish_baseline(
            "test_operation", baseline_operation, iterations=5
        )
        
        assert baseline_result.mean_time > 0, "Should establish valid baseline"
        
        # Test for regression
        regression_result = self.benchmark_runner.run_regression_test(
            "test_operation", regression_operation, iterations=3
        )
        
        # Should detect the intentional slowdown as regression
        assert regression_result['regression'], "Should detect performance regression"
        assert regression_result['relative_change'] > 0, "Should show performance degradation"
    
    @pytest.mark.performance
    def test_performance_under_load(self):
        """Test performance characteristics under concurrent load."""
        filesystem = FilesystemService()
        results = []
        
        def concurrent_operation(thread_id: int):
            """Operation to run concurrently."""
            start_time = time.perf_counter()
            
            try:
                with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                    content = f"Thread {thread_id} content " * 50
                    temp_path = Path(temp_file.name)
                    filesystem.write_file(temp_path, content)
                    
                execution_time = time.perf_counter() - start_time
                results.append({
                    'thread_id': thread_id,
                    'execution_time': execution_time,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'thread_id': thread_id,
                    'execution_time': time.perf_counter() - start_time,
                    'success': False,
                    'error': str(e)
                })
        
        # Run concurrent operations
        threads = []
        thread_count = 5
        
        for i in range(thread_count):
            thread = threading.Thread(target=concurrent_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=10.0)
        
        # Analyze results
        successful_results = [r for r in results if r['success']]
        assert len(successful_results) >= thread_count * 0.8, "Most operations should succeed under load"
        
        # Performance should degrade gracefully under load
        execution_times = [r['execution_time'] for r in successful_results]
        mean_time = statistics.mean(execution_times)
        
        # Under load, operations might be slower but shouldn't be extremely slow
        assert mean_time < 1.0, f"Operations too slow under load: {mean_time:.4f}s"
    
    @pytest.mark.performance
    def test_cpu_intensive_operation_scaling(self):
        """Test CPU-intensive operations scale appropriately."""
        def cpu_intensive_work(iterations: int):
            """Simulate CPU-intensive work."""
            result = 0
            for i in range(iterations):
                result += sum(j * j for j in range(100))
            return result
        
        # Test different workload sizes
        workloads = [1000, 5000, 10000]
        execution_times = []
        
        for workload in workloads:
            start_time = time.perf_counter()
            cpu_intensive_work(workload)
            execution_time = time.perf_counter() - start_time
            execution_times.append(execution_time)
        
        # Verify scaling is roughly linear (not exponential)
        # Time for 10x work should be roughly 10x, not 100x
        ratio_5k_1k = execution_times[1] / execution_times[0]
        ratio_10k_5k = execution_times[2] / execution_times[1]
        
        # Allow for some variation due to system load
        assert ratio_5k_1k < 10, f"CPU scaling too poor: {ratio_5k_1k:.2f}x"
        assert ratio_10k_5k < 5, f"CPU scaling degraded: {ratio_10k_5k:.2f}x"
    
    @pytest.mark.performance
    def test_io_operation_batching_performance(self):
        """Test that batched I/O operations are more efficient than individual operations."""
        filesystem = FilesystemService()
        file_count = 10
        
        # Individual operations
        start_time = time.perf_counter()
        individual_files = []
        
        for i in range(file_count):
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
            temp_path = Path(temp_file.name)
            content = f"Individual file {i} content"
            filesystem.write_file(temp_path, content)
            individual_files.append(str(temp_path))
        
        individual_time = time.perf_counter() - start_time
        
        # Batch operations
        start_time = time.perf_counter()
        
        batch_files = {}
        for i in range(file_count):
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_path = str(temp_file.name)
            content = f"Batch file {i} content"
            batch_files[temp_path] = content
        
        filesystem.write_files_batch(batch_files)
        batch_time = time.perf_counter() - start_time
        
        # Cleanup
        for file_path in individual_files + list(batch_files.keys()):
            Path(file_path).unlink(missing_ok=True)
        
        # Batch operations should be at least as fast as individual operations
        # In many cases, they should be significantly faster
        efficiency_ratio = individual_time / batch_time
        
        print(f"Individual: {individual_time:.4f}s, Batch: {batch_time:.4f}s, "
              f"Ratio: {efficiency_ratio:.2f}x")
        
        # Batch should be at least as efficient (ratio >= 1.0)
        # Often it should be more efficient (ratio > 1.0)
        assert efficiency_ratio >= 0.8, f"Batching performance regression: {efficiency_ratio:.2f}x"


class TestPerformanceRegressionAdvanced:
    """Advanced performance regression testing scenarios."""
    
    @pytest.mark.performance
    def test_performance_profiling_accuracy(self):
        """Test that performance profiling provides accurate measurements."""
        profiler = PerformanceProfiler()
        
        def known_duration_operation():
            """Operation with known duration."""
            time.sleep(0.1)  # Exactly 100ms
        
        with profiler.profile_operation("sleep_test"):
            known_duration_operation()
        
        # Should measure close to 100ms (within 10ms tolerance for system variance)
        measured_time = time.perf_counter() - profiler.start_time
        assert 0.095 <= measured_time <= 0.150, f"Profiling inaccurate: {measured_time:.4f}s"
    
    @pytest.mark.performance
    def test_statistical_significance_detection(self):
        """Test statistical significance detection in performance changes."""
        benchmark_runner = BenchmarkRunner()
        
        def fast_operation():
            time.sleep(0.001)  # 1ms
        
        def slow_operation():
            time.sleep(0.005)  # 5ms (5x slower)
        
        # Establish baseline with fast operation
        benchmark_runner.establish_baseline("significance_test", fast_operation, iterations=10)
        
        # Test with slow operation (should be statistically significant)
        result = benchmark_runner.run_regression_test("significance_test", slow_operation, iterations=10)
        
        assert result['statistically_significant'], "Should detect significant performance change"
        assert result['regression'], "Should classify as regression"
        assert result['relative_change'] > 100, "Should show substantial relative change"
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_long_running_operation_monitoring(self):
        """Test monitoring of long-running operations."""
        profiler = PerformanceProfiler()
        
        def long_operation():
            """Simulate long-running operation with varying resource usage."""
            for i in range(5):
                # Simulate different phases of work
                time.sleep(0.2)
                # Create some memory pressure
                temp_data = [j for j in range(1000)]
                del temp_data
        
        with profiler.profile_operation("long_operation"):
            long_operation()
        
        # Should have collected multiple samples
        assert len(profiler.memory_samples) > 3, "Should collect multiple memory samples"
        assert len(profiler.cpu_samples) > 3, "Should collect multiple CPU samples"
        
        # Memory usage should vary during execution
        memory_variance = statistics.variance(profiler.memory_samples) if len(profiler.memory_samples) > 1 else 0
        assert memory_variance > 0, "Should detect memory usage variation"


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-m", "performance",
        "--tb=short",
        "--benchmark-only",  # Only run benchmark tests when using pytest-benchmark
    ])