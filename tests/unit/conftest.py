"""Test configuration for unit tests."""

import pytest


@pytest.fixture(autouse=True)
def reset_crackerjack_singletons():
    """Reset all Crackerjack singletons before and after each test.

    This ensures that tests in tests/unit/ subdirectories also get
    the autouse fixture that clears global state, LRU caches, etc.
    """
    from tests.conftest_reset import reset_all_singletons

    reset_all_singletons()
    yield
    reset_all_singletons()
