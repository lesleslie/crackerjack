"""Conftest to disable the autouse fixture for websocket auth tests."""
import pytest


@pytest.fixture(autouse=True)
def disable_hook_lock_manager(request):
    """Disable the global autouse fixture for these tests."""
    # Remove the autouse fixture from parent conftest
    request.getfixturevalue.__wrapped__ = request.getfixturevalue
    yield
