"""Tests for ``crackerjack.services.quality.pattern_cache``.

Covers the ``CachedPattern`` dataclass plus the ``PatternCache``'s
load/save/CRUD paths: ``cache_successful_pattern``, ``get_patterns_for_issue``,
``get_best_pattern_for_issue``, ``use_pattern``, ``update_pattern_success_rate``,
``get_pattern_statistics``, ``cleanup_old_patterns``, ``clear_cache``,
``export_patterns``, and ``import_patterns``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from crackerjack.models.issues import FixResult, Issue, IssueType, Priority
from crackerjack.services.quality.pattern_cache import (
    CachedPattern,
    PatternCache,
)


def _make_issue(
    message: str = "Test failed",
    issue_type: IssueType = IssueType.FORMATTING,
) -> Issue:
    return Issue(
        type=issue_type,
        severity=Priority.HIGH,
        message=message,
        file_path="/tmp/x.py",
        line_number=10,
    )


def _make_fix_result(
    *,
    success: bool = True,
    confidence: float = 0.9,
    files: list[str] | None = None,
    fixes: list[str] | None = None,
) -> FixResult:
    return FixResult(
        success=success,
        confidence=confidence,
        fixes_applied=fixes or ["fix-1"],
        files_modified=files or ["/tmp/x.py"],
    )


@pytest.fixture
def cache(tmp_path: Path) -> PatternCache:
    return PatternCache(project_path=tmp_path)


def test_cached_pattern_dataclass() -> None:
    p = CachedPattern(
        pattern_id="abc",
        issue_type=IssueType.FORMATTING,
        strategy="default",
        patterns=["x"],
        confidence=0.9,
        success_rate=1.0,
        usage_count=0,
        last_used=0.0,
        created_at=time.time(),
        files_modified=[],
        fixes_applied=[],
        metadata={},
    )
    assert p.pattern_id == "abc"
    assert p.metadata == {}


def test_cache_init_creates_cache_dir(tmp_path: Path) -> None:
    PatternCache(project_path=tmp_path)
    assert (tmp_path / ".crackerjack" / "patterns").is_dir()


def test_cache_init_no_existing_cache_file(cache: PatternCache) -> None:
    """When the cache file doesn't exist, ``_load_patterns`` is a no-op."""
    cache._load_patterns()  # noqa: SLF001
    assert cache._patterns == {}  # noqa: SLF001


def test_cache_successful_pattern_returns_id(cache: PatternCache) -> None:
    issue = _make_issue()
    result = _make_fix_result()
    plan = {"strategy": "ruff-fix", "patterns": ["apply-black"]}
    pid = cache.cache_successful_pattern(issue=issue, plan=plan, result=result)
    assert pid.startswith(f"{issue.type.value}_ruff-fix_")


def test_cache_successful_pattern_persists_to_disk(
    cache: PatternCache, tmp_path: Path
) -> None:
    issue = _make_issue()
    result = _make_fix_result()
    plan = {"strategy": "ruff-fix", "patterns": ["apply-black"]}
    cache.cache_successful_pattern(issue=issue, plan=plan, result=result)

    cache_file = tmp_path / ".crackerjack" / "patterns" / "pattern_cache.json"
    assert cache_file.exists()
    data = json.loads(cache_file.read_text())
    assert len(data["patterns"]) == 1


def test_cache_successful_pattern_records_metadata(cache: PatternCache) -> None:
    issue = _make_issue()
    result = _make_fix_result(confidence=0.75)
    plan = {"strategy": "s", "patterns": ["p"]}
    cache.cache_successful_pattern(issue=issue, plan=plan, result=result)
    patterns = cache.get_patterns_for_issue(issue)
    assert len(patterns) == 1
    assert patterns[0].confidence == 0.75
    assert patterns[0].metadata["issue_message"] == issue.message


def test_cache_successful_pattern_default_strategy(cache: PatternCache) -> None:
    """A plan without ``strategy`` falls back to ``"unknown"``."""
    issue = _make_issue()
    result = _make_fix_result()
    cache.cache_successful_pattern(issue=issue, plan={}, result=result)
    patterns = cache.get_patterns_for_issue(issue)
    assert patterns[0].strategy == "unknown"


