"""
WarningSuppressionAgent: Detect, categorize, and fix pytest warnings.

This agent intelligently handles warnings by:
1. Categorizing warnings (SKIP, AUTO-FIX, MANUAL, BLOCKER)
2. Skipping non-critical warnings (benchmarks, asyncio cleanup)
3. Auto-fixing safe warnings (deprecated imports, fixture scopes)
4. Flagging warnings requiring manual review
"""

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
    """Categories of warnings with handling strategies."""

    SKIP = "skip"  # Non-critical, ignore
    FIX_AUTOMATIC = "fix_automatic"  # Safe to fix automatically
    FIX_MANUAL = "fix_manual"  # Requires human review
    BLOCKER = "blocker"  # Must fix before continuing


# Warning pattern database
WARNING_PATTERNS = {
    # SKIP: Non-critical warnings
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
    # FIX_AUTOMATIC: Safe to fix
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
    # FIX_MANUAL: Requires review
    "pending-deprecation": {
        "pattern": r"PendingDeprecationWarning",
        "category": WarningCategory.FIX_MANUAL,
        "reason": "Review migration path first",
    },
}


class WarningSuppressionAgent(SubAgent):
    """Agent for detecting and fixing codebase warnings."""

    def __init__(self, context) -> None:
        super().__init__(context)
        self.name = "WarningSuppressionAgent"

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.WARNING}

    async def can_handle(self, issue: Issue) -> float:
        """Check if issue is a warning we can handle."""
        if issue.type != IssueType.WARNING:
            return 0.0

        message_lower = issue.message.lower()

        # High confidence for pytest warnings
        if "pytest" in message_lower and "warning" in message_lower:
            return 0.9

        # Medium confidence for general warnings
        if "warning" in message_lower or "deprecation" in message_lower:
            return 0.7

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Categorize and fix warning based on pattern database."""
        # Step 1: Categorize warning
        category = self._categorize_warning(issue)

        # Step 2: Handle based on category
        if category == WarningCategory.SKIP:
            return self._skip_warning(issue)
        elif category == WarningCategory.FIX_AUTOMATIC:
            return await self._fix_warning(issue)
        elif category == WarningCategory.FIX_MANUAL:
            return self._suggest_manual_fix(issue)
        else:  # BLOCKER
            return await self._fix_blocker(issue)

    def _categorize_warning(self, issue: Issue) -> WarningCategory:
        """Match warning against pattern database."""
        for config in WARNING_PATTERNS.values():
            if re.search(config["pattern"], issue.message):
                return config["category"]

        # Default: manual review if not in database
        return WarningCategory.FIX_MANUAL

    def _skip_warning(self, issue: Issue) -> FixResult:
        """Handle warning that should be skipped."""
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
        """Attempt to automatically fix warning."""
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for warning fix"],
            )

        # Get file content
        from pathlib import Path

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)

        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        # Apply fix based on warning type
        fixed_content, fix_applied = self._apply_fix(content, issue)

        if fixed_content == content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No fix applied - content unchanged"],
            )

        # Write fixed content
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
        """Apply appropriate fix based on warning type."""
        message_lower = issue.message.lower()

        # Fix deprecated pytest imports
        if "pytest.helpers" in message_lower:
            # Replace pytest.helpers imports
            import re

            fixed = re.sub(
                r"from pytest\.helpers import (\w+)",
                r"from _pytest.pytester import \1",
                content,
            )
            if fixed != content:
                return fixed, "Replaced deprecated pytest.helpers import"

        # Fix deprecated collection imports
        if "collections.abc" in message_lower and "mapping" in message_lower:
            import re

            fixed = re.sub(
                r"from collections\.abc import Mapping",
                r"from typing import Mapping",
                content,
            )
            if fixed != content:
                return fixed, "Updated deprecated Mapping import"

        # No fix applied
        return content, "No fix applied"

    def _suggest_manual_fix(self, issue: Issue) -> FixResult:
        """Provide manual fix suggestions."""
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
        """Handle blocker warnings that must be fixed."""
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
