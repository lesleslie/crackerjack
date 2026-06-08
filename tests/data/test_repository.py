"""Tests for the in-memory repository layer in ``crackerjack.data.repository``."""

from __future__ import annotations

import pytest

from crackerjack.data.models import (
    DependencyMonitorCacheRecord,
    ProjectHealthRecord,
    QualityBaselineRecord,
)
from crackerjack.data.repository import (
    DependencyMonitorRepository,
    HealthMetricsRepository,
    InMemoryQuery,
    QualityBaselineRepository,
    _InMemoryAdvancedOps,
    _InMemoryModelInterface,
    _InMemorySimpleOps,
)


@pytest.fixture
def fresh_query() -> InMemoryQuery:
    """Return a brand-new query store, isolated from the module-level singleton."""
    return InMemoryQuery()


@pytest.fixture
def quality_repo(fresh_query: InMemoryQuery) -> QualityBaselineRepository:
    repo = QualityBaselineRepository()
    repo.query = fresh_query
    return repo


@pytest.fixture
def health_repo(fresh_query: InMemoryQuery) -> HealthMetricsRepository:
    repo = HealthMetricsRepository()
    repo.query = fresh_query
    return repo


@pytest.fixture
def dep_repo(fresh_query: InMemoryQuery) -> DependencyMonitorRepository:
    repo = DependencyMonitorRepository()
    repo.query = fresh_query
    return repo


class TestInMemoryQuery:
    """Tests for the InMemoryQuery top-level dispatcher."""

    def test_for_model_returns_interface(self, fresh_query: InMemoryQuery) -> None:
        interface = fresh_query.for_model(QualityBaselineRecord)
        assert isinstance(interface, _InMemoryModelInterface)

    def test_for_model_creates_empty_store(self, fresh_query: InMemoryQuery) -> None:
        fresh_query.for_model(QualityBaselineRecord)
        # The store for the model should be created and empty.
        assert fresh_query._stores[QualityBaselineRecord] == []

    def test_for_model_returns_interface_sharing_underlying_store(
        self,
        fresh_query: InMemoryQuery,
    ) -> None:
        # NOTE: ``for_model`` allocates a *new* ``_InMemoryModelInterface``
        # wrapper on every call, but the store list inside the internal
        # ``_stores`` dict is reused. So identity of the interface wrapper
        # is NOT stable, but the underlying store IS shared.
        first = fresh_query.for_model(QualityBaselineRecord)
        second = fresh_query.for_model(QualityBaselineRecord)
        assert first is not second
        # The two wrappers point at the SAME list object via the
        # ``_stores`` dict, so writes through one are visible through
        # the other.
        assert first.simple._store is second.simple._store
        assert first.advanced._simple._store is second.advanced._simple._store

    async def test_for_model_shares_writes_across_wrappers(
        self,
        fresh_query: InMemoryQuery,
    ) -> None:
        # End-to-end: writes through the first wrapper are visible via
        # the second wrapper.
        await fresh_query.for_model(
            QualityBaselineRecord,
        ).simple.create_or_update({"git_hash": "h1"}, "git_hash")
        match = await fresh_query.for_model(
            QualityBaselineRecord,
        ).simple.find(git_hash="h1")
        assert match is not None
        assert match.git_hash == "h1"

    def test_distinct_models_get_independent_stores(
        self,
        fresh_query: InMemoryQuery,
    ) -> None:
        quality_store = fresh_query.for_model(QualityBaselineRecord).simple
        health_store = fresh_query.for_model(ProjectHealthRecord).simple
        assert quality_store is not health_store

    def test_interface_exposes_simple_and_advanced(
        self,
        fresh_query: InMemoryQuery,
    ) -> None:
        interface = fresh_query.for_model(QualityBaselineRecord)
        assert isinstance(interface.simple, _InMemorySimpleOps)
        assert isinstance(interface.advanced, _InMemoryAdvancedOps)


