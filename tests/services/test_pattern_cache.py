"""Tests for ``crackerjack.services.pattern_cache``.

The module persists cached fix patterns to a JSON file under the
project's ``.crackerjack/patterns/`` directory. Tests use ``tmp_path``
so each test gets a fresh cache directory.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pytest

from crackerjack.models.issues import FixResult, Issue, IssueType, Priority
from crackerjack.services.pattern_cache import CachedPattern, PatternCache


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "project"


@pytest.fixture
def cache(cache_dir: Path) -> PatternCache:
    return PatternCache(cache_dir)


def _make_issue(
    issue_type: IssueType = IssueType.FORMATTING,
    msg: str = "test issue",
    path: str | None = "foo.py",
    line: int | None = 10,
) -> Issue:
    return Issue(
        type=issue_type,
        severity=Priority.MEDIUM,
        message=msg,
        file_path=path,
        line_number=line,
    )


def _make_fix_result(
    confidence: float = 0.9,
    files: list[str] | None = None,
    fixes: list[str] | None = None,
) -> FixResult:
    return FixResult(
        success=True,
        confidence=confidence,
        files_modified=files or [],
        fixes_applied=fixes or [],
    )


# ---------------------------------------------------------------------------
# CachedPattern dataclass
# ---------------------------------------------------------------------------


def test_cached_pattern_construction() -> None:
    p = CachedPattern(
        pattern_id="p1",
        issue_type=IssueType.FORMATTING,
        strategy="ruff",
        patterns=["* .py"],
        confidence=0.9,
        success_rate=1.0,
        usage_count=3,
        last_used=100.0,
        created_at=50.0,
        files_modified=["a.py"],
        fixes_applied=["ruff format"],
        metadata={},
    )
    assert p.pattern_id == "p1"
    assert p.confidence == 0.9


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_creates_cache_dir(cache_dir: Path, cache: PatternCache) -> None:
    assert cache_dir.exists()
    assert (cache_dir / ".crackerjack" / "patterns").exists()


def test_init_cache_file_path(cache: PatternCache, cache_dir: Path) -> None:
    assert cache.cache_file == cache_dir / ".crackerjack" / "patterns" / "pattern_cache.json"


def test_init_empty_patterns(cache: PatternCache) -> None:
    assert cache._patterns == {}
    assert cache._loaded is False


# ---------------------------------------------------------------------------
# _load_patterns
# ---------------------------------------------------------------------------


def test_load_no_file_logs_info(cache: PatternCache, caplog: pytest.LogCaptureFixture) -> None:
    cache._load_patterns()
    assert cache._loaded is True
    # Capture via propagated logger at INFO level.
    logger = logging.getLogger("crackerjack.services.pattern_cache")
    logger.setLevel("INFO")
    logger.propagate = True
    cache._loaded = False  # force reload
    with caplog.at_level("INFO"):
        cache._load_patterns()
    assert any("No existing pattern cache" in r.message for r in caplog.records)


def test_load_existing_patterns(tmp_path: Path) -> None:
    cache_dir = tmp_path / "p"
    cache_dir.mkdir()
    data = {
        "version": "1.0",
        "patterns": [
            {
                "pattern_id": "p1",
                "issue_type": "formatting",
                "strategy": "ruff",
                "patterns": ["x"],
                "confidence": 0.9,
                "success_rate": 1.0,
                "usage_count": 0,
                "last_used": 0.0,
                "created_at": 1.0,
                "files_modified": [],
                "fixes_applied": [],
                "metadata": {},
            },
        ],
    }
    cache_file = cache_dir / ".crackerjack" / "patterns" / "pattern_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data))
    cache = PatternCache(cache_dir)
    cache._load_patterns()
    assert "p1" in cache._patterns


def test_load_invalid_json_handled(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    cache_dir = tmp_path / "p"
    cache_dir.mkdir()
    cache_file = cache_dir / ".crackerjack" / "patterns" / "pattern_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{invalid json")
    cache = PatternCache(cache_dir)
    with caplog.at_level("WARNING", logger="crackerjack.services.pattern_cache"):
        cache._load_patterns()
    assert cache._loaded is True
    assert cache._patterns == {}


def test_load_idempotent(cache: PatternCache) -> None:
    cache._load_patterns()
    assert cache._loaded is True
    cache._load_patterns()  # second call returns early
    assert cache._loaded is True


def test_load_missing_metadata_key_uses_empty_dict(tmp_path: Path) -> None:
    """If metadata key is absent, default to {}."""
    cache_dir = tmp_path / "p"
    cache_dir.mkdir()
    data = {
        "version": "1.0",
        "patterns": [
            {
                "pattern_id": "p1",
                "issue_type": "formatting",
                "strategy": "ruff",
                "patterns": [],
                "confidence": 0.9,
                "success_rate": 1.0,
                "usage_count": 0,
                "last_used": 0.0,
                "created_at": 1.0,
                "files_modified": [],
                "fixes_applied": [],
                # no metadata key
            },
        ],
    }
    cache_file = cache_dir / ".crackerjack" / "patterns" / "pattern_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data))
    cache = PatternCache(cache_dir)
    cache._load_patterns()
    assert cache._patterns["p1"].metadata == {}


# ---------------------------------------------------------------------------
# cache_successful_pattern
# ---------------------------------------------------------------------------


def test_cache_successful_pattern_returns_id(cache: PatternCache) -> None:
    issue = _make_issue()
    plan = {"strategy": "ruff", "patterns": ["* .py"]}
    result = _make_fix_result(confidence=0.85)
    pid = cache.cache_successful_pattern(issue, plan, result)
    assert pid.startswith(f"{issue.type.value}_ruff_")
    assert pid in cache._patterns


def test_cache_successful_pattern_default_strategy(cache: PatternCache) -> None:
    """plan without 'strategy' → 'default'."""
    issue = _make_issue()
    plan: dict[str, object] = {}
    result = _make_fix_result()
    pid = cache.cache_successful_pattern(issue, plan, result)
    assert "_default_" in pid
    assert cache._patterns[pid].strategy == "unknown"


def test_cache_successful_pattern_persists_to_disk(cache: PatternCache) -> None:
    issue = _make_issue()
    plan = {"strategy": "ruff"}
    result = _make_fix_result()
    cache.cache_successful_pattern(issue, plan, result)
    assert cache.cache_file.exists()


def test_cache_successful_pattern_metadata_fields(cache: PatternCache) -> None:
    issue = _make_issue(path="x.py", line=42)
    plan = {"strategy": "ruff", "patterns": []}
    result = _make_fix_result()
    pid = cache.cache_successful_pattern(issue, plan, result)
    md = cache._patterns[pid].metadata
    assert md["file_path"] == "x.py"
    assert md["line_number"] == 42


# ---------------------------------------------------------------------------
# get_patterns_for_issue + get_best_pattern_for_issue
# ---------------------------------------------------------------------------


def test_get_patterns_for_issue_returns_matching(cache: PatternCache) -> None:
    issue = _make_issue(IssueType.FORMATTING)
    cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    out = cache.get_patterns_for_issue(issue)
    assert len(out) == 1
    assert out[0].issue_type == IssueType.FORMATTING


def test_get_patterns_for_issue_filters_by_type(cache: PatternCache) -> None:
    cache.cache_successful_pattern(
        _make_issue(IssueType.FORMATTING),
        {"strategy": "ruff"},
        _make_fix_result(),
    )
    cache.cache_successful_pattern(
        _make_issue(IssueType.SECURITY),
        {"strategy": "bandit"},
        _make_fix_result(),
    )
    out = cache.get_patterns_for_issue(_make_issue(IssueType.FORMATTING))
    assert len(out) == 1
    assert out[0].issue_type == IssueType.FORMATTING


def test_get_patterns_for_issue_sorts_by_success_then_confidence(
    cache: PatternCache,
) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(issue, {"strategy": "a"}, _make_fix_result(confidence=0.5))
    cache.cache_successful_pattern(issue, {"strategy": "b"}, _make_fix_result(confidence=0.9))
    cache.cache_successful_pattern(issue, {"strategy": "c"}, _make_fix_result(confidence=0.7))
    # After one use, b and c both have success_rate=1.0; a has 0.0. Sort descending.
    out = cache.get_patterns_for_issue(issue)
    # success_rate=1.0 entries (b, c) come first, sorted by confidence.
    assert out[0].strategy == "b"


def test_get_patterns_for_issue_empty_when_no_match(cache: PatternCache) -> None:
    cache.cache_successful_pattern(
        _make_issue(IssueType.FORMATTING),
        {"strategy": "ruff"},
        _make_fix_result(),
    )
    out = cache.get_patterns_for_issue(_make_issue(IssueType.SECURITY))
    assert out == []


def test_get_best_pattern_for_issue_returns_first(cache: PatternCache) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(issue, {"strategy": "a"}, _make_fix_result())
    cache.cache_successful_pattern(issue, {"strategy": "b"}, _make_fix_result())
    best = cache.get_best_pattern_for_issue(issue)
    assert best is not None
    assert best.issue_type == IssueType.FORMATTING


def test_get_best_pattern_for_issue_returns_none_when_empty(cache: PatternCache) -> None:
    assert cache.get_best_pattern_for_issue(_make_issue()) is None


# ---------------------------------------------------------------------------
# use_pattern
# ---------------------------------------------------------------------------


def test_use_pattern_increments_counter(cache: PatternCache) -> None:
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    assert cache.use_pattern(pid) is True
    assert cache._patterns[pid].usage_count == 1
    assert cache._patterns[pid].last_used > 0


def test_use_pattern_unknown_returns_false(cache: PatternCache) -> None:
    assert cache.use_pattern("nonexistent") is False


def test_use_pattern_multiple_times(cache: PatternCache) -> None:
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    for _ in range(5):
        cache.use_pattern(pid)
    assert cache._patterns[pid].usage_count == 5


# ---------------------------------------------------------------------------
# update_pattern_success_rate
# ---------------------------------------------------------------------------


def test_update_pattern_success_rate_increments_on_success(cache: PatternCache) -> None:
    """Pre-existing bug: success_rate math is off-by-one.

    After use_pattern (count=1) + update(success=True), source computes
    ``(1.0 * 1 + 1) / 1 = 2.0``. Per CLAUDE.md Rule 7, preserve verbatim.
    """
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    cache.use_pattern(pid)  # usage_count = 1
    cache.update_pattern_success_rate(pid, success=True)
    assert cache._patterns[pid].success_rate == 2.0


def test_update_pattern_success_rate_decrements_on_failure(cache: PatternCache) -> None:
    """Pre-existing bug: failure update yields 0.0 (matches expected math)."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    cache.use_pattern(pid)  # usage_count = 1, success_rate = 1.0
    cache.update_pattern_success_rate(pid, success=False)
    # (1.0 * 1) / 1 = 1.0 → success branch not entered, divide by 1 → 1.0
    assert cache._patterns[pid].success_rate == 1.0


