import json
import logging
import time
import typing as t
from dataclasses import asdict, dataclass
from pathlib import Path

from crackerjack.agents.base import FixResult, Issue, IssueType


@dataclass
class CachedPattern:
    pattern_id: str
    issue_type: IssueType
    strategy: str
    patterns: list[str]
    confidence: float
    success_rate: float
    usage_count: int
    last_used: float
    created_at: float
    files_modified: list[str]
    fixes_applied: list[str]
    metadata: dict[str, t.Any]


class PatternCache:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.cache_dir = project_path / ".crackerjack" / "patterns"
        self.cache_file = self.cache_dir / "pattern_cache.json"
        self.logger = logging.getLogger(__name__)

        self._patterns: dict[str, CachedPattern] = {}
        self._loaded = False

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_patterns(self) -> None:
        if self._loaded:
            return

        try:
            if self.cache_file.exists():
                with self.cache_file.open() as f:
                    data = json.load(f)

                for pattern_data in data.get("patterns", []):
                    pattern = CachedPattern(
                        pattern_id=pattern_data["pattern_id"],
                        issue_type=IssueType(pattern_data["issue_type"]),
                        strategy=pattern_data["strategy"],
                        patterns=pattern_data["patterns"],
                        confidence=pattern_data["confidence"],
                        success_rate=pattern_data["success_rate"],
                        usage_count=pattern_data["usage_count"],
                        last_used=pattern_data["last_used"],
                        created_at=pattern_data["created_at"],
                        files_modified=pattern_data["files_modified"],
                        fixes_applied=pattern_data["fixes_applied"],
                        metadata=pattern_data.get("metadata", {}),
                    )
                    self._patterns[pattern.pattern_id] = pattern

                self.logger.info(f"Loaded {len(self._patterns)} cached patterns")
            else:
                self.logger.info("No existing pattern cache found")

        except Exception as e:
            self.logger.warning(f"Failed to load pattern cache: {e}")

        self._loaded = True

    def _save_patterns(self) -> None:
        try:
            data = {
                "version": "1.0",
                "created": time.time(),
                "patterns": [
                    {**asdict(pattern), "issue_type": pattern.issue_type.value}
                    for pattern in self._patterns.values()
                ],
            }

            with self.cache_file.open("w") as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"Saved {len(self._patterns)} patterns to cache")

        except Exception as e:
            self.logger.error(f"Failed to save pattern cache: {e}")

    def cache_successful_pattern(
        self, issue: Issue, plan: dict[str, t.Any], result: FixResult
    ) -> str:
        self._load_patterns()

        pattern_id = (
            f"{issue.type.value}_{plan.get('strategy', 'default')}_{int(time.time())}"
        )

        cached_pattern = CachedPattern(
            pattern_id=pattern_id,
            issue_type=issue.type,
            strategy=plan.get("strategy", "unknown"),
            patterns=plan.get("patterns", []),
            confidence=result.confidence,
            success_rate=1.0,
            usage_count=0,
            last_used=0.0,
            created_at=time.time(),
            files_modified=result.files_modified,
            fixes_applied=result.fixes_applied,
            metadata={
                "issue_id": issue.id,
                "issue_message": issue.message,
                "file_path": issue.file_path,
                "line_number": issue.line_number,
                "severity": issue.severity.value,
                "plan_details": plan,
                "remaining_issues": result.remaining_issues,
                "recommendations": result.recommendations,
            },
        )

        self._patterns[pattern_id] = cached_pattern
        self._save_patterns()

        self.logger.info(f"Cached successful pattern: {pattern_id}")
        return pattern_id

    def get_patterns_for_issue(self, issue: Issue) -> list[CachedPattern]:
        self._load_patterns()

        matching_patterns = [
            pattern
            for pattern in self._patterns.values()
            if pattern.issue_type == issue.type
        ]

        matching_patterns.sort(
            key=lambda p: (p.success_rate, p.confidence), reverse=True
        )

        return matching_patterns

    def get_best_pattern_for_issue(self, issue: Issue) -> CachedPattern | None:
        patterns = self.get_patterns_for_issue(issue)

        if not patterns:
            return None

        return patterns[0]

    def use_pattern(self, pattern_id: str) -> bool:
        self._load_patterns()

        if pattern_id not in self._patterns:
            return False

        pattern = self._patterns[pattern_id]
        pattern.usage_count += 1
        pattern.last_used = time.time()

        self._save_patterns()
        self.logger.debug(
            f"Used pattern {pattern_id} (usage count: {pattern.usage_count})"
        )

        return True

    def update_pattern_success_rate(self, pattern_id: str, success: bool) -> None:
        self._load_patterns()

        if pattern_id not in self._patterns:
            return

        pattern = self._patterns[pattern_id]

        total_uses = pattern.usage_count
        if total_uses > 0:
            current_successes = pattern.success_rate * total_uses
            if success:
                current_successes += 1
            pattern.success_rate = current_successes / total_uses

        self._save_patterns()
        self.logger.debug(
            f"Updated pattern {pattern_id} success rate: {pattern.success_rate: .2f}"
        )

    def get_pattern_statistics(self) -> dict[str, t.Any]:
        self._load_patterns()

        if not self._patterns:
            return {"total_patterns": 0}

        patterns_by_type: dict[str, int] = {}
        total_usage = 0
        avg_success_rate = 0.0

        for pattern in self._patterns.values():
            issue_type = pattern.issue_type.value
            patterns_by_type[issue_type] = patterns_by_type.get(issue_type, 0) + 1
            total_usage += pattern.usage_count
            avg_success_rate += pattern.success_rate

        avg_success_rate = avg_success_rate / len(self._patterns)

        return {
            "total_patterns": len(self._patterns),
            "patterns_by_type": patterns_by_type,
            "total_usage": total_usage,
            "average_success_rate": avg_success_rate,
            "cache_file": str(self.cache_file),
            "most_used_patterns": self._get_most_used_patterns(),
        }

    def _get_most_used_patterns(self, limit: int = 5) -> list[dict[str, t.Any]]:
        patterns = sorted(
            self._patterns.values(), key=lambda p: p.usage_count, reverse=True
        )[:limit]

        return [
            {
                "pattern_id": p.pattern_id,
                "issue_type": p.issue_type.value,
                "strategy": p.strategy,
                "usage_count": p.usage_count,
                "success_rate": p.success_rate,
                "confidence": p.confidence,
            }
            for p in patterns
        ]

    def cleanup_old_patterns(
        self, max_age_days: int = 30, min_usage_count: int = 2
    ) -> int:
        self._load_patterns()

        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        patterns_to_remove = [
            pattern_id
            for pattern_id, pattern in self._patterns.items()
            if (
                pattern.created_at < cutoff_time
                and pattern.usage_count < min_usage_count
            )
            or (pattern.success_rate < 0.2 and pattern.usage_count > 5)
        ]

        for pattern_id in patterns_to_remove:
            del self._patterns[pattern_id]

        if patterns_to_remove:
            self._save_patterns()
            self.logger.info(f"Cleaned up {len(patterns_to_remove)} old patterns")

        return len(patterns_to_remove)

    def clear_cache(self) -> None:
        self._patterns.clear()
        self._loaded = False

        if self.cache_file.exists():
            self.cache_file.unlink()

        self.logger.info("Cleared pattern cache")

    def export_patterns(self, export_path: Path) -> bool:
        self._load_patterns()

        try:
            data = {
                "version": "1.0",
                "exported_at": time.time(),
                "project_path": str(self.project_path),
                "patterns": [
                    {**asdict(pattern), "issue_type": pattern.issue_type.value}
                    for pattern in self._patterns.values()
                ],
            }

            with export_path.open("w") as f:
                json.dump(data, f, indent=2)

            self.logger.info(
                f"Exported {len(self._patterns)} patterns to {export_path}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to export patterns: {e}")
            return False

    def import_patterns(self, import_path: Path, merge: bool = True) -> bool:
        try:
            with import_path.open() as f:
                data = json.load(f)

            imported_count = 0

            for pattern_data in data.get("patterns", []):
                pattern = CachedPattern(
                    pattern_id=pattern_data["pattern_id"],
                    issue_type=IssueType(pattern_data["issue_type"]),
                    strategy=pattern_data["strategy"],
                    patterns=pattern_data["patterns"],
                    confidence=pattern_data["confidence"],
                    success_rate=pattern_data["success_rate"],
                    usage_count=pattern_data["usage_count"],
                    last_used=pattern_data["last_used"],
                    created_at=pattern_data["created_at"],
                    files_modified=pattern_data["files_modified"],
                    fixes_applied=pattern_data["fixes_applied"],
                    metadata=pattern_data.get("metadata", {}),
                )

                if not merge or pattern.pattern_id not in self._patterns:
                    self._patterns[pattern.pattern_id] = pattern
                    imported_count += 1

            if imported_count > 0:
                self._save_patterns()
                self.logger.info(
                    f"Imported {imported_count} patterns from {import_path}"
                )

            return True

        except Exception as e:
            self.logger.error(f"Failed to import patterns: {e}")
            return False
