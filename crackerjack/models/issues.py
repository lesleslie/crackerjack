from __future__ import annotations

import typing as t
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel
from uuid_utils import uuid4


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueType(Enum):
    FORMATTING = "formatting"
    TYPE_ERROR = "type_error"
    SECURITY = "security"
    TEST_FAILURE = "test_failure"
    IMPORT_ERROR = "import_error"
    COMPLEXITY = "complexity"
    DEAD_CODE = "dead_code"
    DEPENDENCY = "dependency"
    DRY_VIOLATION = "dry_violation"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    TEST_ORGANIZATION = "test_organization"
    COVERAGE_IMPROVEMENT = "coverage_improvement"
    REGEX_VALIDATION = "regex_validation"
    SEMANTIC_CONTEXT = "semantic_context"
    WARNING = "warning"
    REFURB = "refurb"


@dataclass
class Issue:
    type: IssueType
    severity: Priority
    message: str
    id: str = field(default_factory=lambda: f"issue_{uuid4().hex}")
    file_path: str | None = None
    line_number: int | None = None
    details: list[str] = field(default_factory=list)
    stage: str = "unknown"


@dataclass
class FixResult:
    success: bool
    confidence: float = 0.0
    fixes_applied: list[str] = field(default_factory=list)
    remaining_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    issue_specific_confidence: float | None = None

    def merge_with(self, other: FixResult) -> FixResult:
        return FixResult(
            success=self.success and other.success,
            confidence=max(self.confidence, other.confidence),
            fixes_applied=self.fixes_applied + other.fixes_applied,
            remaining_issues=list[t.Any](
                set[t.Any](self.remaining_issues + other.remaining_issues),
            ),
            recommendations=self.recommendations + other.recommendations,
            files_modified=list[t.Any](
                set[t.Any](self.files_modified + other.files_modified),
            ),
        )


class CrackerjackRunResult(BaseModel):
    """Versioned, tested contract for `crackerjack run --json` output.

    An external ai-fix-loop driver (a separate piece of software, outside
    this repo) depends on this schema. `schema_version` must be bumped
    whenever this shape changes in a way that isn't purely additive, so the
    external consumer can detect drift instead of silently misparsing
    output.
    """

    schema_version: str = "1"
    success: bool
    issues: list[Issue]
    summary: dict[str, int]
