"""Test configuration for new Crackerjack features."""

from contextlib import contextmanager
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest

from acb.console import Console
from acb.depends import depends


def pytest_configure(config):
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")


@pytest.fixture
def sample_test_data():
    """Sample test data for new feature tests."""
    return {
        "files": [
            {"name": "test.py", "content": "print('hello world')"},
            {"name": "main.py", "content": "def main(): pass"},
        ],
        "hooks": [
            {"name": "black", "status": "passed"},
            {"name": "ruff", "status": "failed", "error": "Import not found"},
        ],
        "test_results": [
            {"name": "test_example", "status": "passed", "duration": 0.1},
            {"name": "test_failure", "status": "failed", "error": "AssertionError"},
        ],
    }


@contextmanager
def acb_depends_context(injection_map: dict[type, Any]) -> Generator[None, None, None]:
    """Context manager for setting up ACB dependency injection in tests.

    Usage:
        with acb_depends_context({Console: mock_console}):
            # Your test code here
            pass
    """
    original_values = {}
    try:
        # Save original values and set new ones
        for dep_type, dep_value in injection_map.items():
            try:
                original_values[dep_type] = depends.get_sync(dep_type)
            except Exception:
                # Dependency not registered yet
                original_values[dep_type] = None
            depends.set(dep_type, dep_value)
        yield
    finally:
        # Restore original values
        for dep_type, original_value in original_values.items():
            if original_value is not None:
                depends.set(dep_type, original_value)


@pytest.fixture
def mock_console() -> MagicMock:
    """Fixture providing a mock console for tests."""
    return MagicMock(spec=Console)


@pytest.fixture
def acb_di_fixture(mock_console: MagicMock) -> Generator[dict[type, Any], None, None]:
    """Fixture providing ACB dependency injection setup for tests.

    Usage:
        def test_something(acb_di_fixture):
            # DI is automatically set up
            coordinator = SessionCoordinator(console=acb_di_fixture[Console], ...)
    """
    with acb_depends_context({Console: mock_console}):
        yield {Console: mock_console}
