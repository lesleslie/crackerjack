"""Tests for Dhara adapter learning integration."""

from __future__ import annotations

import typing as t
from datetime import datetime
from pathlib import Path

import pytest

from crackerjack.integration import (
    AdapterAttemptRecord,
    DharaLearningIntegration,
    NoOpAdapterLearner,
    SQLiteAdapterLearner,
    create_adapter_learner,
)
from crackerjack.integration.dhara_mcp_client import DharaMCPConfig

_DHARA_HAS_ASYNC_CONNECTION = True
try:
    from dhara.core.connection import AsyncConnection  # noqa: F401
except ImportError:
    _DHARA_HAS_ASYNC_CONNECTION = False

requires_dhara_async_connection = pytest.mark.skipif(
    not _DHARA_HAS_ASYNC_CONNECTION,
    reason=(
        "Dhara backend too old (no AsyncConnection in dhara.core.connection); "
        "these tests require a newer Dhara"
    ),
)


class TestAdapterAttemptRecord:
    """Test AdapterAttemptRecord data model."""

    def test_create_record(self) -> None:
        record = AdapterAttemptRecord(
            adapter_name="ruff",
            file_type=".py",
            file_size=1024,
            project_context={"phase": "fast"},
            success=True,
            execution_time_ms=150,
            error_type=None,
            timestamp=datetime.now(),
        )
        assert record.adapter_name == "ruff"
        assert record.success is True

    def test_roundtrip(self) -> None:
        record = AdapterAttemptRecord(
            adapter_name="bandit",
            file_type=".py",
            file_size=2048,
            project_context={},
            success=False,
            execution_time_ms=300,
            error_type="SecurityError",
            timestamp=datetime.now(),
        )
        restored = AdapterAttemptRecord.from_dict(record.to_dict())
        assert restored.adapter_name == record.adapter_name
        assert restored.file_type == record.file_type
        assert restored.success == record.success
        assert restored.error_type == record.error_type


class TestNoOpAdapterLearner:
    """Test NoOpAdapterLearner does nothing."""

    def test_is_noop(self) -> None:
        learner = NoOpAdapterLearner()
        assert not learner.is_enabled()

    def test_record_is_noop(self) -> None:
        learner = NoOpAdapterLearner()
        record = AdapterAttemptRecord(
            adapter_name="ruff",
            file_type=".py",
            file_size=100,
            project_context={},
            success=True,
            execution_time_ms=50,
            error_type=None,
            timestamp=datetime.now(),
        )
        # Should not raise
        learner.record_adapter_attempt(record)

    def test_recommend_returns_none(self) -> None:
        learner = NoOpAdapterLearner()
        assert learner.recommend_adapter("test.py", {}, ["ruff"]) is None

    def test_get_effectiveness_returns_none(self) -> None:
        learner = NoOpAdapterLearner()
        assert learner.get_adapter_effectiveness("ruff", ".py") is None

    def test_get_best_adapters_returns_empty(self) -> None:
        learner = NoOpAdapterLearner()
        assert learner.get_best_adapters_for_file_type(".py") == []