def test_cache_loads_existing_cache_file(tmp_path: Path) -> None:
    """A pre-existing cache file is loaded into ``_patterns``."""
    cache_dir = tmp_path / ".crackerjack" / "patterns"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / "pattern_cache.json"
    cache_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "patterns": [
                    {
                        "pattern_id": "loaded-pattern",
                        "issue_type": "formatting",
                        "strategy": "default",
                        "patterns": ["x"],
                        "confidence": 0.8,
                        "success_rate": 0.7,
                        "usage_count": 3,
                        "last_used": 0.0,
                        "created_at": 0.0,
                        "files_modified": [],
                        "fixes_applied": [],
                        "metadata": {},
                    }
                ],
            }
        )
    )
    cache = PatternCache(project_path=tmp_path)
    patterns = cache.get_patterns_for_issue(_make_issue())
    assert len(patterns) == 1
    assert patterns[0].pattern_id == "loaded-pattern"


def test_cache_load_swallows_corrupt_file(tmp_path: Path) -> None:
    """A corrupt cache file is logged but does not raise."""
    cache_dir = tmp_path / ".crackerjack" / "patterns"
    cache_dir.mkdir(parents=True)
    (cache_dir / "pattern_cache.json").write_text("not valid json {{{")
    cache = PatternCache(project_path=tmp_path)
    patterns = cache.get_patterns_for_issue(_make_issue())
    assert patterns == []


def test_get_patterns_for_issue_empty(cache: PatternCache) -> None:
    assert cache.get_patterns_for_issue(_make_issue()) == []


def test_get_patterns_for_issue_filters_by_type(cache: PatternCache) -> None:
    formatting_issue = _make_issue(issue_type=IssueType.FORMATTING)
    type_error_issue = _make_issue(issue_type=IssueType.TYPE_ERROR)
    cache.cache_successful_pattern(
        issue=formatting_issue, plan={"strategy": "a"}, result=_make_fix_result()
    )
    cache.cache_successful_pattern(
        issue=type_error_issue, plan={"strategy": "b"}, result=_make_fix_result()
    )
    assert len(cache.get_patterns_for_issue(formatting_issue)) == 1
    assert len(cache.get_patterns_for_issue(type_error_issue)) == 1


def test_get_patterns_sorted_by_success_rate_and_confidence(
    cache: PatternCache,
) -> None:
    """Patterns are sorted by (success_rate, confidence) descending."""
    issue = _make_issue()
    pids = []
    for i, (conf, sr) in enumerate([(0.5, 0.3), (0.9, 0.7), (0.9, 0.5)]):
        pid = cache.cache_successful_pattern(
            issue=issue,
            plan={"strategy": f"s{i}"},
            result=_make_fix_result(confidence=conf),
        )
        pids.append(pid)
    # Force success rates via direct mutation.
    cache._patterns[pids[0]].success_rate = 0.3  # noqa: SLF001
    cache._patterns[pids[1]].success_rate = 0.7  # noqa: SLF001
    cache._patterns[pids[2]].success_rate = 0.5  # noqa: SLF001
    cache._save_patterns()  # noqa: SLF001

    sorted_patterns = cache.get_patterns_for_issue(issue)
    # The first should have the highest (success_rate, confidence).
    assert sorted_patterns[0].success_rate == 0.7
    assert sorted_patterns[0].confidence == 0.9


def test_get_best_pattern_for_issue_returns_first(
    cache: PatternCache,
) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "a"}, result=_make_fix_result()
    )
    best = cache.get_best_pattern_for_issue(issue)
    assert best is not None


def test_get_best_pattern_for_issue_returns_none_when_empty(
    cache: PatternCache,
) -> None:
    assert cache.get_best_pattern_for_issue(_make_issue()) is None


def test_use_pattern_returns_false_for_unknown_id(
    cache: PatternCache,
) -> None:
    assert cache.use_pattern("nonexistent") is False


def test_use_pattern_increments_count(cache: PatternCache) -> None:
    issue = _make_issue()
    pid = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    assert cache.use_pattern(pid) is True
    assert cache._patterns[pid].usage_count == 1  # noqa: SLF001
    assert cache._patterns[pid].last_used > 0  # noqa: SLF001


def test_update_pattern_success_rate_no_op_for_unknown_id(
    cache: PatternCache,
) -> None:
    cache.update_pattern_success_rate("nope", success=True)  # no raise


