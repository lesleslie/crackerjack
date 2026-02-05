from __future__ import annotations

import logging
import re
from enum import StrEnum

from crackerjack.agents.base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)

logger = logging.getLogger(__name__)


class WarningCategory(StrEnum):
    SKIP = "skip"
    FIX_AUTOMATIC = "fix_automatic"
    FIX_MANUAL = "fix_manual"
    BLOCKER = "blocker"


WARNING_PATTERNS = {
    "pytest-benchmark": {
        "pattern": r"PytestBenchmarkWarning",
        "category": WarningCategory.SKIP,
        "reason": "Benchmark internals, not user code issues",
    },
    "pytest-unraisable": {
        "pattern": r"PytestUnraisableExceptionWarning.*asyncio",
        "category": WarningCategory.SKIP,
        "reason": "Async cleanup warnings are acceptable in test context",
    },
    "deprecated-pytest-import": {
        "pattern": r"DeprecationWarning:.*pytest\.helpers\.",
        "category": WarningCategory.FIX_AUTOMATIC,
        "fix": "Replace with direct pytest import",
    },
    "import-warning": {
        "pattern": r"ImportWarning:.*deprecated",
        "category": WarningCategory.FIX_AUTOMATIC,
        "fix": "Update to current import location",
    },
    "pending-deprecation": {
        "pattern": r"PendingDeprecationWarning",
        "category": WarningCategory.FIX_MANUAL,
        "reason": "Review migration path first",
    },
}


class WarningSuppressionAgent(SubAgent):
    def __init__(self, context) -> None:
        super().__init__(context)
        self.name = "WarningSuppressionAgent"

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.WARNING}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.WARNING:
            return 0.0

        message_lower = issue.message.lower()

        if "pytest" in message_lower and "warning" in message_lower:
            return 0.9

        if "warning" in message_lower or "deprecation" in message_lower:
            return 0.7

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:

        category = self._categorize_warning(issue)

        if category == WarningCategory.SKIP:
            return self._skip_warning(issue)
        elif category == WarningCategory.FIX_AUTOMATIC:
            return await self._fix_warning(issue)
        elif category == WarningCategory.FIX_MANUAL:
            return self._suggest_manual_fix(issue)
        return await self._fix_blocker(issue)

    def _categorize_warning(self, issue: Issue) -> WarningCategory:
        for config in WARNING_PATTERNS.values():
            if re.search(config["pattern"], issue.message):
                return config["category"]

        return WarningCategory.FIX_MANUAL

    def _skip_warning(self, issue: Issue) -> FixResult:
        self.log(f"Skipping warning (non-critical): {issue.message}")

        return FixResult(
            success=True,
            confidence=1.0,
            fixes_applied=[f"Skipped non-critical warning: {issue.message}"],
            remaining_issues=[],
            recommendations=[],
            files_modified=[],
        )

    async def _fix_warning(self, issue: Issue) -> FixResult:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for warning fix"],
            )

        from pathlib import Path

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)

        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        fixed_content, fix_applied = self._apply_fix(content, issue)

        if fixed_content == content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No fix applied - content unchanged"],
            )

        if self.context.write_file_content(file_path, fixed_content):
            self.log(f"Fixed warning in {file_path.name}")

            return FixResult(
                success=True,
                confidence=0.8,
                fixes_applied=[fix_applied],
                remaining_issues=[],
                files_modified=[str(file_path)],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Failed to write fixed content"],
        )

    def _apply_fix(self, content: str, issue: Issue) -> tuple[str, str]:
        from crackerjack.services.patterns import SAFE_PATTERNS

        message_lower = issue.message.lower()

        if "pytest.helpers" in message_lower:
            fixed = SAFE_PATTERNS["fix_pytest_helpers_import"].apply(content)
            if fixed != content:
                return fixed, "Replaced deprecated pytest.helpers import"

        if "collections.abc" in message_lower and "mapping" in message_lower:
            fixed = SAFE_PATTERNS["fix_deprecated_mapping_import"].apply(content)
            if fixed != content:
                return fixed, "Updated deprecated Mapping import"

        return content, "No fix applied"

    def _suggest_manual_fix(self, issue: Issue) -> FixResult:
        self.log(f"Manual review required for: {issue.message}")

        return FixResult(
            success=False,
            confidence=0.5,
            fixes_applied=[],
            remaining_issues=[
                f"Manual review required: {issue.message}",
                f"Location: {issue.file_path}:{issue.line_number}",
            ],
            recommendations=[
                f"Review warning at {issue.file_path}:{issue.line_number}",
                "Determine if this is a false positive or requires fixing",
            ],
            files_modified=[],
        )

    async def _fix_blocker(self, issue: Issue) -> FixResult:
        self.log(f"BLOCKER warning detected: {issue.message}")

        return FixResult(
            success=False,
            confidence=0.0,
            fixes_applied=[],
            remaining_issues=[
                f"BLOCKER: {issue.message}",
                f"Location: {issue.file_path}:{issue.line_number}",
            ],
            recommendations=[
                "This warning must be fixed before continuing",
                "Review pytest configuration and test setup",
            ],
            files_modified=[],
        )


agent_registry.register(WarningSuppressionAgent)


__all__ = ["WarningSuppressionAgent", "WarningCategory"]