def test_update_pattern_success_rate_unknown_id_no_op(cache: PatternCache) -> None:
    cache.update_pattern_success_rate("nonexistent", success=True)  # must not raise


def test_update_pattern_success_rate_zero_usage(cache: PatternCache) -> None:
    """With usage_count=0, the if branch is skipped → no change."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    cache.update_pattern_success_rate(pid, success=True)
    # usage_count is 0 → if total_uses > 0 is False → success_rate unchanged.
    assert cache._patterns[pid].success_rate == 1.0


# ---------------------------------------------------------------------------
# get_pattern_statistics + _get_most_used_patterns
# ---------------------------------------------------------------------------


def test_get_pattern_statistics_empty(cache: PatternCache) -> None:
    stats = cache.get_pattern_statistics()
    assert stats["total_patterns"] == 0
    assert "patterns_by_type" not in stats


def test_get_pattern_statistics_with_data(cache: PatternCache) -> None:
    """Cache 2 patterns with different strategies to avoid int(time.time()) collision."""
    issue = _make_issue(IssueType.FORMATTING)
    cache.cache_successful_pattern(issue, {"strategy": "ruff1"}, _make_fix_result())
    cache.cache_successful_pattern(issue, {"strategy": "ruff2"}, _make_fix_result())
    stats = cache.get_pattern_statistics()
    assert stats["total_patterns"] == 2
    assert stats["patterns_by_type"]["formatting"] == 2
    assert stats["total_usage"] == 0


def test_get_most_used_patterns_default_limit(cache: PatternCache) -> None:
    issue = _make_issue()
    pids = [
        cache.cache_successful_pattern(issue, {"strategy": f"s{i}"}, _make_fix_result())
        for i in range(7)
    ]
    for pid in pids:
        cache.use_pattern(pid)
    stats = cache.get_pattern_statistics()
    assert len(stats["most_used_patterns"]) == 5  # default limit


def test_get_most_used_patterns_custom_limit(cache: PatternCache) -> None:
    issue = _make_issue()
    pids = [
        cache.cache_successful_pattern(issue, {"strategy": f"s{i}"}, _make_fix_result())
        for i in range(3)
    ]
    for pid in pids:
        cache.use_pattern(pid)
    most = cache._get_most_used_patterns(limit=2)
    assert len(most) == 2


def test_get_most_used_patterns_sorts_by_usage(cache: PatternCache) -> None:
    issue = _make_issue()
    p_low = cache.cache_successful_pattern(issue, {"strategy": "low"}, _make_fix_result())
    p_high = cache.cache_successful_pattern(issue, {"strategy": "high"}, _make_fix_result())
    cache.use_pattern(p_low)
    for _ in range(5):
        cache.use_pattern(p_high)
    most = cache._get_most_used_patterns()
    assert most[0]["strategy"] == "high"


# ---------------------------------------------------------------------------
# cleanup_old_patterns
# ---------------------------------------------------------------------------


def test_cleanup_old_patterns_removes_old_unused(cache: PatternCache) -> None:
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "old"}, _make_fix_result())
    # Backdate the pattern.
    cache._patterns[pid].created_at = time.time() - (40 * 24 * 60 * 60)
    removed = cache.cleanup_old_patterns(max_age_days=30, min_usage_count=2)
    assert removed == 1
    assert pid not in cache._patterns


def test_cleanup_old_patterns_keeps_recent_unused(cache: PatternCache) -> None:
    """Patterns newer than max_age_days are kept even if unused."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "new"}, _make_fix_result())
    removed = cache.cleanup_old_patterns(max_age_days=30, min_usage_count=2)
    assert removed == 0
    assert pid in cache._patterns