class TestCreateAdapterLearner:
    """Test factory function."""

    def test_disabled_returns_noop(self) -> None:
        learner = create_adapter_learner(enabled=False)
        assert isinstance(learner, NoOpAdapterLearner)

    def test_enabled_returns_sqlite(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_adapter_learning.db"
        learner = create_adapter_learner(
            enabled=True, db_path=db_path, backend="sqlite"
        )
        assert isinstance(learner, SQLiteAdapterLearner)
        assert learner.is_enabled()

    def test_enabled_creates_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_adapter_learning.db"
        create_adapter_learner(enabled=True, db_path=db_path, backend="sqlite")
        assert db_path.exists()


class TestSQLiteAdapterLearner:
    """Test SQLite adapter learner with real database."""

    def test_record_and_get_effectiveness(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path)

        record = AdapterAttemptRecord(
            adapter_name="ruff",
            file_type=".py",
            file_size=500,
            project_context={},
            success=True,
            execution_time_ms=100,
            error_type=None,
            timestamp=datetime.now(),
        )
        learner.record_adapter_attempt(record)

        effectiveness = learner.get_adapter_effectiveness("ruff", ".py")
        assert effectiveness is not None
        assert effectiveness.adapter_name == "ruff"
        assert effectiveness.total_attempts == 1
        assert effectiveness.successful_attempts == 1
        assert effectiveness.success_rate == 1.0

    def test_get_best_adapters(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path, min_attempts=1)

        for i in range(3):
            record = AdapterAttemptRecord(
                adapter_name="ruff",
                file_type=".py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=100,
                error_type=None,
                timestamp=datetime.now(),
            )
            learner.record_adapter_attempt(record)

        best = learner.get_best_adapters_for_file_type(".py")
        assert len(best) >= 1
        assert best[0][0] == "ruff"

    def test_recommend_after_enough_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path, min_attempts=3)

        for _ in range(5):
            record = AdapterAttemptRecord(
                adapter_name="ruff",
                file_type=".py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=100,
                error_type=None,
                timestamp=datetime.now(),
            )
            learner.record_adapter_attempt(record)

        rec = learner.recommend_adapter("test.py", {}, ["ruff", "bandit"])
        assert rec == "ruff"


class TestDharaLearningIntegration:
    """Test DharaLearningIntegration wrapper."""

    def test_tracks_via_learner(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path)
        integration = DharaLearningIntegration(adapter_learner=learner)

        integration.track_adapter_execution(
            adapter_name="ruff",
            file_path="test.py",
            file_size=1024,
            project_context={},
            success=True,
            execution_time_ms=200,
        )

        effectiveness = integration.get_adapter_stats("ruff", ".py")
        assert effectiveness is not None
        assert effectiveness.total_attempts == 1

    def test_get_recommendation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        learner = SQLiteAdapterLearner(db_path=db_path, min_attempts=2)
        integration = DharaLearningIntegration(adapter_learner=learner)

        for _ in range(3):
            integration.track_adapter_execution(
                adapter_name="bandit",
                file_path="test.py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=300,
            )

        rec = integration.get_adapter_recommendation(
            file_path="test.py",
            project_context={},
            available_adapters=["bandit", "ruff"],
        )
        assert rec == "bandit"

    def test_noop_integration_does_nothing(self) -> None:
        learner = NoOpAdapterLearner()
        integration = DharaLearningIntegration(adapter_learner=learner)

        integration.track_adapter_execution(
            adapter_name="ruff",
            file_path="test.py",
            file_size=100,
            project_context={},
            success=True,
            execution_time_ms=50,
        )

        assert integration.get_adapter_stats("ruff", ".py") is None