class TestInMemorySimpleOps:
    """Direct tests for the simple ops helper class."""

    @pytest.fixture
    def store(self) -> list[QualityBaselineRecord]:
        return []

    @pytest.fixture
    def ops(self, store: list[QualityBaselineRecord]) -> _InMemorySimpleOps:
        return _InMemorySimpleOps(QualityBaselineRecord, store)

    async def test_create_or_update_creates_new(
        self,
        ops: _InMemorySimpleOps,
        store: list[QualityBaselineRecord],
    ) -> None:
        record = await ops.create_or_update(
            {"git_hash": "abc", "quality_score": 90},
            "git_hash",
        )
        assert isinstance(record, QualityBaselineRecord)
        assert record.git_hash == "abc"
        assert record.quality_score == 90
        assert store == [record]

    async def test_create_or_update_returns_existing_on_duplicate(
        self,
        ops: _InMemorySimpleOps,
        store: list[QualityBaselineRecord],
    ) -> None:
        first = await ops.create_or_update({"git_hash": "abc"}, "git_hash")
        second = await ops.create_or_update(
            {"git_hash": "abc", "quality_score": 99},
            "git_hash",
        )
        # The same instance should be updated, not duplicated.
        assert first is second
        assert len(store) == 1
        assert second.quality_score == 99

    async def test_create_or_update_calls_update_from_dict_when_available(
        self,
        ops: _InMemorySimpleOps,
    ) -> None:
        record = await ops.create_or_update({"git_hash": "abc"}, "git_hash")
        # QualityBaselineRecord.update_from_dict ignores unknown keys
        # but applies known ones, including extra_metadata.
        await ops.create_or_update(
            {
                "git_hash": "abc",
                "quality_score": 12,
                "extra_metadata": {"k": "v"},
            },
            "git_hash",
        )
        assert record.quality_score == 12
        assert record.extra_metadata == {"k": "v"}

    async def test_create_or_update_falls_back_to_setattr_for_model_without_dict_method(
        self,
    ) -> None:
        """Models without ``update_from_dict`` get a plain setattr-based update."""

        class _Bare:
            def __init__(self, name: str, value: int = 0) -> None:
                self.name = name
                self.value = value

        store: list[_Bare] = []
        ops = _InMemorySimpleOps(_Bare, store)
        first = await ops.create_or_update({"name": "x", "value": 1}, "name")
        second = await ops.create_or_update({"name": "x", "value": 2}, "name")
        assert first is second
        assert second.value == 2

    async def test_find_returns_match(self, ops: _InMemorySimpleOps) -> None:
        await ops.create_or_update({"git_hash": "abc"}, "git_hash")
        await ops.create_or_update({"git_hash": "def"}, "git_hash")
        match = await ops.find(git_hash="def")
        assert match is not None
        assert match.git_hash == "def"

    async def test_find_returns_none_when_no_match(
        self,
        ops: _InMemorySimpleOps,
    ) -> None:
        await ops.create_or_update({"git_hash": "abc"}, "git_hash")
        assert await ops.find(git_hash="zzz") is None

    async def test_find_uses_multiple_filters(self, ops: _InMemorySimpleOps) -> None:
        await ops.create_or_update({"git_hash": "abc", "quality_score": 5}, "git_hash")
        await ops.create_or_update({"git_hash": "def", "quality_score": 5}, "git_hash")
        match = await ops.find(git_hash="abc", quality_score=5)
        assert match is not None
        assert match.git_hash == "abc"
        # Wrong secondary filter should miss.
        assert await ops.find(git_hash="abc", quality_score=999) is None

    async def test_delete_returns_true_when_match(
        self,
        ops: _InMemorySimpleOps,
        store: list[QualityBaselineRecord],
    ) -> None:
        await ops.create_or_update({"git_hash": "abc"}, "git_hash")
        result = await ops.delete(git_hash="abc")
        assert result is True
        assert store == []

    async def test_delete_returns_false_when_no_match(
        self,
        ops: _InMemorySimpleOps,
    ) -> None:
        result = await ops.delete(git_hash="missing")
        assert result is False

    async def test_delete_removes_only_matching(
        self,
        ops: _InMemorySimpleOps,
        store: list[QualityBaselineRecord],
    ) -> None:
        await ops.create_or_update({"git_hash": "abc"}, "git_hash")
        await ops.create_or_update({"git_hash": "def"}, "git_hash")
        result = await ops.delete(git_hash="abc")
        assert result is True
        assert len(store) == 1
        assert store[0].git_hash == "def"

    async def test_all_returns_copy_of_store(
        self,
        ops: _InMemorySimpleOps,
        store: list[QualityBaselineRecord],
    ) -> None:
        await ops.create_or_update({"git_hash": "abc"}, "git_hash")
        snapshot = await ops.all()
        assert snapshot == store
        # Mutating the snapshot must NOT affect the underlying store.
        snapshot.clear()
        assert len(store) == 1

    async def test_all_on_empty_store(self, ops: _InMemorySimpleOps) -> None:
        assert await ops.all() == []


