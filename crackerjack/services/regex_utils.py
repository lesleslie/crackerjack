import re
import typing as t
from pathlib import Path

from crackerjack.services.regex_patterns import SAFE_PATTERNS, CompiledPatternCache


def test_pattern_immediately(
    pattern: str,
    replacement: str,
    test_cases: list[tuple[str, str]],
    description: str = "",
) -> dict[str, t.Any]:
    results: dict[str, t.Any] = {
        "pattern": pattern,
        "replacement": replacement,
        "description": description,
        "all_passed": True,
        "test_results": [],
        "warnings": [],
        "errors": [],
    }

    try:
        compiled = CompiledPatternCache.get_compiled_pattern(pattern)
    except ValueError as e:
        results["errors"].append(f"Invalid regex pattern: {e}")
        results["all_passed"] = False
        return results

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
                },
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
                },
            )
            results["all_passed"] = False

    if ".*.*" in pattern:
        results["warnings"].append(
            "Multiple .* constructs may cause performance issues",
        )
    if ".+.+" in pattern:
        results["warnings"].append(
            "Multiple .+ constructs may cause performance issues",
        )

    return results


def print_pattern_test_report(results: dict[str, t.Any]) -> None:
    if results["description"]:
        pass

    if results["errors"]:
        for _error in results["errors"]:
            pass

    if results["warnings"]:
        for _warning in results["warnings"]:
            pass

    for test in results["test_results"]:
        "✅ PASS" if test["passed"] else "❌ FAIL"
        if not test["passed"]:
            pass


def quick_pattern_test(
    pattern: str,
    replacement: str,
    test_cases: list[tuple[str, str]],
    description: str = "",
) -> bool:
    results = test_pattern_immediately(pattern, replacement, test_cases, description)
    print_pattern_test_report(results)
    passed: bool = results["all_passed"]
    return passed


def find_safe_pattern_for_text(text: str) -> list[str]:
    matches = []
    for name, pattern in SAFE_PATTERNS.items():
        try:
            if pattern.test(text):
                matches.append(name)
        except Exception:
            continue
    return matches


def _determine_suggested_name(original_pattern: str) -> str:
    if "python.*-.*m" in original_pattern:
        return "fix_python_command_spacing"
    if r"\-\s*\-" in original_pattern:
        return "fix_double_dash_spacing"
    if "token" in original_pattern.lower():
        return "fix_token_pattern"
    if "password" in original_pattern.lower():
        return "fix_password_pattern"

    keyword_pattern = CompiledPatternCache.get_compiled_pattern(r"[a-zA-Z]+")
    keywords = keyword_pattern.findall(original_pattern)
    if keywords:
        return f"fix_{'_'.join(keywords[:3])}_pattern".lower()

    return "fix_custom_pattern"


def _build_test_cases(original_pattern: str, sample_text: str) -> list[tuple[str, str]]:
    test_cases = []

    if sample_text:
        test_cases.append((sample_text, "Expected output needed"))

    if "-" in original_pattern:
        test_cases.extend(
            [
                ("word - word", "word-word"),
                ("already-good", "already-good"),
                ("multiple - word - spacing", "multiple-word - spacing"),
            ],
        )

    return test_cases


def suggest_migration_for_re_sub(
    original_pattern: str,
    original_replacement: str,
    sample_text: str = "",
) -> dict[str, t.Any]:
    suggestion: dict[str, t.Any] = {
        "original_pattern": original_pattern,
        "original_replacement": original_replacement,
        "existing_matches": [],
        "needs_new_pattern": True,
        "safety_issues": [],
        "suggested_name": "",
        "test_cases_needed": [],
    }

    forbidden_checks = [
        (r"\\g\s*<\s*\d+\s*>", "\\g<1> with spaces"),
        (r"\\g<\s+\d+>", "\\g<1> with space after <"),
        (r"\\\\g<\\d+\\s+>", "\\\\g<1 > with space before >"),
    ]
    for forbidden_pattern, _ in forbidden_checks:
        compiled = CompiledPatternCache.get_compiled_pattern(forbidden_pattern)
        if compiled.search(original_replacement):
            suggestion["safety_issues"].append(
                "CRITICAL: Bad replacement syntax - spaces in \\g<1>",
            )

    if sample_text:
        matches = find_safe_pattern_for_text(sample_text)
        suggestion["existing_matches"] = matches
        if matches:
            suggestion["needs_new_pattern"] = False

    suggestion["suggested_name"] = _determine_suggested_name(original_pattern)
    suggestion["test_cases_needed"] = _build_test_cases(original_pattern, sample_text)

    return suggestion


def print_migration_suggestion(suggestion: dict[str, t.Any]) -> None:
    if suggestion["safety_issues"]:
        for _issue in suggestion["safety_issues"]:
            pass

    if suggestion["existing_matches"]:
        for pattern_name in suggestion["existing_matches"]:
            SAFE_PATTERNS[pattern_name]

    if suggestion["needs_new_pattern"]:
        for _test_input, _test_output in suggestion["test_cases_needed"]:
            pass

    if suggestion["existing_matches"]:
        for pattern_name in suggestion["existing_matches"]:
            pass
    if suggestion["needs_new_pattern"]:
        pass


def audit_file_for_re_sub(file_path: Path) -> list[dict[str, t.Any]]:
    findings = []

    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            re_sub_pattern = CompiledPatternCache.get_compiled_pattern(
                r're\.sub\s*\(\s*[r]?["\']([^"\']+)["\'], \s*[r]?["\']([^"\']*)["\']',
            )
            re_sub_match = re_sub_pattern.search(line)
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
            },
        )

    return findings