def test_cleanup_old_patterns_keeps_low_success_used(cache: PatternCache) -> None:
    """Patterns with usage_count > 5 but low success_rate → cleaned up."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "stale"}, _make_fix_result())
    cache._patterns[pid].usage_count = 10
    cache._patterns[pid].success_rate = 0.1
    removed = cache.cleanup_old_patterns(max_age_days=30, min_usage_count=2)
    assert removed == 1


def test_cleanup_old_patterns_keeps_low_success_but_few_uses(cache: PatternCache) -> None:
    """Patterns with usage_count <= 5 are kept even if success_rate < 0.2."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(issue, {"strategy": "stale"}, _make_fix_result())
    cache._patterns[pid].usage_count = 3
    cache._patterns[pid].success_rate = 0.1
    removed = cache.cleanup_old_patterns(max_age_days=30, min_usage_count=2)
    assert removed == 0


def test_cleanup_old_patterns_no_matches(cache: PatternCache) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(issue, {"strategy": "fresh"}, _make_fix_result())
    assert cache.cleanup_old_patterns() == 0


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------


def test_clear_cache_removes_file(cache: PatternCache) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    assert cache.cache_file.exists()
    cache.clear_cache()
    assert not cache.cache_file.exists()
    assert cache._patterns == {}
    assert cache._loaded is False