def test_update_pattern_success_rate_no_op_when_no_uses(
    cache: PatternCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    issue = _make_issue()
    pid = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    pattern = cache._patterns[pid]  # noqa: SLF001
    pattern.usage_count = 0
    cache.update_pattern_success_rate(pid, success=True)
    # success_rate unchanged when total_uses == 0
    assert pattern.success_rate == 1.0


def test_update_pattern_success_rate_decrements_on_failure(
    cache: PatternCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed use recomputes success_rate as a weighted average."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    pattern = cache._patterns[pid]  # noqa: SLF001
    pattern.usage_count = 1
    pattern.success_rate = 1.0
    cache.update_pattern_success_rate(pid, success=False)
    # previous_uses = 0, total_uses = 1, current_successes = 0 → 0 / 1 = 0.0
    assert pattern.success_rate == 0.0


def test_update_pattern_success_rate_updates_on_success(
    cache: PatternCache,
) -> None:
    issue = _make_issue()
    pid = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    pattern = cache._patterns[pid]  # noqa: SLF001
    pattern.usage_count = 1
    pattern.success_rate = 0.5
    cache.update_pattern_success_rate(pid, success=True)
    # previous_uses = 0, total_uses = 1, current_successes = 1 → 1.0
    assert pattern.success_rate == 1.0


def test_get_pattern_statistics_empty(cache: PatternCache) -> None:
    stats = cache.get_pattern_statistics()
    assert stats == {"total_patterns": 0}


def test_get_pattern_statistics_with_patterns(cache: PatternCache) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    stats = cache.get_pattern_statistics()
    assert stats["total_patterns"] == 1
    assert stats["patterns_by_type"]["formatting"] == 1
    assert stats["cache_file"].endswith("pattern_cache.json")


def test_get_most_used_patterns(cache: PatternCache) -> None:
    issue = _make_issue()
    for i in range(3):
        cache.cache_successful_pattern(
            issue=issue,
            plan={"strategy": f"s{i}"},
            result=_make_fix_result(),
        )
    # Set usage counts directly.
    pids = list(cache._patterns.keys())  # noqa: SLF001
    cache._patterns[pids[0]].usage_count = 5  # noqa: SLF001
    cache._patterns[pids[1]].usage_count = 10  # noqa: SLF001
    cache._patterns[pids[2]].usage_count = 1  # noqa: SLF001
    most_used = cache._get_most_used_patterns(limit=2)  # noqa: SLF001
    assert len(most_used) == 2
    assert most_used[0]["usage_count"] == 10


def test_cleanup_old_patterns_removes_unused_old(cache: PatternCache) -> None:
    """Old patterns with low usage are removed."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    # Force pattern to be old and unused.
    cache._patterns[pid].created_at = time.time() - (40 * 24 * 60 * 60)  # noqa: SLF001
    cache._patterns[pid].usage_count = 0  # noqa: SLF001
    cache._save_patterns()  # noqa: SLF001

    removed = cache.cleanup_old_patterns(max_age_days=30, min_usage_count=2)
    assert removed == 1
    assert pid not in cache._patterns  # noqa: SLF001


def test_cleanup_old_patterns_removes_low_success(cache: PatternCache) -> None:
    """Patterns with success_rate < 0.2 and usage > 5 are removed."""
    issue = _make_issue()
    pid = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    cache._patterns[pid].success_rate = 0.1  # noqa: SLF001
    cache._patterns[pid].usage_count = 10  # noqa: SLF001
    cache._save_patterns()  # noqa: SLF001

    removed = cache.cleanup_old_patterns()
    assert removed == 1


def test_cleanup_old_patterns_keeps_recent(
    cache: PatternCache,
) -> None:
    """Recent patterns are kept."""
    issue = _make_issue()
    cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    removed = cache.cleanup_old_patterns(max_age_days=30, min_usage_count=2)
    assert removed == 0
    assert len(cache._patterns) == 1  # noqa: SLF001


def test_clear_cache_removes_in_memory_and_file(
    cache: PatternCache, tmp_path: Path
) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    cache_file = tmp_path / ".crackerjack" / "patterns" / "pattern_cache.json"
    assert cache_file.exists()

    cache.clear_cache()
    assert cache._patterns == {}  # noqa: SLF001
    assert not cache_file.exists()


def test_clear_cache_when_no_file(cache: PatternCache) -> None:
    """``clear_cache`` is safe even if the file doesn't exist."""
    cache.clear_cache()  # no raise


def test_export_patterns_success(cache: PatternCache, tmp_path: Path) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    export_path = tmp_path / "export.json"
    assert cache.export_patterns(export_path) is True
    assert export_path.exists()
    data = json.loads(export_path.read_text())
    assert data["version"] == "1.0"
    assert len(data["patterns"]) == 1


def test_export_patterns_returns_false_on_error(
    cache: PatternCache, tmp_path: Path
) -> None:
    """A write failure during export → ``False``."""
    bad_path = tmp_path / "nonexistent_dir" / "x" / "export.json"
    assert cache.export_patterns(bad_path) is False


def test_import_patterns_success(cache: PatternCache, tmp_path: Path) -> None:
    issue = _make_issue()
    cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    export_path = tmp_path / "export.json"
    cache.export_patterns(export_path)

    # Fresh cache, then import.
    new_cache = PatternCache(project_path=tmp_path / "new")
    assert new_cache.import_patterns(export_path) is True
    assert len(new_cache.get_patterns_for_issue(issue)) >= 1


def test_import_patterns_merge_false_overwrites(
    cache: PatternCache, tmp_path: Path
) -> None:
    """``merge=False`` allows existing patterns to be replaced when IDs collide."""
    issue = _make_issue()
    # Pre-seed a pattern and then export it.
    pid_old = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "old"}, result=_make_fix_result()
    )
    export_path = tmp_path / "export.json"
    cache.export_patterns(export_path)

    # Mutate the export file: same pattern_id (will collide), new fields.
    data = json.loads(export_path.read_text())
    data["patterns"][0]["confidence"] = 0.42  # unique marker for new version
    export_path.write_text(json.dumps(data))

    cache.import_patterns(export_path, merge=False)
    # The same pattern_id now has confidence 0.42.
    assert cache._patterns[pid_old].confidence == 0.42  # noqa: SLF001


