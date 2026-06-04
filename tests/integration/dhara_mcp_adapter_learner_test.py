"""Integration tests for `DharaMCPAdapterLearner`.

The learner is the crackerjack-side bridge to the Dhara MCP server.
It translates each `AdapterAttemptRecord` into a `record_time_series`
tool call. These tests use mock clients to verify the translation
without needing a live Dhara server.
"""

from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.integration.dhara_mcp_client import (
    DharaMCPClient,
    DharaMCPConfig,
)
from crackerjack.integration.dhara_integration import (
    AdapterAttemptRecord,
    DharaMCPAdapterLearner,
)


def _make_attempt(
    *, success: bool = True, error_type: str | None = None
) -> AdapterAttemptRecord:
    """Build an `AdapterAttemptRecord` for tests."""
    return AdapterAttemptRecord(
        adapter_name="prefect",
        file_type="py",
        file_size=100,
        project_context={"path": "/tmp/test"},
        success=success,
        execution_time_ms=42,
        error_type=error_type,
        timestamp=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
    )


def test_dhara_mcp_learner_close_is_idempotent() -> None:
    """`close()` may be called any number of times without raising."""
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    learner.close()
    learner.close()


def test_dhara_mcp_learner_close_swallows_exceptions() -> None:
    """If the underlying disconnect raises, `close()` must not propagate."""
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    learner._client = MagicMock()
    learner._client.disconnect = AsyncMock(side_effect=RuntimeError("boom"))
    learner.close()
