"""Pytest configuration file with hooks for detecting slow and hanging tests."""

import time
import typing as t
from pathlib import Path

import pytest
from pytest import Config, Item, Parser


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers", "benchmark: mark test as a benchmark (disables parallel execution)"
    )


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--benchmark",
        action="store_true",
        default=False,
        help="Run benchmark tests and disable parallelism",
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