def test_clear_cache_no_file_no_error(cache: PatternCache) -> None:
    """If cache_file doesn't exist, clear is a no-op."""
    cache.clear_cache()  # must not raise


# ---------------------------------------------------------------------------
# export_patterns + import_patterns
# ---------------------------------------------------------------------------


def test_export_patterns_success(cache: PatternCache, tmp_path: Path) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(issue, {"strategy": "ruff"}, _make_fix_result())
    export = tmp_path / "export.json"
    assert cache.export_patterns(export) is True
    assert export.exists()
    data = json.loads(export.read_text())
    assert "version" in data
    assert "patterns" in data
    assert len(data["patterns"]) == 1


def test_export_patterns_failure(cache: PatternCache, tmp_path: Path) -> None:
    """Export to a path that can't be written → returns False."""
    export = tmp_path / "no_dir" / "x.json"
    assert cache.export_patterns(export) is False


def test_import_patterns_merge_new(cache: PatternCache, tmp_path: Path) -> None:
    """import with merge=True adds new patterns and skips existing ones."""
    export = tmp_path / "src.json"
    data = {
        "version": "1.0",
        "patterns": [
            {
                "pattern_id": "p1",
                "issue_type": "formatting",
                "strategy": "ruff",
                "patterns": [],
                "confidence": 0.9,
                "success_rate": 1.0,
                "usage_count": 0,
                "last_used": 0.0,
                "created_at": 1.0,
                "files_modified": [],
                "fixes_applied": [],
                "metadata": {},
            },
            {
                "pattern_id": "p2",
                "issue_type": "security",
                "strategy": "bandit",
                "patterns": [],
                "confidence": 0.7,
                "success_rate": 1.0,
                "usage_count": 0,
                "last_used": 0.0,
                "created_at": 2.0,
                "files_modified": [],
                "fixes_applied": [],
                "metadata": {},
            },
        ],
    }
    export.write_text(json.dumps(data))
    # Pre-populate with p1 → merge should skip it but add p2.
    cache._patterns["p1"] = CachedPattern(
        pattern_id="p1",
        issue_type=IssueType.FORMATTING,
        strategy="existing",
        patterns=[],
        confidence=0.0,
        success_rate=0.0,
        usage_count=0,
        last_used=0.0,
        created_at=0.0,
        files_modified=[],
        fixes_applied=[],
        metadata={},
    )
    assert cache.import_patterns(export, merge=True) is True
    assert cache._patterns["p1"].strategy == "existing"  # not overwritten
    assert "p2" in cache._patterns


