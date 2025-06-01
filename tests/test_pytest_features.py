"""Tests for pytest timeout and parallel execution features."""

import time

import pytest


def test_normal_execution() -> None:
    assert True


@pytest.mark.timeout(2)
def test_timeout_feature() -> None:
    time.sleep(1)
    assert True


@pytest.mark.xdist_group("group1")
def test_xdist_group1() -> None:
    assert True


@pytest.mark.xdist_group("group1")
def test_xdist_group1_second() -> None:
    assert True


@pytest.mark.xdist_group("group2")
def test_xdist_group2() -> None:
    assert True


def test_slow_but_not_hanging() -> None:
    time.sleep(12)
    assert True


@pytest.mark.skip(reason="This test intentionally hangs to test timeout feature")
def test_hanging() -> None:
    while True:
        time.sleep(1)


@pytest.mark.benchmark
def test_benchmark_marker() -> None:
    """Test that should run without xdist when marked with benchmark."""
    # This test should run without parallelism when the benchmark option is used
    start_time = time.time()
    time.sleep(0.1)  # Small sleep to simulate benchmark work
    end_time = time.time()
    duration = end_time - start_time
    assert duration >= 0.1


@pytest.mark.benchmark
class TestBenchmarkClass:
    """A class that contains benchmark tests."""

    def test_benchmark_in_class(self) -> None:
        """Test that benchmark marker works on classes too."""
        assert True

    def test_benchmark_with_timing(self) -> None:
        """Test with precise timing measurement."""
        results: list[float] = []
        for _ in range(5):
            start = time.time()
            # Simple operation to benchmark
            sum(range(10000))
            end = time.time()
            results.append(end - start)

        # Check that we have consistent results (would fail under high contention)
        assert max(results) - min(results) < 0.1