@requires_dhara_async_connection
class TestDharaAdapterLearner:
    """Test DharaAdapterLearner with real Dhara storage."""

    @pytest.fixture()
    def dhara_learner(self, tmp_path: Path):
        """Create a DharaAdapterLearner. Skips if dhara not installed."""
        pytest.importorskip("dhara")
        db_path = tmp_path / "dhara_test.db"
        from crackerjack.integration.dhara_integration import DharaAdapterLearner

        learner = DharaAdapterLearner(db_path=db_path)
        yield learner
        learner.close()

    def test_records_attempt(self, dhara_learner) -> None:
        record = AdapterAttemptRecord(
            adapter_name="ruff",
            file_type=".py",
            file_size=1024,
            project_context={},
            success=True,
            execution_time_ms=200,
            error_type=None,
            timestamp=datetime.now(),
        )
        dhara_learner.record_adapter_attempt(record)

        effectiveness = dhara_learner.get_adapter_effectiveness("ruff", ".py")
        assert effectiveness is not None
        assert effectiveness.total_attempts == 1
        assert effectiveness.successful_attempts == 1
        assert effectiveness.success_rate == 1.0
        assert effectiveness.avg_execution_time_ms == 200.0

    def test_accumulates_effectiveness(self, dhara_learner) -> None:
        for i in range(5):
            record = AdapterAttemptRecord(
                adapter_name="ruff",
                file_type=".py",
                file_size=1024,
                project_context={},
                success=True if i < 4 else False,
                execution_time_ms=100 + i * 10,
                error_type="SyntaxError" if i == 4 else None,
                timestamp=datetime.now(),
            )
            dhara_learner.record_adapter_attempt(record)

        effectiveness = dhara_learner.get_adapter_effectiveness("ruff", ".py")
        assert effectiveness is not None
        assert effectiveness.total_attempts == 5
        assert effectiveness.successful_attempts == 4
        assert effectiveness.success_rate == 0.8
        assert ("SyntaxError", 1) in effectiveness.common_errors

    def test_recommendation_after_enough_data(self, dhara_learner) -> None:
        dhara_learner.min_attempts = 3

        for _ in range(5):
            record = AdapterAttemptRecord(
                adapter_name="ruff",
                file_type=".py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=100,
                error_type=None,
                timestamp=datetime.now(),
            )
            dhara_learner.record_adapter_attempt(record)

        rec = dhara_learner.recommend_adapter("test.py", {}, ["ruff", "bandit"])
        assert rec == "ruff"

    def test_get_best_adapters_for_file_type(self, dhara_learner) -> None:
        dhara_learner.min_attempts = 2

        for _ in range(4):
            record = AdapterAttemptRecord(
                adapter_name="ruff",
                file_type=".py",
                file_size=500,
                project_context={},
                success=True,
                execution_time_ms=100,
                error_type=None,
                timestamp=datetime.now(),
            )
            dhara_learner.record_adapter_attempt(record)

        for _ in range(3):
            record = AdapterAttemptRecord(
                adapter_name="mypy",
                file_type=".py",
                file_size=500,
                project_context={},
                success=False,
                execution_time_ms=300,
                error_type="TypeError",
                timestamp=datetime.now(),
            )
            dhara_learner.record_adapter_attempt(record)

        best = dhara_learner.get_best_adapters_for_file_type(".py")
        assert len(best) >= 1
        assert best[0][0] == "ruff"
        assert best[0][1] > best[1][1]  # ruff rate > mypy rate

    def test_close_disables_learner(self, dhara_learner) -> None:
        dhara_learner.close()
        assert not dhara_learner.is_enabled()
        assert dhara_learner.recommend_adapter("test.py", {}, ["ruff"]) is None
        assert dhara_learner.get_best_adapters_for_file_type(".py") == []
        assert dhara_learner.get_adapter_effectiveness("ruff", ".py") is None

    def test_close_nullifies_async_connection(self, dhara_learner) -> None:
        """close() must nullify _async_connection to prevent stale reference reuse."""
        # Verify initialized state
        assert dhara_learner._initialized is True
        assert dhara_learner._async_connection is not None

        # Close
        dhara_learner.close()

        # After close, _async_connection must be None
        assert dhara_learner._async_connection is None, (
            "Stale _async_connection remains after close()"
        )
        assert dhara_learner._initialized is False


