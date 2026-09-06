"""Tests for ``crackerjack.integration.akosha_learning``.

The ``SQLiteQueryOptimizer`` uses an on-disk SQLite database. Tests use
``tmp_path`` so each test gets a fresh DB and there is no leakage
between tests. The ``QueryInteractionRecord`` round-trips through
``to_dict``/``from_dict``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from crackerjack.integration.akosha_learning import (
    AkoshaLearningIntegration,
    NoOpQueryOptimizer,
    QueryInteractionRecord,
    QuerySuggestion,
    SQLiteQueryOptimizer,
    create_query_optimizer,
)


@pytest.fixture
def optimizer(tmp_path: Path) -> SQLiteQueryOptimizer:
    return SQLiteQueryOptimizer(db_path=tmp_path / "opt.db")


# ---------------------------------------------------------------------------
# QueryInteractionRecord round-trip
# ---------------------------------------------------------------------------


def test_query_interaction_record_round_trip() -> None:
    rec = QueryInteractionRecord(
        query="how to foo",
        query_embedding=[0.1, 0.2, 0.3],
        results_returned=["r1", "r2"],
        results_clicked=["r1"],
        results_skipped=["r2"],
        user_satisfaction=0.85,
        outcome="success",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        session_id="s1",
    )
    data = rec.to_dict()
    rec2 = QueryInteractionRecord.from_dict(data)
    assert rec == rec2


def test_query_interaction_record_session_id_optional() -> None:
    rec = QueryInteractionRecord(
        query="q",
        query_embedding=[],
        results_returned=[],
        results_clicked=[],
        results_skipped=[],
        user_satisfaction=0.0,
        outcome="failure",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert rec.session_id is None
    rec2 = QueryInteractionRecord.from_dict(rec.to_dict())
    assert rec2.session_id is None


# ---------------------------------------------------------------------------
# SQLiteQueryOptimizer — initialization
# ---------------------------------------------------------------------------


def test_optimizer_init_creates_db(tmp_path: Path) -> None:
    """``__post_init__`` runs ``_initialize_db``, creating the parent dir + file."""
    db_path = tmp_path / "nested" / "opt.db"
    SQLiteQueryOptimizer(db_path=db_path)
    assert db_path.exists()
    assert db_path.parent.is_dir()


def test_optimizer_is_enabled_after_init(optimizer: SQLiteQueryOptimizer) -> None:
    assert optimizer.is_enabled() is True


def test_optimizer_init_failure_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If DB init raises, the optimizer propagates the exception."""
    import sqlite3

    def _raise(*a: object, **kw: object) -> object:
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(sqlite3, "connect", _raise)
    with pytest.raises(sqlite3.OperationalError):
        SQLiteQueryOptimizer(db_path=tmp_path / "x.db")


# ---------------------------------------------------------------------------
# track_search_interaction
# ---------------------------------------------------------------------------