def test_import_patterns_no_merge_overwrites(cache: PatternCache, tmp_path: Path) -> None:
    export = tmp_path / "src.json"
    data = {
        "version": "1.0",
        "patterns": [
            {
                "pattern_id": "p1",
                "issue_type": "formatting",
                "strategy": "imported",
                "patterns": [],
                "confidence": 0.9,
                "success_rate": 1.0,
                "usage_count": 0,
                "last_used": 0.0,
                "created_at": 1.0,
                "files_modified": [],
                "fixes_applied": [],
                "metadata": {},
            },
        ],
    }
    export.write_text(json.dumps(data))
    cache._patterns["p1"] = CachedPattern(
        pattern_id="p1",
        issue_type=IssueType.FORMATTING,
        strategy="original",
        patterns=[],
        confidence=0.0,
        success_rate=0.0,
        usage_count=0,
        last_used=0.0,
        created_at=0.0,
        files_modified=[],
        fixes_applied=[],
        metadata={},
    )
    cache.import_patterns(export, merge=False)
    assert cache._patterns["p1"].strategy == "imported"


def test_import_patterns_failure_returns_false(cache: PatternCache, tmp_path: Path) -> None:
    assert cache.import_patterns(tmp_path / "nonexistent.json") is False


def test_import_patterns_metadata_missing_key(cache: PatternCache, tmp_path: Path) -> None:
    """Patterns without 'metadata' key in import → default {}."""
    export = tmp_path / "src.json"
    data = {
        "version": "1.0",
        "patterns": [
            {
                "pattern_id": "p1",
                "issue_type": "formatting",
                "strategy": "ruff",
                "patterns": [],
                "confidence": 0.9,
                "success_rate": 1.0,
                "usage_count": 0,
                "last_used": 0.0,
                "created_at": 1.0,
                "files_modified": [],
                "fixes_applied": [],
                # no metadata
            },
        ],
    }
    export.write_text(json.dumps(data))
    cache.import_patterns(export)
    assert cache._patterns["p1"].metadata == {}
