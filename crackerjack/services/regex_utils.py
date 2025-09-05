"""
Utility functions for immediate regex pattern testing and validation.

Provides quick functions for testing regex patterns before adding them
to the centralized registry, and utilities for migrating existing re.sub() calls.
"""

import re
from pathlib import Path

from crackerjack.services.regex_patterns import SAFE_PATTERNS


def test_pattern_immediately(
    pattern: str,
    replacement: str,
    test_cases: list[tuple[str, str]],
    description: str = "",
) -> dict[str, any]:
    """
    Test a regex pattern immediately without adding to registry.

    Returns a report of test results for quick validation.
    """
    results = {
        "pattern": pattern,
        "replacement": replacement,
        "description": description,
        "all_passed": True,
        "test_results": [],
        "warnings": [],
        "errors": [],
    }

    # Check for forbidden replacement syntax first
    forbidden_patterns = [
        r"\\g\s*<\s*\d+\s*>",  # \g < 1 > with spaces
        r"\\g<\s+\d+>",  # \g< 1> with space after <
        r"\\g<\d+\s+>",  # \g<1 > with space before >
    ]

    for forbidden in forbidden_patterns:
        if re.search(forbidden, replacement):
            results["errors"].append(
                f"CRITICAL: Bad replacement syntax detected: '{replacement}'. Use \\g<1> not \\g < 1 >"
            )
            results["all_passed"] = False
            return results

    # Validate pattern compilation
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        results["errors"].append(f"Invalid regex pattern: {e}")
        results["all_passed"] = False
        return results

    # Test all cases
    for i, (input_text, expected) in enumerate(test_cases):
        try:
            result = compiled.sub(replacement, input_text)
            passed = result == expected
            results["test_results"].append(
                {
                    "test_case": i + 1,
                    "input": input_text,
                    "expected": expected,
                    "actual": result,
                    "passed": passed,
                }
            )
            if not passed:
                results["all_passed"] = False
        except Exception as e:
            results["test_results"].append(
                {
                    "test_case": i + 1,
                    "input": input_text,
                    "expected": expected,
                    "actual": f"ERROR: {e}",
                    "passed": False,
                }
            )
            results["all_passed"] = False

    # Safety warnings
    if ".*.*" in pattern:
        results["warnings"].append(
            "Multiple .* constructs may cause performance issues"
        )
    if ".+.+" in pattern:
        results["warnings"].append(
            "Multiple .+ constructs may cause performance issues"
        )

    return results


def print_pattern_test_report(results: dict[str, any]) -> None:
    """Print a formatted report of pattern test results."""
    print("\n🔍 REGEX PATTERN TEST REPORT")
    print("=" * 50)
    print(f"Pattern: {results['pattern']}")
    print(f"Replacement: {results['replacement']}")
    if results["description"]:
        print(f"Description: {results['description']}")
    print()

    if results["errors"]:
        print("❌ ERRORS:")
        for error in results["errors"]:
            print(f"  • {error}")
        print()

    if results["warnings"]:
        print("⚠️  WARNINGS:")
        for warning in results["warnings"]:
            print(f"  • {warning}")
        print()

    print("📋 TEST CASES:")
    for test in results["test_results"]:
        status = "✅ PASS" if test["passed"] else "❌ FAIL"
        print(
            f"  {status} Test {test['test_case']}: '{test['input']}' → '{test['actual']}'"
        )
        if not test["passed"]:
            print(f"    Expected: '{test['expected']}'")

    print(
        f"\n🎯 OVERALL: {'✅ ALL TESTS PASSED' if results['all_passed'] else '❌ TESTS FAILED'}"
    )
    print("=" * 50)


def quick_pattern_test(
    pattern: str,
    replacement: str,
    test_cases: list[tuple[str, str]],
    description: str = "",
) -> bool:
    """Quick test function that returns True if all tests pass."""
    results = test_pattern_immediately(pattern, replacement, test_cases, description)
    print_pattern_test_report(results)
    return results["all_passed"]


