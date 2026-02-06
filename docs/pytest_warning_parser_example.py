import re
from dataclasses import dataclass
from enum import StrEnum

from crackerjack.agents.base import Issue, IssueType, Priority


class WarningCategory(StrEnum):
    SKIP = "skip"
    FIX_AUTOMATIC = "fix_automatic"
    FIX_MANUAL = "fix_manual"
    BLOCKER = "blocker"


@dataclass
class WarningPattern:
    pattern: str
    category: WarningCategory
    reason: str
    example: str


WARNING_PATTERNS: dict[str, WarningPattern] = {
    "pytest-benchmark": WarningPattern(
        pattern=r"PytestBenchmarkWarning",
        category=WarningCategory.SKIP,
        reason="Benchmark internals, not user code issues",
        example="tests/test_benchmarks.py: 10: PytestBenchmarkWarning: internal warning",
    ),
    "pytest-unraisable": WarningPattern(
        pattern=r"PytestUnraisableExceptionWarning.*asyncio",
        category=WarningCategory.SKIP,
        reason="Async cleanup warnings are acceptable in test context",
        example="tests/test_async.py: 45: PytestUnraisableExceptionWarning: asyncio",
    ),
    "benchmark-collection": WarningPattern(
        pattern=r"cannot collect test class.*Test.*__init__",
        category=WarningCategory.SKIP,
        reason="Benchmark classes with __init__ are expected",
        example="tests/benchmarks/test_benchmark.py: 10: cannot collect 'TestBench'",
    ),
    "deprecated-pytest-import": WarningPattern(
        pattern=r"DeprecationWarning:.*pytest\.helpers\.",
        category=WarningCategory.FIX_AUTOMATIC,
        reason="Replace with direct pytest import",
        example="DeprecationWarning: pytest.helpers.sysprog is deprecated",
    ),
    "deprecated-assert": WarningPattern(
        pattern=r"DeprecationWarning:.*assert (called|rewritten)",
        category=WarningCategory.FIX_AUTOMATIC,
        reason="Update to modern pytest assertion style",
        example="DeprecationWarning: assert called on a string",
    ),
    "import-warning": WarningPattern(
        pattern=r"ImportWarning:.*deprecated",
        category=WarningCategory.FIX_AUTOMATIC,
        reason="Update to current import location",
        example="ImportWarning: 'collections.abc.Mapping' deprecated",
    ),
    "fixture-scope": WarningPattern(
        pattern=r"fixture.*scope mismatch.*use 'scope'",
        category=WarningCategory.FIX_AUTOMATIC,
        reason="Add explicit scope to fixture",
        example="test_foo.py: 20: fixture 'db' scope mismatch",
    ),
    "pending-deprecation": WarningPattern(
        pattern=r"PendingDeprecationWarning",
        category=WarningCategory.FIX_MANUAL,
        reason="Review migration path first",
        example="PendingDeprecationWarning: foo() will be deprecated in 2.0",
    ),
    "experimental-api": WarningPattern(
        pattern=r"experimental.*API",
        category=WarningCategory.FIX_MANUAL,
        reason="Experimental APIs may change",
        example="UserWarning: Using experimental API",
    ),
    "config-error": WarningPattern(
        pattern=r"PytestConfigWarning",
        category=WarningCategory.BLOCKER,
        reason="Configuration errors prevent proper test execution",
        example="PytestConfigWarning: Unknown config option",
    ),
}


def parse_pytest_warnings(test_output: str) -> list[Issue]:
    issues = []

    warning_pattern = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<type>\w+Warning):\s*(?P<message>.+)$",
        re.MULTILINE,
    )

    for match in warning_pattern.finditer(test_output):
        file_path = match.group("file")
        line_number = int(match.group("line"))
        warning_type = match.group("type")
        message = f"{warning_type}: {match.group('message').strip()}"

        if "Config" in warning_type or "Error" in warning_type:
            severity = Priority.HIGH
        elif "Deprecation" in warning_type:
            severity = Priority.MEDIUM
        else:
            severity = Priority.LOW

        issue = Issue(
            type=IssueType.WARNING,
            severity=severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
        )
        issues.append(issue)

    return issues


def categorize_warning(issue: Issue) -> tuple[WarningCategory, str]:
    for pattern_name, config in WARNING_PATTERNS.items():
        if re.search(config.pattern, issue.message):
            return config.category, pattern_name

    return WarningCategory.FIX_MANUAL, "unknown"


def categorize_all_warnings(issues: list[Issue]) -> dict[WarningCategory, list[Issue]]:
    categorized: dict[WarningCategory, list[Issue]] = {
        WarningCategory.SKIP: [],
        WarningCategory.FIX_AUTOMATIC: [],
        WarningCategory.FIX_MANUAL: [],
        WarningCategory.BLOCKER: [],
    }

    for issue in issues:
        category, _ = categorize_warning(issue)
        categorized[category].append(issue)

    return categorized


def print_warning_summary(issues: list[Issue]) -> None:
    categorized = categorize_all_warnings(issues)

    total = len(issues)
    print(f"\n📊 Warning Summary: {total} warnings detected\n")

    skip_count = len(categorized[WarningCategory.SKIP])
    print(f"  ✅ SKIP: {skip_count}")
    for issue in categorized[WarningCategory.SKIP][:3]:
        _, pattern_name = categorize_warning(issue)
        reason = WARNING_PATTERNS[pattern_name].reason
        print(f"     - {pattern_name}: {issue.file_path}:{issue.line_number}")
        print(f"       Reason: {reason}")
    if skip_count > 3:
        print(f"     ... and {skip_count - 3} more")

    autofix_count = len(categorized[WarningCategory.FIX_AUTOMATIC])
    print(f"\n  🔧 AUTO-FIX: {autofix_count}")
    for issue in categorized[WarningCategory.FIX_AUTOMATIC][:3]:
        _, pattern_name = categorize_warning(issue)
        print(f"     - {pattern_name}: {issue.file_path}:{issue.line_number}")
    if autofix_count > 3:
        print(f"     ... and {autofix_count - 3} more")

    manual_count = len(categorized[WarningCategory.FIX_MANUAL])
    print(f"\n  👁 MANUAL: {manual_count}")
    for issue in categorized[WarningCategory.FIX_MANUAL]:
        print(f"     - {issue.file_path}:{issue.line_number}: {issue.message}")

    blocker_count = len(categorized[WarningCategory.BLOCKER])
    if blocker_count > 0:
        print(f"\n  🚨 BLOCKER: {blocker_count}")
        for issue in categorized[WarningCategory.BLOCKER]:
            print(f"     - {issue.file_path}:{issue.line_number}: {issue.message}")


if __name__ == "__main__":
    example_output = """
tests/test_benchmarks.py: 10: PytestBenchmarkWarning: internal warning
tests/test_benchmarks.py: 20: PytestBenchmarkWarning: internal warning
tests/test_async.py: 45: PytestUnraisableExceptionWarning: asyncio cleanup
tests/test_foo.py: 15: DeprecationWarning: pytest.helpers.sysprog is deprecated
tests/test_bar.py: 20: DeprecationWarning: pytest.helpers.sysprog is deprecated
tests/test_fixture.py: 30: fixture 'db' scope mismatch, use 'scope="session"'
tests/test_api.py: 50: PendingDeprecationWarning: foo() will be deprecated in 2.0
tests/test_legacy.py: 60: UserWarning: Using experimental API
"""

    print("Parsing pytest warnings...")
    issues = parse_pytest_warnings(example_output)

    print(f"Found {len(issues)} warnings")
    print_warning_summary(issues)
