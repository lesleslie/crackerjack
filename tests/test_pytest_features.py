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
    start_time = time.time()
    time.sleep(0.1)
    end_time = time.time()
    duration = end_time - start_time
    assert duration >= 0.1


@pytest.mark.benchmark
class TestBenchmarkClass:
    def test_benchmark_in_class(self) -> None:
        assert True

    def test_benchmark_with_timing(self) -> None:
        results: list[float] = []
        for _ in range(5):
            start = time.time()
            sum(range(10000))
            end = time.time()
            results.append(end - start)
        assert max(results) - min(results) < 0.1