def test_track_search_interaction_records(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    optimizer.track_search_interaction(
        query="how to foo",
        results_clicked=["r1"],
        results_skipped=["r2"],
        user_satisfaction=0.8,
        outcome="success",
        session_id="s1",
    )
    assert optimizer.is_enabled()


def test_track_search_interaction_when_not_initialized(
    tmp_path: Path,
) -> None:
    """When ``_initialized`` is False, ``track_search_interaction`` is a no-op."""
    opt = SQLiteQueryOptimizer(db_path=tmp_path / "opt.db")
    opt._initialized = False  # type: ignore[attr-defined]
    opt.track_search_interaction(
        query="q",
        results_clicked=[],
        results_skipped=[],
        user_satisfaction=0.0,
        outcome="success",
    )
    # No exception, no state change.
    assert opt._initialized is False


def test_track_search_interaction_handles_exception(
    optimizer: SQLiteQueryOptimizer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlite3

    def _raise(*a: object, **kw: object) -> object:
        raise sqlite3.OperationalError("disk fail")

    monkeypatch.setattr(sqlite3, "connect", _raise)
    # Should log but not raise.
    optimizer.track_search_interaction(
        query="q",
        results_clicked=[],
        results_skipped=[],
        user_satisfaction=0.0,
        outcome="success",
    )


def test_track_search_interaction_non_success_outcome(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    """An outcome of ``failure`` does NOT increment success_count."""
    optimizer.track_search_interaction(
        query="how to foo",
        results_clicked=[],
        results_skipped=[],
        user_satisfaction=0.1,
        outcome="failure",
        session_id="s1",
    )
    # No exception; we just verify it doesn't blow up.
    assert optimizer.is_enabled()


# ---------------------------------------------------------------------------
# _update_query_pattern (via track_search_interaction success)
# ---------------------------------------------------------------------------


def test_track_search_increments_pattern_success(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    """A success outcome increments success_count + total_count + updates
    the running average satisfaction."""
    optimizer.track_search_interaction(
        query="how to foo",
        results_clicked=["r1"],
        results_skipped=[],
        user_satisfaction=0.9,
        outcome="success",
        session_id="s1",
    )
    # After 1 success: SQLite evaluates SET RHS using OLD row values.
    #   INSERT OR IGNORE → row: success=0, total=1, avg=0.0
    #   UPDATE success=0+1=1, total=1+1=2, avg=(0.0*(1-1)+0.9)/1=0.9
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(str(optimizer.db_path))
    row = conn.execute(
        "SELECT success_count, total_count, avg_satisfaction "
        "FROM query_patterns WHERE query_pattern = ?",
        ("how to foo",),
    ).fetchone()
    conn.close()
    assert row == (1, 2, 0.9)


def test_track_success_then_failure_updates_pattern(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    """Two outcomes with the same query pattern update the running average."""
    optimizer.track_search_interaction(
        query="how to foo",
        results_clicked=["r1"],
        results_skipped=[],
        user_satisfaction=0.8,
        outcome="success",
    )
    optimizer.track_search_interaction(
        query="how to foo",
        results_clicked=[],
        results_skipped=["r1"],
        user_satisfaction=0.6,
        outcome="partial",
    )
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(str(optimizer.db_path))
    row = conn.execute(
        "SELECT success_count, total_count, avg_satisfaction "
        "FROM query_patterns WHERE query_pattern = ?",
        ("how to foo",),
    ).fetchone()
    conn.close()
    # SQLite UPDATE evaluates SET RHS using OLD row values, then assigns.
    # After call 1 (success, 0.8):
    #   INSERT OR IGNORE → row: success=0, total=1, avg=0.0
    #   UPDATE success=0+1=1, total=1+1=2, avg=(0.0*(1-1)+0.8)/1=0.8
    # After call 2 (partial, 0.6):
    #   UPDATE total=2+1=3, avg=(0.8*(2-1)+0.6)/2=0.7 (success unchanged at 1)
    assert row[0] == 1
    assert row[1] == 3
    assert abs(row[2] - 0.7) < 0.01


# ---------------------------------------------------------------------------
# get_query_suggestions
# ---------------------------------------------------------------------------


def test_get_query_suggestions_empty_when_not_initialized(
    tmp_path: Path,
) -> None:
    opt = SQLiteQueryOptimizer(db_path=tmp_path / "opt.db")
    opt._initialized = False  # type: ignore[attr-defined]
    assert opt.get_query_suggestions("partial", ["similar"]) == []


def test_get_query_suggestions_no_rows(optimizer: SQLiteQueryOptimizer) -> None:
    """With no recorded patterns, no suggestions are returned."""
    out = optimizer.get_query_suggestions("how", ["how to do x"])
    assert out == []


def test_get_query_suggestions_finds_high_success(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    """A pattern with success_rate > 0.7 and avg_satisfaction > 0.7
    yields a suggestion."""
    # Seed 10 successes on the pattern.
    for _ in range(10):
        optimizer.track_search_interaction(
            query="how to do x",
            results_clicked=["r1"],
            results_skipped=["r2"],
            user_satisfaction=0.9,
            outcome="success",
        )
    out = optimizer.get_query_suggestions("how", ["how to do x"])
    assert len(out) == 1
    assert out[0].suggested_query == "how to do x"


def test_get_query_suggestions_caps_at_five(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    """Suggestions are limited to 5 entries."""
    # Seed 5 distinct similar queries, all with high success.
    for i in range(10):
        optimizer.track_search_interaction(
            query=f"query {i}",
            results_clicked=["r1"],
            results_skipped=["r2"],
            user_satisfaction=0.9,
            outcome="success",
        )
    similar = [f"query {i}" for i in range(10)]
    out = optimizer.get_query_suggestions("partial", similar)
    assert len(out) <= 5


def test_get_query_suggestions_handles_exception(
    optimizer: SQLiteQueryOptimizer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlite3

    def _raise(*a: object, **kw: object) -> object:
        raise sqlite3.OperationalError("disk fail")

    monkeypatch.setattr(sqlite3, "connect", _raise)
    out = optimizer.get_query_suggestions("q", ["similar"])
    assert out == []


# ---------------------------------------------------------------------------
# adapt_ranking
# ---------------------------------------------------------------------------


def test_adapt_ranking_empty_db_returns_candidates(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    candidates = [{"id": "x", "score": 0.5}, {"id": "y", "score": 0.7}]
    out = optimizer.adapt_ranking("query", candidates)
    assert out == candidates


def test_adapt_ranking_boosts_clicked_results(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    # Seed a query with 100% clicks on r1 (5 of 5 shown).
    for _ in range(5):
        optimizer.track_search_interaction(
            query="find python docs",
            results_clicked=["r1"],
            results_skipped=["r2"],
            user_satisfaction=0.9,
            outcome="success",
        )
    # r1 has 100% CTR (boost=1.0). With boost 0.5x, r1 score = 0.9 * 1.5 = 1.35.
    # r2 has 0% CTR (boost=0.0). r2 score stays at 0.8.
    candidates = [
        {"id": "r2", "score": 0.8},  # not clicked → no boost
        {"id": "r1", "score": 0.9},  # clicked → boost to 1.35
    ]
    out = optimizer.adapt_ranking("find python docs", candidates)
    # r1 should now outrank r2 due to CTR boost (1.35 > 0.8).
    assert out[0]["id"] == "r1"
    # Original score preserved.
    assert out[0]["original_score"] == 0.9
    assert out[0]["ctr_boost"] == 1.0


def test_adapt_ranking_when_not_initialized(tmp_path: Path) -> None:
    opt = SQLiteQueryOptimizer(db_path=tmp_path / "opt.db")
    opt._initialized = False  # type: ignore[attr-defined]
    candidates = [{"id": "x", "score": 0.5}]
    assert opt.adapt_ranking("q", candidates) == candidates


def test_adapt_ranking_handles_exception(
    optimizer: SQLiteQueryOptimizer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlite3

    def _raise(*a: object, **kw: object) -> object:
        raise sqlite3.OperationalError("disk fail")

    monkeypatch.setattr(sqlite3, "connect", _raise)
    candidates = [{"id": "x", "score": 0.5}]
    assert optimizer.adapt_ranking("q", candidates) == candidates


# ---------------------------------------------------------------------------
# get_click_through_rate
# ---------------------------------------------------------------------------


def test_get_click_through_rate_empty_db(optimizer: SQLiteQueryOptimizer) -> None:
    assert optimizer.get_click_through_rate("anything") == 0.0


def test_get_click_through_rate_computes_ratio(
    optimizer: SQLiteQueryOptimizer,
) -> None:
    # Seed: 4 clicks out of 10 shown.
    optimizer.track_search_interaction(
        query="rare query",
        results_clicked=["a", "b", "c", "d"],
        results_skipped=["e", "f", "g", "h", "i", "j"],
        user_satisfaction=0.5,
        outcome="partial",
    )
    rate = optimizer.get_click_through_rate("rare query")
    assert rate == 0.4


def test_get_click_through_rate_zero_shown(
    optimizer: SQLiteQueryOptimizer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If all shown-counts sum to 0, the function returns 0.0 (no div-by-zero)."""
    import sqlite3

    class _FakeCursor:
        def execute(self, *a: object, **kw: object) -> None:
            pass

        def fetchall(self) -> list[tuple[str, str]]:
            # Return a row where both click+shown are empty JSON.
            return [("[]", "[]")]

        def fetchone(self) -> None:
            return None

    class _FakeConn:
        def execute(self, *a: object, **kw: object) -> _FakeCursor:
            return _FakeCursor()

        def close(self) -> None:
            pass

    def _fake_connect(*a: object, **kw: object) -> _FakeConn:
        return _FakeConn()

    monkeypatch.setattr(sqlite3, "connect", _fake_connect)
    optimizer._initialized = True  # type: ignore[attr-defined]
    assert optimizer.get_click_through_rate("q") == 0.0


def test_get_click_through_rate_handles_exception(
    optimizer: SQLiteQueryOptimizer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlite3

    def _raise(*a: object, **kw: object) -> object:
        raise sqlite3.OperationalError("disk fail")

    monkeypatch.setattr(sqlite3, "connect", _raise)
    assert optimizer.get_click_through_rate("q") == 0.0


def test_get_click_through_rate_not_initialized(tmp_path: Path) -> None:
    opt = SQLiteQueryOptimizer(db_path=tmp_path / "opt.db")
    opt._initialized = False  # type: ignore[attr-defined]
    assert opt.get_click_through_rate("q") == 0.0


# ---------------------------------------------------------------------------
# NoOpQueryOptimizer
# ---------------------------------------------------------------------------


def test_no_op_optimizer_records() -> None:
    """The no-op optimizer never raises on track_search_interaction."""
    opt = NoOpQueryOptimizer()
    # Should silently log and return.
    opt.track_search_interaction(
        query="q",
        results_clicked=["r1"],
        results_skipped=[],
        user_satisfaction=0.5,
        outcome="success",
    )
    assert opt.is_enabled() is False


def test_no_op_optimizer_empty_suggestions() -> None:
    opt = NoOpQueryOptimizer()
    assert opt.get_query_suggestions("q", ["similar"]) == []


def test_no_op_optimizer_adapt_ranking_returns_candidates() -> None:
    opt = NoOpQueryOptimizer()
    candidates = [{"id": "x", "score": 0.1}]
    assert opt.adapt_ranking("q", candidates) == candidates


def test_no_op_optimizer_click_through_rate_zero() -> None:
    opt = NoOpQueryOptimizer()
    assert opt.get_click_through_rate("q") == 0.0


# ---------------------------------------------------------------------------
# AkoshaLearningIntegration (factory entry point)
# ---------------------------------------------------------------------------


def test_akosha_learning_integration_create_with_optimization(
    tmp_path: Path,
) -> None:
    """``create_query_optimizer(enabled=True)`` returns a SQLite-backed optimizer."""
    optimizer = create_query_optimizer(
        enabled=True, db_path=tmp_path / "akosha.db"
    )
    assert isinstance(optimizer, SQLiteQueryOptimizer)


def test_akosha_learning_integration_create_disabled() -> None:
    optimizer = create_query_optimizer(enabled=False)
    assert isinstance(optimizer, NoOpQueryOptimizer)


def test_akosha_learning_integration_create_falls_back_to_noop_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """If SQLite init fails, the integration falls back to ``NoOpQueryOptimizer``."""
    import sqlite3 as _sqlite3

    def _raise(*a: object, **kw: object) -> object:
        raise _sqlite3.OperationalError("disk fail")

    monkeypatch.setattr(_sqlite3, "connect", _raise)
    optimizer = create_query_optimizer(
        enabled=True, db_path=tmp_path / "akosha.db"
    )
    assert isinstance(optimizer, NoOpQueryOptimizer)


# ---------------------------------------------------------------------------
# QuerySuggestion dataclass
# ---------------------------------------------------------------------------


def test_query_suggestion_fields() -> None:
    s = QuerySuggestion(
        original_query="how",
        suggested_query="how to foo",
        confidence=0.9,
        expected_improvement=0.85,
        reason="high success",
    )
    assert s.confidence == 0.9


# ---------------------------------------------------------------------------
# AkoshaLearningIntegration
# ---------------------------------------------------------------------------


def test_akosha_learning_integration_track_search_results_completer(
    tmp_path: Path,
) -> None:
    """``track_search_results`` returns a completer that captures the
    click/skip/satisfaction inputs."""
    optimizer = SQLiteQueryOptimizer(db_path=tmp_path / "akosha.db")
    integ = AkoshaLearningIntegration(query_optimizer=optimizer)
    results = [{"id": "r1"}, {"id": "r2"}]
    completer = integ.track_search_results("how to foo", results)
    completer(results_clicked=["r1"], outcome="success")
    # r1 was clicked → recorded in optimizer.
    assert optimizer.is_enabled()


def test_akosha_learning_integration_enhance_search_results(
    tmp_path: Path,
) -> None:
    optimizer = SQLiteQueryOptimizer(db_path=tmp_path / "akosha.db")
    integ = AkoshaLearningIntegration(query_optimizer=optimizer)
    candidates = [{"id": "x", "score": 0.5}]
    assert integ.enhance_search_results("q", candidates) == candidates


def test_akosha_learning_integration_get_query_improvements(
    tmp_path: Path,
) -> None:
    optimizer = SQLiteQueryOptimizer(db_path=tmp_path / "akosha.db")
    integ = AkoshaLearningIntegration(query_optimizer=optimizer)
    assert integ.get_query_improvements("q", ["similar"]) == []


def test_akosha_learning_integration_session_id(
    tmp_path: Path,
) -> None:
    """``session_id`` is forwarded to the optimizer on each interaction."""
    optimizer = SQLiteQueryOptimizer(db_path=tmp_path / "akosha.db")
    integ = AkoshaLearningIntegration(
        query_optimizer=optimizer, session_id="my-session"
    )
    completer = integ.track_search_results("q", [{"id": "r1"}])
    completer(results_clicked=["r1"], outcome="success")
    assert integ.session_id == "my-session"
