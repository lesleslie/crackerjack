import asyncio
import json
import time
import typing as t
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from acb.depends import depends

# Phase 9.2: ACB Integration - Module registration for dependency injection
MODULE_ID: Final[UUID] = uuid4()
MODULE_STATUS: Final[str] = "stable"


@dataclass
class ErrorPattern:
    pattern_id: str
    error_type: str
    error_code: str
    message_pattern: str
    file_pattern: str | None = None
    common_fixes: list[str] | None = None
    auto_fixable: bool = False
    frequency: int = 1
    last_seen: float | None = None

    def __post_init__(self) -> None:
        if self.common_fixes is None:
            self.common_fixes = []
        if self.last_seen is None:
            self.last_seen = time.time()

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class FixResult:
    fix_id: str
    pattern_id: str
    success: bool
    files_affected: list[str]
    time_taken: float
    error_message: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


class ErrorCache:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self._lock = asyncio.Lock()
        self.cache_dir = cache_dir or Path.home() / ".cache" / "crackerjack-mcp"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_file = self.cache_dir / "error_patterns.json"
        self.fixes_file = self.cache_dir / "fix_results.json"
        self.patterns: dict[str, ErrorPattern] = {}
        self.fix_results: list[FixResult] = []
        self._load_cache()

    async def add_pattern(self, pattern: ErrorPattern) -> None:
        async with self._lock:
            existing = self.patterns.get(pattern.pattern_id)
            if existing:
                self._update_existing_pattern(existing, pattern)
            else:
                self.patterns[pattern.pattern_id] = pattern
            self._save_patterns()

    def _update_existing_pattern(
        self,
        existing: ErrorPattern,
        pattern: ErrorPattern,
    ) -> None:
        existing.frequency += 1
        existing.last_seen = time.time()
        if pattern.common_fixes:
            self._merge_fixes(existing, pattern.common_fixes)

    def _merge_fixes(self, existing: ErrorPattern, new_fixes: list[str]) -> None:
        for fix in new_fixes:
            if fix not in (existing.common_fixes or []):
                if existing.common_fixes is None:
                    existing.common_fixes = []
                existing.common_fixes.append(fix)

    def get_pattern(self, pattern_id: str) -> ErrorPattern | None:
        return self.patterns.get(pattern_id)

    def find_patterns_by_type(self, error_type: str) -> list[ErrorPattern]:
        return [
            pattern
            for pattern in self.patterns.values()
            if pattern.error_type == error_type
        ]

    def find_patterns_by_code(self, error_code: str) -> list[ErrorPattern]:
        return [
            pattern
            for pattern in self.patterns.values()
            if pattern.error_code == error_code
        ]

    def get_common_patterns(self, limit: int = 20) -> list[ErrorPattern]:
        patterns = list[t.Any](self.patterns.values())
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns[:limit]

    def get_auto_fixable_patterns(self) -> list[ErrorPattern]:
        return [pattern for pattern in self.patterns.values() if pattern.auto_fixable]

    async def add_fix_result(self, result: FixResult) -> None:
        async with self._lock:
            self.fix_results.append(result)
            pattern = self.patterns.get(result.pattern_id)
            if pattern and result.success:
                pattern.auto_fixable = True
                fix_command = f"Auto-fix applied for {result.pattern_id}"
                if pattern.common_fixes is None:
                    pattern.common_fixes = []
                if fix_command not in pattern.common_fixes:
                    pattern.common_fixes.append(fix_command)
            self._save_fixes()
        self._save_patterns()

    def get_fix_success_rate(self, pattern_id: str) -> float:
        pattern_fixes = [
            result for result in self.fix_results if result.pattern_id == pattern_id
        ]
        if not pattern_fixes:
            return 0.0
        successful = sum(1 for result in pattern_fixes if result.success)
        return successful / len(pattern_fixes)

    def get_recent_patterns(self, hours: int = 24) -> list[ErrorPattern]:
        cutoff_time = time.time() - (hours * 3600)

        return [
            pattern
            for pattern in self.patterns.values()
            if (pattern.last_seen or 0) >= cutoff_time
        ]

    def create_pattern_from_error(
        self,
        error_output: str,
        error_type: str,
    ) -> ErrorPattern | None:
        try:
            lines = error_output.split("\n")
            for line in lines:
                line = line.strip()
                if not self._is_valid_error_line(line):
                    continue
                error_code, message_pattern = self._extract_error_info(line, error_type)
                if self._is_meaningful_pattern(error_code, message_pattern):
                    return self._create_error_pattern(
                        error_type,
                        error_code,
                        message_pattern,
                    )

            return None
        except Exception:
            return None

    def _is_valid_error_line(self, line: str) -> bool:
        return bool(line and any(char.isalpha() for char in line))

    def _extract_error_info(self, line: str, error_type: str) -> tuple[str, str]:
        if error_type == "ruff":
            return self._extract_ruff_info(line)
        if error_type == "pyright":
            return self._extract_pyright_info(line)
        if error_type == "bandit":
            return self._extract_bandit_info(line)
        return "", line

    def _extract_ruff_info(self, line: str) -> tuple[str, str]:
        error_code = ""
        message_pattern = line
        if ": " in line and any(c.isdigit() for c in line):
            parts = line.split(": ")
            if len(parts) >= 4:
                code_msg = parts[-1].strip()
                if " " in code_msg:
                    code_part, msg_part = code_msg.split(" ", 1)
                    if code_part.isupper() or code_part[0].isupper():
                        error_code = code_part
                        message_pattern = msg_part

        return error_code, message_pattern

    def _extract_pyright_info(self, line: str) -> tuple[str, str]:
        error_code = ""
        message_pattern = line
        if "-error: " in line:
            parts = line.split("-error: ")
            if len(parts) >= 2:
                message_pattern = parts[1].strip()
                if "(" in message_pattern and ")" in message_pattern:
                    error_code = message_pattern.split("(")[-1].split(")")[0]

        return error_code, message_pattern

    def _extract_bandit_info(self, line: str) -> tuple[str, str]:
        error_code = ""
        message_pattern = line
        if "Issue: " in line:
            message_pattern = line.split("Issue: ")[-1].strip()
            if "Test: " in message_pattern:
                parts = message_pattern.split("Test: ")
                message_pattern = parts[0].strip()
                error_code = parts[1].strip() if len(parts) > 1 else ""

        return error_code, message_pattern

    def _is_meaningful_pattern(self, error_code: str, message_pattern: str) -> bool:
        return bool(error_code) or len(message_pattern) > 10

    def _create_error_pattern(
        self,
        error_type: str,
        error_code: str,
        message_pattern: str,
    ) -> ErrorPattern:
        pattern_id = f"{error_type}_{error_code}_{hash(message_pattern) % 10000}"

        return ErrorPattern(
            pattern_id=pattern_id,
            error_type=error_type,
            error_code=error_code,
            message_pattern=message_pattern,
            auto_fixable=error_type == "ruff",
        )

    async def analyze_output_for_patterns(
        self,
        output: str,
        error_type: str,
    ) -> list[ErrorPattern]:
        patterns: list[ErrorPattern] = []
        sections = output.split("\n\n")
        for section in sections:
            if section.strip():
                pattern = self.create_pattern_from_error(section, error_type)
                if pattern:
                    await self.add_pattern(pattern)
                    patterns.append(pattern)

        return patterns

    def get_cache_stats(self) -> dict[str, t.Any]:
        total_patterns = len(self.patterns)
        auto_fixable = len(self.get_auto_fixable_patterns())
        total_fixes = len(self.fix_results)
        successful_fixes = sum(1 for result in self.fix_results if result.success)
        frequencies = [pattern.frequency for pattern in self.patterns.values()]
        avg_frequency = sum(frequencies) / len(frequencies) if frequencies else 0
        type_counts: dict[str, int] = {}
        for pattern in self.patterns.values():
            type_counts[pattern.error_type] = type_counts.get(pattern.error_type, 0) + 1

        return {
            "total_patterns": total_patterns,
            "auto_fixable_patterns": auto_fixable,
            "auto_fixable_rate": (auto_fixable / total_patterns) * 100
            if total_patterns
            else 0,
            "total_fix_attempts": total_fixes,
            "successful_fixes": successful_fixes,
            "fix_success_rate": (successful_fixes / total_fixes) * 100
            if total_fixes
            else 0,
            "average_pattern_frequency": avg_frequency,
            "error_types": type_counts,
        }

    def cleanup_old_patterns(self, days: int = 30) -> int:
        cutoff_time = time.time() - (days * 24 * 3600)
        old_patterns = [
            pattern_id
            for pattern_id, pattern in self.patterns.items()
            if (pattern.last_seen or 0) < cutoff_time
        ]
        for pattern_id in old_patterns:
            del self.patterns[pattern_id]
        if old_patterns:
            self._save_patterns()

        return len(old_patterns)

    def export_patterns(self, file_path: Path) -> None:
        export_data = {
            "export_time": time.time(),
            "total_patterns": len(self.patterns),
            "patterns": [pattern.to_dict() for pattern in self.patterns.values()],
            "fix_results": [result.to_dict() for result in self.fix_results],
            "stats": self.get_cache_stats(),
        }
        with file_path.open("w") as f:
            json.dump(export_data, f, indent=2)

    def _load_cache(self) -> None:
        if self.patterns_file.exists():
            try:
                with self.patterns_file.open("r") as f:
                    patterns_data = json.load(f)
                self.patterns = {
                    pid: ErrorPattern(**data) for pid, data in patterns_data.items()
                }
            except Exception:
                self.patterns = {}
        if self.fixes_file.exists():
            try:
                with self.fixes_file.open("r") as f:
                    fixes_data = json.load(f)
                self.fix_results = [FixResult(**data) for data in fixes_data]
            except Exception:
                self.fix_results = []

    def _save_patterns(self) -> None:
        with suppress(OSError, json.JSONEncodeError):
            patterns_data = {
                pid: pattern.to_dict() for pid, pattern in self.patterns.items()
            }
            with self.patterns_file.open("w") as f:
                json.dump(patterns_data, f, indent=2)

    def _save_fixes(self) -> None:
        with suppress(OSError, json.JSONEncodeError):
            fixes_data = [result.to_dict() for result in self.fix_results]
            with self.fixes_file.open("w") as f:
                json.dump(fixes_data, f, indent=2)

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID for ACB integration."""
        return MODULE_ID

    @property
    def module_status(self) -> str:
        """Module status for ACB integration."""
        return MODULE_STATUS


# Phase 9.2: ACB Integration - Register ErrorCache with dependency injection system
with suppress(Exception):
    depends.set(ErrorCache)