class TestInMemoryAdvancedOps:
    """Direct tests for the advanced query/ordering/limiting helper."""

    @pytest.fixture
    def simple(self) -> _InMemorySimpleOps:
        return _InMemorySimpleOps(QualityBaselineRecord, [])

    @pytest.fixture
    def advanced(self, simple: _InMemorySimpleOps) -> _InMemoryAdvancedOps:
        return _InMemoryAdvancedOps(simple)

    async def test_order_by_desc_returns_self(
        self,
        advanced: _InMemoryAdvancedOps,
    ) -> None:
        assert advanced.order_by_desc("quality_score") is advanced

    async def test_limit_returns_self(self, advanced: _InMemoryAdvancedOps) -> None:
        assert advanced.limit(5) is advanced

    async def test_all_sorts_descending_by_field(
        self,
        advanced: _InMemoryAdvancedOps,
        simple: _InMemorySimpleOps,
    ) -> None:
        for score in (10, 30, 20):
            await simple.create_or_update(
                {"git_hash": f"h{score}", "quality_score": score},
                "git_hash",
            )
        result = await advanced.order_by_desc("quality_score").all()
        scores = [r.quality_score for r in result]
        assert scores == [30, 20, 10]

    async def test_all_respects_limit(self, advanced: _InMemoryAdvancedOps) -> None:
        simple = advanced._simple
        for i in range(5):
            await simple.create_or_update(
                {"git_hash": f"g{i}", "quality_score": i},
                "git_hash",
            )
        result = await advanced.order_by_desc("quality_score").limit(3).all()
        assert len(result) == 3
        assert [r.quality_score for r in result] == [4, 3, 2]

    async def test_all_without_order_preserves_insertion(
        self,
        advanced: _InMemoryAdvancedOps,
    ) -> None:
        simple = advanced._simple
        for git in ("a", "b", "c"):
            await simple.create_or_update({"git_hash": git}, "git_hash")
        result = await advanced.all()
        assert [r.git_hash for r in result] == ["a", "b", "c"]

    async def test_all_limit_only_no_order(
        self,
        advanced: _InMemoryAdvancedOps,
    ) -> None:
        simple = advanced._simple
        for i in range(4):
            await simple.create_or_update(
                {"git_hash": f"x{i}", "quality_score": i},
                "git_hash",
            )
        result = await advanced.limit(2).all()
        assert len(result) == 2

    async def test_chained_calls_compose(self, advanced: _InMemoryAdvancedOps) -> None:
        simple = advanced._simple
        for score in (1, 5, 3, 4, 2):
            await simple.create_or_update(
                {"git_hash": f"c{score}", "quality_score": score},
                "git_hash",
            )
        result = (
            await advanced.order_by_desc("quality_score").limit(2).all()
        )
        assert [r.quality_score for r in result] == [5, 4]