def audit_codebase_re_sub() -> dict[str, list[dict[str, t.Any]]]:
    findings_by_file = {}

    crackerjack_dir = Path(__file__).parent.parent

    for py_file in crackerjack_dir.rglob("*.py"):
        if "test_" in py_file.name or "__pycache__" in str(py_file):
            continue

        findings = audit_file_for_re_sub(py_file)
        if findings:
            findings_by_file[str(py_file)] = findings

    return findings_by_file


def replace_unsafe_regex_with_safe_patterns(content: str) -> str:
    lines = content.split("\n")
    modified = False

    has_safe_patterns_import = _check_for_safe_patterns_import(lines)

    for i, line in enumerate(lines):
        original_line = line

        line = _fix_replacement_syntax_issues(line)

        line, _, needs_import = _process_re_sub_patterns(line, has_safe_patterns_import)

        if needs_import and not has_safe_patterns_import:
            import_index = _find_import_insertion_point(lines)
            lines.insert(
                import_index,
                "from crackerjack.services.regex_patterns import SAFE_PATTERNS",
            )
            has_safe_patterns_import = True
            i += 1

        if line != original_line:
            lines[i] = line
            modified = True

    return "\n".join(lines) if modified else content


def _check_for_safe_patterns_import(lines: list[str]) -> bool:
    return any(
        "from crackerjack.services.regex_patterns import SAFE_PATTERNS" in line
        or "SAFE_PATTERNS" in line
        for line in lines
    )


def _fix_replacement_syntax_issues(line: str) -> str:
    if r"\g < " in line or r"\g< " in line or r"\g <" in line:
        spacing_fix_pattern = CompiledPatternCache.get_compiled_pattern(
            r"\\g\s*<\s*(\d+)\s*>",
        )
        line = spacing_fix_pattern.sub(r"\\g<\1>", line)
    return line


def _process_re_sub_patterns(
    line: str,
    has_safe_patterns_import: bool,
) -> tuple[str, bool, bool]:
    re_sub_match = CompiledPatternCache.get_compiled_pattern(
        r're\.sub\s*\(\s*r?["\']([^"\']+)["\']\s*, \s*r?["\']([^"\']*)["\']',
    ).search(line)

    if not re_sub_match:
        return line, False, False

    pattern = re_sub_match.group(1)
    replacement = re_sub_match.group(2)

    safe_pattern_name = _identify_safe_pattern(pattern, replacement)
    if not safe_pattern_name:
        return line, False, False

    return _replace_with_safe_pattern(line, re_sub_match, safe_pattern_name)


def _identify_safe_pattern(pattern: str, replacement: str) -> str | None:
    if pattern == r"(\w+)\s*-\s*(\w+)" and replacement in (
        r"\1-\2",
        r"\g<1>-\g<2>",
    ):
        return "fix_hyphenated_names"
    if "token" in pattern.lower() and "*" in replacement:
        return "mask_tokens"
    if r"python\s*-\s*m" in pattern:
        return "fix_python_command_spacing"
    return None


def _replace_with_safe_pattern(
    line: str,
    re_sub_match: re.Match[str],
    safe_pattern_name: str,
) -> tuple[str, bool, bool]:
    before_re_sub = line[: re_sub_match.start()]
    after_re_sub = line[re_sub_match.end() :]

    assign_match = CompiledPatternCache.get_compiled_pattern(r"(\w+)\s*=\s*$").search(
        before_re_sub,
    )

    if assign_match:
        return _handle_assignment_pattern(
            line,
            assign_match,
            before_re_sub,
            after_re_sub,
            safe_pattern_name,
        )
    return _handle_direct_replacement(line, re_sub_match, safe_pattern_name)


def _handle_assignment_pattern(
    line: str,
    assign_match: re.Match[str],
    before_re_sub: str,
    after_re_sub: str,
    safe_pattern_name: str,
) -> tuple[str, bool, bool]:
    var_name = assign_match.group(1)
    text_var = _extract_source_variable(line)
    new_line = f"{var_name} = SAFE_PATTERNS['{safe_pattern_name}'].apply({text_var})"
    return before_re_sub + new_line + after_re_sub, True, True


def _handle_direct_replacement(
    line: str,
    re_sub_match: re.Match[str],
    safe_pattern_name: str,
) -> tuple[str, bool, bool]:
    text_var = _extract_source_variable(line)
    new_line = line.replace(
        re_sub_match.group(0),
        f"SAFE_PATTERNS['{safe_pattern_name}'].apply({text_var})",
    )
    return new_line, True, True


def _extract_source_variable(line: str) -> str:
    full_match = CompiledPatternCache.get_compiled_pattern(
        r"re\.sub\s*\([^, ]+, \s*[^, ]+, \s*(\w+)",
    ).search(line)
    return full_match.group(1) if full_match else "text"


def _find_import_insertion_point(lines: list[str]) -> int:
    import_index = 0
    for j, check_line in enumerate(lines):
        if check_line.strip().startswith(("import ", "from ")):
            import_index = j + 1
        elif check_line.strip() == "":
            continue
        else:
            break
    return import_index


if __name__ == "__main__":
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

    migration = suggest_migration_for_re_sub(
        r"python\s*-\s*m\s+",
        "python -m ",
        "python - m crackerjack",
    )
    print_migration_suggestion(migration)
