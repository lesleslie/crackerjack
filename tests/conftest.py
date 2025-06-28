import os
import time
import typing as t
from pathlib import Path

import pytest
from pytest import Config, Item, Parser


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers", "benchmark: mark test as a benchmark (disables parallel execution)"
    )
    if not hasattr(config, "workerinput"):
        benchmark_regression = config.getoption("--benchmark-regression")
        if benchmark_regression:
            threshold_str = str(config.getoption("--benchmark-regression-threshold"))
            threshold = float(threshold_str) / 100.0
            os.environ["BENCHMARK_THRESHOLD"] = str(threshold)


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--benchmark",
        action="store_true",
        default=False,
        help="Run benchmark tests and disable parallelism",
    )
    parser.addoption(
        "--benchmark-regression",
        action="store_true",
        default=False,
        help="Fail tests if benchmarks regress beyond threshold",
    )
    group = parser.getgroup("benchmark")
    group.addoption(
        "--benchmark-regression-threshold",
        action="store",
        default="5.0",
        help="Regression threshold in percent (default: 5.0%%)",
    )


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    benchmark_mode = t.cast(bool, config.getoption("--benchmark"))
    has_benchmark_tests = any(item.get_closest_marker("benchmark") for item in items)
    if benchmark_mode or has_benchmark_tests:
        has_worker = hasattr(config, "workerinput")
        try:
            num_processes = t.cast(int, config.getoption("numprocesses"))
            has_multi_processes = num_processes > 0
        except Exception:
            has_multi_processes = False
        if has_worker or has_multi_processes:
            config.option.numprocesses = 0
            print(
                "Benchmark tests detected: Disabling parallel execution for accurate timing"
            )


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item: t.Any) -> None:
    item._start_time = time.time()
    print(f"Starting test: {item.name}")


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: t.Any) -> None:
    if hasattr(item, "_start_time"):
        duration = time.time() - item._start_time
        if duration > 10:
            print(f"SLOW TEST: {item.name} took {duration:.2f}s")
        else:
            print(f"Test completed: {item.name} in {duration:.2f}s")


@pytest.hookimpl(trylast=True)
def pytest_runtest_protocol(item: t.Any) -> None:
    Path(".current_test").write_text(f"Current test: {item.name}")


def pytest_benchmark_compare_machine_info(
    machine_info: dict[str, t.Any], compared_benchmark: t.Any
) -> bool:
    return True


def pytest_benchmark_generate_commit_info(config: Config) -> dict[str, t.Any]:
    return {"id": "current", "time": time.time(), "project_name": "crackerjack"}