class TestQualityBaselineRepository:
    """Tests for the ``QualityBaselineRepository`` wrapper."""

    async def test_upsert_creates_record(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        record = await quality_repo.upsert(
            {"git_hash": "h1", "quality_score": 75},
        )
        assert isinstance(record, QualityBaselineRecord)
        assert record.git_hash == "h1"
        assert record.quality_score == 75

    async def test_upsert_updates_existing(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        first = await quality_repo.upsert({"git_hash": "h1", "quality_score": 1})
        second = await quality_repo.upsert(
            {"git_hash": "h1", "quality_score": 99},
        )
        assert first is second
        assert second.quality_score == 99

    async def test_upsert_uses_update_from_dict_semantics(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        first = await quality_repo.upsert({"git_hash": "h1"})
        # ``update_from_dict`` ignores unknown keys but applies known ones.
        await quality_repo.upsert(
            {
                "git_hash": "h1",
                "coverage_percent": 12.5,
                "extra_metadata": {"k": "v"},
                "bogus_field": "ignored",
            },
        )
        assert first.coverage_percent == 12.5
        assert first.extra_metadata == {"k": "v"}
        assert not hasattr(first, "bogus_field")

    async def test_get_by_git_hash_returns_match(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        await quality_repo.upsert({"git_hash": "abc", "quality_score": 88})
        match = await quality_repo.get_by_git_hash("abc")
        assert match is not None
        assert match.git_hash == "abc"
        assert match.quality_score == 88

    async def test_get_by_git_hash_returns_none(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        assert await quality_repo.get_by_git_hash("absent") is None

    async def test_list_recent_returns_all_when_under_limit(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        for i in range(3):
            await quality_repo.upsert(
                {"git_hash": f"h{i}", "quality_score": i},
            )
        result = await quality_repo.list_recent(limit=10)
        assert len(result) == 3

    async def test_list_recent_sorts_by_recorded_at_desc(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        # Insert three records — recorded_at is auto-generated per record
        # so a descending sort must reverse the insertion order.
        for i in range(3):
            await quality_repo.upsert(
                {"git_hash": f"h{i}", "quality_score": i},
            )
        result = await quality_repo.list_recent(limit=10)
        # Most recent (last inserted) should come first.
        assert [r.git_hash for r in result] == ["h2", "h1", "h0"]

    async def test_list_recent_respects_limit(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        for i in range(5):
            await quality_repo.upsert(
                {"git_hash": f"h{i}", "quality_score": i},
            )
        result = await quality_repo.list_recent(limit=2)
        assert len(result) == 2

    async def test_list_recent_default_limit(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        for i in range(15):
            await quality_repo.upsert(
                {"git_hash": f"h{i}", "quality_score": i},
            )
        result = await quality_repo.list_recent()
        # Default limit is 10.
        assert len(result) == 10

    async def test_delete_for_git_hash_returns_true(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        await quality_repo.upsert({"git_hash": "abc"})
        assert await quality_repo.delete_for_git_hash("abc") is True
        # Now the record is gone.
        assert await quality_repo.get_by_git_hash("abc") is None

    async def test_delete_for_git_hash_returns_false_when_missing(
        self,
        quality_repo: QualityBaselineRepository,
    ) -> None:
        assert await quality_repo.delete_for_git_hash("nope") is False


class TestHealthMetricsRepository:
    """Tests for the ``HealthMetricsRepository`` wrapper."""

    async def test_upsert_sets_project_name(
        self,
        health_repo: HealthMetricsRepository,
    ) -> None:
        record = await health_repo.upsert(
            "myproj",
            {"health_score": 80, "issue_count": 4},
        )
        assert isinstance(record, ProjectHealthRecord)
        assert record.project_name == "myproj"
        assert record.health_score == 80
        assert record.issue_count == 4

    async def test_upsert_explicit_name_overridden_by_data(
        self,
        health_repo: HealthMetricsRepository,
    ) -> None:
        # Documented bug: ``HealthMetricsRepository.upsert`` merges
        # ``data = {"project_name": project_name} | data``. In a Python
        # ``dict | dict`` union, the RIGHT operand wins on conflicts, so
        # the explicit ``project_name`` argument is silently overridden
        # by ``data["project_name"]``. This test pins the current
        # (buggy) behavior; callers should not pass ``project_name`` in
        # ``data``.
        record = await health_repo.upsert(
            "explicit",
            {"project_name": "ignored", "health_score": 10},
        )
        assert record.project_name == "ignored"

    async def test_upsert_updates_existing(
        self,
        health_repo: HealthMetricsRepository,
    ) -> None:
        first = await health_repo.upsert("myproj", {"health_score": 1})
        second = await health_repo.upsert("myproj", {"health_score": 99})
        assert first is second
        assert second.health_score == 99

    async def test_upsert_pydantic_model_uses_setattr_fallback(
        self,
        health_repo: HealthMetricsRepository,
    ) -> None:
        # ProjectHealthRecord has no ``update_from_dict`` so the
        # ``_update_entity_fields`` branch is exercised.
        record = await health_repo.upsert("p", {"health_score": 1})
        await health_repo.upsert(
            "p",
            {"health_score": 5, "warning_count": 7},
        )
        assert record.health_score == 5
        assert record.warning_count == 7

    async def test_get_returns_match(
        self,
        health_repo: HealthMetricsRepository,
    ) -> None:
        await health_repo.upsert("myproj", {"health_score": 42})
        record = await health_repo.get("myproj")
        assert record is not None
        assert record.project_name == "myproj"
        assert record.health_score == 42

    async def test_get_returns_none(self, health_repo: HealthMetricsRepository) -> None:
        assert await health_repo.get("missing") is None


class TestDependencyMonitorRepository:
    """Tests for the ``DependencyMonitorRepository`` wrapper."""

    async def test_upsert_creates_record(
        self,
        dep_repo: DependencyMonitorRepository,
    ) -> None:
        record = await dep_repo.upsert(
            "/path/to/repo",
            {"project_root": "/path/to/repo", "cache_data": {"k": 1}},
        )
        assert isinstance(record, DependencyMonitorCacheRecord)
        assert record.project_root == "/path/to/repo"
        assert record.cache_data == {"k": 1}

    async def test_upsert_updates_existing(
        self,
        dep_repo: DependencyMonitorRepository,
    ) -> None:
        first = await dep_repo.upsert(
            "/path",
            {"project_root": "/path", "cache_data": {"v": 1}},
        )
        second = await dep_repo.upsert(
            "/path",
            {"project_root": "/path", "cache_data": {"v": 2}},
        )
        assert first is second
        assert second.cache_data == {"v": 2}

    async def test_get_returns_match(
        self,
        dep_repo: DependencyMonitorRepository,
    ) -> None:
        await dep_repo.upsert("/path", {"project_root": "/path", "cache_data": {}})
        record = await dep_repo.get("/path")
        assert record is not None
        assert record.project_root == "/path"

    async def test_get_returns_none(self, dep_repo: DependencyMonitorRepository) -> None:
        assert await dep_repo.get("/nope") is None

    async def test_multiple_projects_are_isolated(
        self,
        dep_repo: DependencyMonitorRepository,
    ) -> None:
        a = await dep_repo.upsert("/a", {"project_root": "/a", "cache_data": {"a": 1}})
        b = await dep_repo.upsert("/b", {"project_root": "/b", "cache_data": {"b": 1}})
        assert a is not b
        assert (await dep_repo.get("/a")).cache_data == {"a": 1}
        assert (await dep_repo.get("/b")).cache_data == {"b": 1}


class TestRepositoryIsolation:
    """The three repositories share ``_QUERY`` — make sure they don't bleed."""

    def test_repositories_use_shared_module_query(self) -> None:
        # Each repo exposes the *module-level* _QUERY by default.
        from crackerjack.data.repository import _QUERY

        assert QualityBaselineRepository().query is _QUERY
        assert HealthMetricsRepository().query is _QUERY
        assert DependencyMonitorRepository().query is _QUERY

    async def test_repositories_share_module_store(
        self,
        fresh_query: InMemoryQuery,
    ) -> None:
        # When a caller injects a custom ``InMemoryQuery``, that instance
        # is shared across all repositories wired to it. The
        # default module-level ``_QUERY`` is a separate, global singleton.
        from crackerjack.data.repository import _QUERY  # noqa: PLC0415

        repo_a = QualityBaselineRepository()
        repo_a.query = fresh_query
        repo_b = HealthMetricsRepository()
        repo_b.query = fresh_query

        await repo_a.upsert({"git_hash": "shared", "quality_score": 7})
        match = await repo_b.get("shared")
        # The two repos have different models and different key fields,
        # so this should NOT collide — but the *store* is per-model, not
        # per-repo, so a "shared" hash under ``QualityBaselineRecord`` is
        # not visible as a ``ProjectHealthRecord`` entry. We assert
        # exactly that.
        assert match is None

        # And the shared query now has exactly one entry for
        # QualityBaselineRecord and zero for ProjectHealthRecord.
        baseline_count = len(fresh_query._stores[QualityBaselineRecord])
        assert baseline_count == 1
        # The model-level _QUERY singleton is unaffected.
        assert _QUERY is not fresh_query
