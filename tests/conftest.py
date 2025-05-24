"""Pytest configuration file with hooks for detecting slow and hanging tests."""

import time
from pathlib import Path
from typing import Any

import pytest


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item: Any) -> None:
    item._start_time = time.time()
    print(f"Starting test: {item.name}")


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: Any) -> None:
    if hasattr(item, "_start_time"):
        duration = time.time() - item._start_time
        if duration > 10:
            print(f"SLOW TEST: {item.name} took {duration:.2f}s")
        else:
            print(f"Test completed: {item.name} in {duration:.2f}s")


@pytest.hookimpl(trylast=True)
def pytest_runtest_protocol(item: Any) -> None:
    Path(".current_test").write_text(f"Current test: {item.name}")