def test_import_patterns_returns_false_on_error(
    cache: PatternCache, tmp_path: Path
) -> None:
    """A read failure during import → ``False``."""
    assert cache.import_patterns(tmp_path / "nonexistent.json") is False


def test_import_patterns_empty_list_skips_save(
    cache: PatternCache, tmp_path: Path
) -> None:
    """An export with no patterns is a no-op (no _save_patterns call)."""
    export_path = tmp_path / "empty.json"
    export_path.write_text(json.dumps({"version": "1.0", "patterns": []}))
    assert cache.import_patterns(export_path) is True
    assert cache._patterns == {}  # noqa: SLF001


def test_import_patterns_merge_skips_existing_id(
    cache: PatternCache, tmp_path: Path
) -> None:
    """With ``merge=True`` (default), an existing pattern_id is not overwritten."""
    issue = _make_issue()
    pid_old = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )
    old_pattern = cache._patterns[pid_old]  # noqa: SLF001

    # Export and re-import the same pattern; should not overwrite.
    export_path = tmp_path / "export.json"
    cache.export_patterns(export_path)
    # Mutate the export: same ID, new fields. merge=True should keep the old.
    data = json.loads(export_path.read_text())
    data["patterns"][0]["confidence"] = 0.99
    export_path.write_text(json.dumps(data))

    cache.import_patterns(export_path, merge=True)
    # The original confidence should be preserved.
    assert cache._patterns[pid_old].confidence == old_pattern.confidence  # noqa: SLF001


def test_save_patterns_swallows_write_errors(
    cache: PatternCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write failure during ``_save_patterns`` is logged but does not raise."""
    import pathlib

    issue = _make_issue()
    pid = cache.cache_successful_pattern(
        issue=issue, plan={"strategy": "s"}, result=_make_fix_result()
    )

    real_open = pathlib.Path.open

    def _boom_open(self, mode="r", *args, **kwargs):
        if "w" in mode and "pattern_cache" in str(self):
            raise OSError("disk full")
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", _boom_open)
    cache._save_patterns()  # noqa: SLF001
    assert pid in cache._patterns  # noqa: SLF001