def find_safe_pattern_for_text(text: str) -> list[str]:
    """Find which existing safe patterns would match the given text."""
    matches = []
    for name, pattern in SAFE_PATTERNS.items():
        try:
            if pattern.test(text):
                matches.append(name)
        except Exception:
            # Skip patterns that error
            continue
    return matches


def suggest_migration_for_re_sub(
    original_pattern: str, original_replacement: str, sample_text: str = ""
) -> dict[str, any]:
    """
    Suggest how to migrate a raw re.sub() call to use safe patterns.

    Args:
        original_pattern: The original regex pattern
        original_replacement: The original replacement string
        sample_text: Optional sample text to test against

    Returns:
        Dictionary with migration suggestions
    """
    suggestion = {
        "original_pattern": original_pattern,
        "original_replacement": original_replacement,
        "existing_matches": [],
        "needs_new_pattern": True,
        "safety_issues": [],
        "suggested_name": "",
        "test_cases_needed": [],
    }

    # Check for safety issues first
    forbidden_patterns = [
        r"\\g\s*<\s*\d+\s*>",  # \g < 1 > with spaces
        r"\\g<\s+\d+>",  # \g< 1> with space after <
        r"\\g<\d+\s+>",  # \g<1 > with space before >
    ]

    for forbidden in forbidden_patterns:
        if re.search(forbidden, original_replacement):
            suggestion["safety_issues"].append(
                "CRITICAL: Bad replacement syntax - spaces in \\g<1>"
            )

    # Look for existing patterns that might work
    if sample_text:
        matches = find_safe_pattern_for_text(sample_text)
        suggestion["existing_matches"] = matches
        if matches:
            suggestion["needs_new_pattern"] = False

    # Generate suggested pattern name based on original pattern
    if "python.*-.*m" in original_pattern:
        suggestion["suggested_name"] = "fix_python_command_spacing"
    elif r"\-\s*\-" in original_pattern:
        suggestion["suggested_name"] = "fix_double_dash_spacing"
    elif "token" in original_pattern.lower():
        suggestion["suggested_name"] = "fix_token_pattern"
    elif "password" in original_pattern.lower():
        suggestion["suggested_name"] = "fix_password_pattern"
    else:
        # Generate name from pattern keywords
        keywords = re.findall(r"[a-zA-Z]+", original_pattern)
        if keywords:
            suggestion["suggested_name"] = (
                f"fix_{'_'.join(keywords[:3])}_pattern".lower()
            )
        else:
            suggestion["suggested_name"] = "fix_custom_pattern"

    # Suggest test cases based on common patterns
    if sample_text:
        suggestion["test_cases_needed"].append((sample_text, "Expected output needed"))

    # Common test cases for spacing issues
    if "-" in original_pattern:
        suggestion["test_cases_needed"].extend(
            [
                ("word - word", "word-word"),
                ("already-good", "already-good"),  # No change
                ("multiple - word - spacing", "multiple-word - spacing"),  # Partial fix
            ]
        )

    return suggestion


