
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.agents.base import Issue

logger = logging.getLogger(__name__)


@dataclass
class FailedFixAttempt:

    issue_type: str
    error_code: str
    file_path: str
    line_number: int
    original_message: str
    attempted_fix: str
    failure_reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    context_before: str = ""
    context_after: str = ""


@dataclass
class SuccessfulFixPattern:

    issue_type: str
    error_code: str
    pattern_description: str
    before_code: str
    after_code: str
    success_count: int = 1
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())


class PromptEvolution:

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or Path.home() / ".cache" / "crackerjack" / "prompt_evolution"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.failed_attempts: list[FailedFixAttempt] = []
        self.successful_patterns: dict[str, SuccessfulFixPattern] = {}

        self._load_state()

    def record_failed_fix(
        self,
        issue: Issue,
        attempted_fix: str,
        failure_reason: str,
        context: dict[str, str] | None = None,
    ) -> None:
        context = context or {}

        attempt = FailedFixAttempt(
            issue_type=issue.type.value,
            error_code=self._extract_error_code(issue.message),
            file_path=str(issue.file_path) if issue.file_path else "",
            line_number=issue.line_number or 0,
            original_message=issue.message,
            attempted_fix=attempted_fix,
            failure_reason=failure_reason,
            context_before=context.get("before", ""),
            context_after=context.get("after", ""),
        )

        self.failed_attempts.append(attempt)
        self._save_state()

        logger.info(f"Recorded failed fix: {issue.type.value} - {failure_reason}")

    def record_successful_fix(
        self,
        issue: Issue,
        before_code: str,
        after_code: str,
    ) -> None:
        error_code = self._extract_error_code(issue.message)
        pattern_key = f"{issue.type.value}:{error_code}"

        if pattern_key in self.successful_patterns:
            pattern = self.successful_patterns[pattern_key]
            pattern.success_count += 1
            pattern.last_used = datetime.now().isoformat()
        else:
            self.successful_patterns[pattern_key] = SuccessfulFixPattern(
                issue_type=issue.type.value,
                error_code=error_code,
                pattern_description=self._generate_pattern_description(before_code, after_code),
                before_code=before_code,
                after_code=after_code,
            )

        self._save_state()
        logger.info(f"Recorded successful fix pattern: {pattern_key}")

    def get_evolved_prompt(self, issue: Issue, base_prompt: str) -> str:
        error_code = self._extract_error_code(issue.message)
        pattern_key = f"{issue.type.value}:{error_code}"

        enhancements = []


        if pattern_key in self.successful_patterns:
            pattern = self.successful_patterns[pattern_key]
            enhancements.append(
                f"\n\nLEARNED PATTERN (success count: {pattern.success_count}):\n"
                f"Description: {pattern.pattern_description}\n"
                f"Before: {pattern.before_code[:200]}\n"
                f"After: {pattern.after_code[:200]}"
            )


        related_failures = [
            f for f in self.failed_attempts
            if f.error_code == error_code and f.issue_type == issue.type.value
        ][-3:]

        if related_failures:
            failure_warnings = []
            for failure in related_failures:
                failure_warnings.append(
                    f"- AVOID: {failure.attempted_fix[:100]} (failed: {failure.failure_reason})"
                )
            enhancements.append(
                f"\n\nWARNINGS FROM PAST FAILURES:\n" + "\n".join(failure_warnings)
            )

        if enhancements:
            return base_prompt + "".join(enhancements)

        return base_prompt

    def analyze_failure_patterns(self) -> dict[str, list[str]]:
        patterns: dict[str, list[str]] = {}

        for failure in self.failed_attempts:
            key = f"{failure.issue_type}:{failure.error_code}"
            if key not in patterns:
                patterns[key] = []
            patterns[key].append(failure.failure_reason)


        result: dict[str, list[str]] = {}
        for key, reasons in patterns.items():
            reason_counts: dict[str, int] = {}
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            result[key] = sorted(reason_counts.keys(), key=lambda r: reason_counts[r], reverse=True)

        return result

    def get_success_rate(self, issue_type: str, error_code: str) -> float:
        pattern_key = f"{issue_type}:{error_code}"

        success_count = 0
        if pattern_key in self.successful_patterns:
            success_count = self.successful_patterns[pattern_key].success_count

        failure_count = sum(
            1 for f in self.failed_attempts
            if f.issue_type == issue_type and f.error_code == error_code
        )

        total = success_count + failure_count
        if total == 0:
            return 0.0

        return success_count / total

    def _extract_error_code(self, message: str) -> str:

        match = re.search(r'\[([a-z0-9-]+)\]', message)
        if match:
            return match.group(1)


        message_lower = message.lower()
        if "not defined" in message_lower or "name" in message_lower:
            return "name-defined"
        if "need type annotation" in message_lower:
            return "var-annotated"
        if "has no attribute" in message_lower or "no attribute" in message_lower:
            return "attr-defined"
        if "incompatible" in message_lower and "argument" in message_lower:
            return "call-arg"
        if "incompatible type" in message_lower:
            return "arg-type"

        return "unknown"

    def _generate_pattern_description(self, before: str, after: str) -> str:

        if "import " in after and "import " not in before:
            return "Added missing import statement"
        if ": " in after and ": " not in before:
            return "Added type annotation"
        if "# type: ignore" in after:
            return "Added type: ignore comment"
        if len(after) < len(before):
            return "Removed redundant code"

        return "Code transformation applied"

    def _save_state(self) -> None:
        state = {
            "failed_attempts": [
                {
                    "issue_type": f.issue_type,
                    "error_code": f.error_code,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "original_message": f.original_message,
                    "attempted_fix": f.attempted_fix,
                    "failure_reason": f.failure_reason,
                    "timestamp": f.timestamp,
                }
                for f in self.failed_attempts[-100:]
            ],
            "successful_patterns": {
                k: {
                    "issue_type": v.issue_type,
                    "error_code": v.error_code,
                    "pattern_description": v.pattern_description,
                    "before_code": v.before_code,
                    "after_code": v.after_code,
                    "success_count": v.success_count,
                    "last_used": v.last_used,
                }
                for k, v in self.successful_patterns.items()
            },
        }

        state_file = self.storage_path / "evolution_state.json"
        state_file.write_text(json.dumps(state, indent=2))

    def _load_state(self) -> None:
        state_file = self.storage_path / "evolution_state.json"

        if not state_file.exists():
            return

        try:
            state = json.loads(state_file.read_text())

            self.failed_attempts = [
                FailedFixAttempt(**f) for f in state.get("failed_attempts", [])
            ]

            self.successful_patterns = {
                k: SuccessfulFixPattern(**v)
                for k, v in state.get("successful_patterns", {}).items()
            }

            logger.info(
                f"Loaded prompt evolution state: {len(self.failed_attempts)} failures, "
                f"{len(self.successful_patterns)} patterns"
            )
        except Exception as e:
            logger.warning(f"Failed to load prompt evolution state: {e}")


_evolution_instance: PromptEvolution | None = None


def get_prompt_evolution() -> PromptEvolution:
    global _evolution_instance
    if _evolution_instance is None:
        _evolution_instance = PromptEvolution()
    return _evolution_instance
