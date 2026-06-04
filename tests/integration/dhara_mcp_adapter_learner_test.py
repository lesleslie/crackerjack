"""Integration tests for `DharaMCPAdapterLearner`.

The learner is the crackerjack-side bridge to the Dhara MCP server.
It translates each `AdapterAttemptRecord` into a `record_time_series`
tool call. These tests use mock clients to verify the translation
without needing a live Dhara server.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from crackerjack.integration.dhara_integration import (
    AdapterAttemptRecord,
    DharaMCPAdapterLearner,
)
from crackerjack.integration.dhara_mcp_client import (
    DharaMCPConfig,
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


def test_dhara_mcp_learner_record_includes_pattern_key() -> None:
    """`record_adapter_attempt` must include a `pattern` key in the
    record body for `aggregate_patterns` to group on.
    """
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    learner._client = MagicMock()
    learner._client.connect = AsyncMock(return_value=True)
    learner._client.record_time_series = AsyncMock()

    attempt = _make_attempt(success=True)
    learner.record_adapter_attempt(attempt)

    learner._client.record_time_series.assert_awaited_once()
    call_args = learner._client.record_time_series.await_args
    assert call_args.kwargs["metric_type"] == "adapter_attempt"
    assert call_args.kwargs["entity_id"] == "prefect"
    record = call_args.kwargs["record"]
    assert record["pattern"] == "success:prefect"
    assert record["success"] is True
    assert record["execution_time_ms"] == 42


def test_dhara_mcp_learner_pattern_handles_failure_without_error_type() -> None:
    """When a failed attempt has no error_type, the pattern must
    default to `error:unknown` so `aggregate_patterns` still groups
    consistently.
    """
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    attempt = _make_attempt(success=False, error_type=None)
    assert learner._derive_pattern(attempt) == "error:unknown"


def test_dhara_mcp_learner_record_skips_when_connect_fails() -> None:
    """When the MCP server is unreachable (`connect()` returns False),
    `record_adapter_attempt` must not raise and must not call
    `record_time_series` (no point in talking to a server we never
    connected to).
    """
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    learner._client = MagicMock()
    learner._client.connect = AsyncMock(return_value=False)
    learner._client.record_time_series = AsyncMock()

    attempt = _make_attempt(success=True)
    learner.record_adapter_attempt(attempt)

    learner._client.connect.assert_awaited_once()
    learner._client.record_time_series.assert_not_called()


def test_dhara_mcp_learner_is_enabled_reads_config() -> None:
    """`is_enabled` must reflect the client config (the kill switch)."""
    learner = DharaMCPAdapterLearner(
        DharaMCPConfig(url="http://test/mcp", enabled=False)
    )
    assert learner.is_enabled() is False

    learner2 = DharaMCPAdapterLearner(
        DharaMCPConfig(url="http://test/mcp", enabled=True)
    )
    assert learner2.is_enabled() is True