def print_migration_suggestion(suggestion: dict[str, any]) -> None:
    """Print a formatted migration suggestion report."""
    print("\n🔄 REGEX MIGRATION SUGGESTION")
    print("=" * 50)
    print(f"Original Pattern: {suggestion['original_pattern']}")
    print(f"Original Replacement: {suggestion['original_replacement']}")
    print()

    if suggestion["safety_issues"]:
        print("❌ SAFETY ISSUES:")
        for issue in suggestion["safety_issues"]:
            print(f"  • {issue}")
        print()

    if suggestion["existing_matches"]:
        print("✅ EXISTING PATTERNS AVAILABLE:")
        for pattern_name in suggestion["existing_matches"]:
            pattern = SAFE_PATTERNS[pattern_name]
            print(f"  • {pattern_name}: {pattern.description}")
        print("💡 Consider using existing patterns instead of creating new ones.")
        print()

    if suggestion["needs_new_pattern"]:
        print("🆕 NEW PATTERN NEEDED:")
        print(f"  Suggested Name: {suggestion['suggested_name']}")
        print("  Add to crackerjack/services/regex_patterns.py:")
        print()
        print("  ```python")
        print(f'  "{suggestion["suggested_name"]}": ValidatedPattern(')
        print(f'      name="{suggestion["suggested_name"]}",')
        print(f'      pattern=r"{suggestion["original_pattern"]}",')
        print(f'      replacement=r"{suggestion["original_replacement"]}",')
        print('      description="TODO: Add description",')
        print("      test_cases=[")
        for test_input, test_output in suggestion["test_cases_needed"]:
            print(f'          ("{test_input}", "{test_output}"),')
        print("      ]")
        print("  ),")
        print("  ```")
        print()

    print("🔧 MIGRATION STEPS:")
    print("  1. Fix any safety issues in replacement syntax")
    if suggestion["existing_matches"]:
        print("  2. Use existing safe patterns if possible:")
        for pattern_name in suggestion["existing_matches"]:
            print(f"     SAFE_PATTERNS['{pattern_name}'].apply(text)")
    if suggestion["needs_new_pattern"]:
        print("  3. Add new ValidatedPattern to regex_patterns.py")
        print("  4. Test thoroughly with comprehensive test cases")
    print("  5. Replace re.sub() call with safe pattern usage")
    print("  6. Run pre-commit hook to validate")

    print("=" * 50)


def audit_file_for_re_sub(file_path: Path) -> list[dict[str, any]]:
    """
    Audit a file for re.sub() calls and return migration suggestions.

    Returns list of findings with line numbers and suggestions.
    """
    findings = []

    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Look for re.sub() calls
            re_sub_match = re.search(
                r're\.sub\s*\(\s*[r]?["\']([^"\']+)["\'],\s*[r]?["\']([^"\']*)["\']',
                line,
            )
            if re_sub_match:
                pattern = re_sub_match.group(1)
                replacement = re_sub_match.group(2)

                finding = {
                    "file": str(file_path),
                    "line_number": i,
                    "line_content": line.strip(),
                    "pattern": pattern,
                    "replacement": replacement,
                    "suggestion": suggest_migration_for_re_sub(pattern, replacement),
                }
                findings.append(finding)

    except Exception as e:
        findings.append(
            {
                "file": str(file_path),
                "line_number": 0,
                "error": f"Failed to audit file: {e}",
            }
        )

    return findings


def audit_codebase_re_sub() -> dict[str, list[dict[str, any]]]:
    """
    Audit entire crackerjack codebase for re.sub() usage.

    Returns dictionary mapping file paths to findings.
    """
    findings_by_file = {}

    # Audit crackerjack package
    crackerjack_dir = Path(__file__).parent.parent

    for py_file in crackerjack_dir.rglob("*.py"):
        # Skip test files and __pycache__
        if "test_" in py_file.name or "__pycache__" in str(py_file):
            continue

        findings = audit_file_for_re_sub(py_file)
        if findings:
            findings_by_file[str(py_file)] = findings

    return findings_by_file


if __name__ == "__main__":
    # Example usage for testing patterns
    test_result = quick_pattern_test(
        pattern=r"(\w+)\s*-\s*(\w+)",
        replacement=r"\1-\2",
        test_cases=[
            ("python - pro", "python-pro"),
            ("already-good", "already-good"),
            ("test - case - multiple", "test-case - multiple"),
        ],
        description="Fix spacing in hyphenated names",
    )

    # Example migration suggestion
    print("\n" + "=" * 60)
    migration = suggest_migration_for_re_sub(
        r"python\s*-\s*m\s+", "python -m ", "python - m crackerjack"
    )
    print_migration_suggestion(migration)