class TestFactoryBackendSelection:
    """Test factory backend selection logic."""

    @requires_dhara_async_connection
    def test_auto_backend_with_dhara_available(self, tmp_path: Path) -> None:
        pytest.importorskip("dhara")
        from crackerjack.integration.dhara_integration import DharaAdapterLearner

        db_path = tmp_path / "auto_test.db"
        # Force the factory down the in-process Dhara path: MCP is
        # preferred in the new chain, but for this test we want to
        # verify the in-process Dhara path is still selected when MCP
        # is disabled.
        import crackerjack.integration.dhara_integration as mod

        monkeypatch_obj = pytest.MonkeyPatch()
        monkeypatch_obj.setattr(
            mod, "_load_dhara_mcp_config", lambda: DharaMCPConfig(enabled=False)
        )
        try:
            learner = create_adapter_learner(
                enabled=True,
                backend="auto",
                db_path=db_path,
            )
        finally:
            monkeypatch_obj.undo()
        assert isinstance(learner, DharaAdapterLearner)
        assert learner.db_path.suffix == ".dhara"
        assert learner.db_path.name.endswith(".dhara")

    def test_sqlite_backend_explicit(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sqlite_test.db"
        learner = create_adapter_learner(
            enabled=True,
            backend="sqlite",
            db_path=db_path,
        )
        assert isinstance(learner, SQLiteAdapterLearner)

    def test_dhara_backend_falls_back_to_noop_when_unavailable(
        self, tmp_path: Path
    ) -> None:
        """When dhara import fails and backend='dhara', return NoOp."""
        from unittest.mock import patch

        db_path = tmp_path / "no_dhara_test.db"

        # Disable the MCP path so the in-process Dhara fallback is exercised.
        import crackerjack.integration.dhara_integration as mod

        monkeypatch_obj = pytest.MonkeyPatch()
        monkeypatch_obj.setattr(
            mod, "_load_dhara_mcp_config", lambda: DharaMCPConfig(enabled=False)
        )
        try:
            with patch.dict(
                "sys.modules",
                {
                    "dhara": None,
                    "dhara.core": None,
                    "dhara.core.connection": None,
                    "dhara.mcp": None,
                    "dhara.mcp.kv_timeseries": None,
                },
            ):
                learner = create_adapter_learner(
                    enabled=True,
                    backend="dhara",
                    db_path=db_path,
                )
        finally:
            monkeypatch_obj.undo()
        assert isinstance(learner, NoOpAdapterLearner)

    def test_auto_backend_falls_back_to_sqlite_when_dhara_unavailable(
        self, tmp_path: Path
    ) -> None:
        """When dhara import fails and backend='auto', fall back to SQLite."""
        from unittest.mock import patch

        db_path = tmp_path / "auto_fallback_test.db"

        # Disable the MCP path so the in-process Dhara fallback is exercised.
        import crackerjack.integration.dhara_integration as mod

        monkeypatch_obj = pytest.MonkeyPatch()
        monkeypatch_obj.setattr(
            mod, "_load_dhara_mcp_config", lambda: DharaMCPConfig(enabled=False)
        )
        try:
            with patch.dict(
                "sys.modules",
                {
                    "dhara": None,
                    "dhara.core": None,
                    "dhara.core.connection": None,
                    "dhara.mcp": None,
                    "dhara.mcp.kv_timeseries": None,
                },
            ):
                learner = create_adapter_learner(
                    enabled=True,
                    backend="auto",
                    db_path=db_path,
                )
        finally:
            monkeypatch_obj.undo()
        assert isinstance(learner, SQLiteAdapterLearner)
        assert learner.is_enabled()

    def test_sqlite_backend_falls_back_to_later_candidate_path(
        self, tmp_path: Path
    ) -> None:
        """When the first SQLite candidate fails, a later candidate should be used."""
        import crackerjack.integration.dhara_integration as mod

        requested_path = tmp_path / "readonly" / "adapter_learning.db"
        calls: list[Path] = []

        class FakeSQLiteLearner:
            def __init__(self, db_path: Path, min_attempts: int) -> None:
                calls.append(db_path)
                if len(calls) == 1:
                    raise OSError("Operation not permitted")
                self.db_path = db_path
                self._initialized = True

            def is_enabled(self) -> bool:
                return True

        original = mod.SQLiteAdapterLearner
        mod.SQLiteAdapterLearner = FakeSQLiteLearner  # type: ignore[assignment]
        try:
            learner = create_adapter_learner(
                enabled=True,
                backend="sqlite",
                db_path=requested_path,
            )
        finally:
            mod.SQLiteAdapterLearner = original  # type: ignore[assignment]

        assert calls[0] == requested_path
        assert learner.db_path != requested_path
        assert learner.is_enabled()


@requires_dhara_async_connection
def test_record_adapter_attempt_single_event_loop(tmp_path):
    """record_adapter_attempt must use a single asyncio.run() call, not multiple."""
    pytest.importorskip("dhara")
    import asyncio
    from unittest.mock import patch

    from crackerjack.integration.dhara_integration import DharaAdapterLearner

    db_path = tmp_path / "test_single_loop.db"
    learner = DharaAdapterLearner(db_path=db_path)

    attempt = AdapterAttemptRecord(
        adapter_name="test_adapter",
        file_type=".py",
        file_size=100,
        project_context={"project": "test"},
        success=True,
        execution_time_ms=50,
        error_type=None,
        timestamp=datetime.now(),
    )

    # Patch asyncio.run to track call count
    run_count = 0
    original_run = asyncio.run

    def counting_run(coro):
        nonlocal run_count
        run_count += 1
        return original_run(coro)

    with patch("asyncio.run", side_effect=counting_run):
        learner.record_adapter_attempt(attempt)

    # Must be exactly 1 asyncio.run() call, not 6
    assert run_count == 1, f"Expected 1 asyncio.run() call, got {run_count}"

    learner.close()


def test_factory_prefers_mcp_when_server_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the Dhara MCP server is reachable, the factory returns
    `DharaMCPAdapterLearner`."""
    from crackerjack.integration import dhara_integration

    monkeypatch.setattr(
        dhara_integration,
        "_load_dhara_mcp_config",
        lambda: DharaMCPConfig(enabled=True),
    )

    class _StubLearner:
        def __init__(self, config: DharaMCPConfig) -> None:
            pass

    monkeypatch.setattr(dhara_integration, "DharaMCPAdapterLearner", _StubLearner)

    learner = dhara_integration.create_adapter_learner(enabled=True, backend="auto")
    assert isinstance(learner, _StubLearner)


def test_factory_falls_back_to_noop_when_everything_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If all backends fail, the factory returns NoOpAdapterLearner."""
    from crackerjack.integration import dhara_integration
    from crackerjack.integration.dhara_integration import NoOpAdapterLearner

    monkeypatch.setattr(
        dhara_integration,
        "_load_dhara_mcp_config",
        lambda: DharaMCPConfig(enabled=False),
    )

    def _raise_dhara(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        raise RuntimeError("AsyncConnection missing")

    def _raise_sqlite(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        raise OSError("locked")

    monkeypatch.setattr(dhara_integration, "DharaAdapterLearner", _raise_dhara)
    monkeypatch.setattr(dhara_integration, "SQLiteAdapterLearner", _raise_sqlite)

    learner = dhara_integration.create_adapter_learner(enabled=True, backend="auto")
    assert isinstance(learner, NoOpAdapterLearner)


def test_factory_respects_dhara_mcp_disabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `dhara_mcp.enabled` is False, the factory must skip the
    MCP path and fall through to in-process / SQLite / NoOp.
    """
    from crackerjack.integration import dhara_integration

    monkeypatch.setattr(
        dhara_integration,
        "_load_dhara_mcp_config",
        lambda: DharaMCPConfig(enabled=False),
    )

    used_dhara_mcp = False

    class _SpyMCP:
        def __init__(self, config: DharaMCPConfig) -> None:
            nonlocal used_dhara_mcp
            used_dhara_mcp = True

    def _raise_init(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        raise RuntimeError("init failed")

    monkeypatch.setattr(dhara_integration, "DharaMCPAdapterLearner", _SpyMCP)
    monkeypatch.setattr(dhara_integration, "DharaAdapterLearner", _raise_init)
    monkeypatch.setattr(dhara_integration, "SQLiteAdapterLearner", _raise_init)

    dhara_integration.create_adapter_learner(enabled=True, backend="auto")
    assert not used_dhara_mcp
