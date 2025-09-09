"""
Test syntax validation to prevent code cleaner from breaking Python syntax.

This module tests for common syntax issues that automated formatters
or code cleaners might introduce, particularly walrus operators (:=)
and other Python 3.8+ syntax that can be broken by spacing changes.
"""

import ast
from pathlib import Path

import pytest

from crackerjack.services.filesystem import FileSystemService


class TestWalrusOperatorSyntax:
    """Test that walrus operators (:=) are properly formatted."""

    def test_walrus_operators_have_no_spaces(self) -> None:
        """Test that all walrus operators in codebase use := not : ="""
        project_root = Path(__file__).parent.parent
        crackerjack_dir = project_root / "crackerjack"

        # Find all Python files using walrus operators
        python_files = list(crackerjack_dir.rglob("*.py"))
        files_with_walrus = []
        malformed_walrus_instances = []

        for py_file in python_files:
            try:
                content = py_file.read_text(encoding="utf-8")

                # Check for walrus operators
                if ":=" in content:
                    files_with_walrus.append(py_file)

                # Check for malformed walrus operators (: =)
                if ": =" in content:
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if ": =" in line:
                            malformed_walrus_instances.append(
                                (py_file, i, line.strip())
                            )

            except UnicodeDecodeError:
                # Skip binary files
                continue

        # Report malformed walrus operators
        if malformed_walrus_instances:
            error_msg = "Found malformed walrus operators (': =' instead of ':='):\n"
            for file_path, line_num, line_content in malformed_walrus_instances:
                rel_path = file_path.relative_to(project_root)
                error_msg += f"  {rel_path}:{line_num}: {line_content}\n"
            pytest.fail(error_msg)

        # Ensure we actually found some walrus operators to test
        assert len(files_with_walrus) > 0, "No walrus operators found in codebase"

    def test_all_python_files_parse_successfully(self) -> None:
        """Test that all Python files in crackerjack can be parsed by AST."""
        project_root = Path(__file__).parent.parent
        crackerjack_dir = project_root / "crackerjack"

        python_files = list(crackerjack_dir.rglob("*.py"))
        syntax_errors = []

        for py_file in python_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                # Try to parse with AST - this will catch syntax errors
                ast.parse(content, filename=str(py_file))
            except SyntaxError as e:
                rel_path = py_file.relative_to(project_root)
                syntax_errors.append(f"{rel_path}:{e.lineno}: {e.msg}")
            except UnicodeDecodeError:
                # Skip binary files
                continue

        if syntax_errors:
            error_msg = "Found Python syntax errors:\n" + "\n".join(syntax_errors)
            pytest.fail(error_msg)

    def test_specific_walrus_operator_patterns(self) -> None:
        """Test specific walrus operator patterns that were previously broken."""
        # These are patterns that were found to be broken by the code cleaner
        test_cases = [
            # From coverage_ratchet.py
            "if (next_milestone := self._get_next_milestone(new_coverage))",
            "points_to_next = (next_milestone - new_coverage) if (next_milestone := self._get_next_milestone(new_coverage)) else 0",
            # General patterns that should work
            "if (value := some_function()) is not None:",
            "while (line := file.readline()):",
            "data = [(x, y) for x in range(10) if (y := x * 2) > 5]",
            "[y for x in items if (y := process(x)) is not None]",
        ]

        for code in test_cases:
            try:
                # This should parse successfully if walrus operator is properly formatted
                ast.parse(code)
            except SyntaxError as e:
                pytest.fail(f"Walrus operator syntax error in: {code}\nError: {e.msg}")

    def test_malformed_walrus_operator_detection(self) -> None:
        """Test that we can detect malformed walrus operators."""
        # These should all fail to parse
        malformed_cases = [
            "if (value : = some_function()) is not None:",  # Space before =
            "if (value: = some_function()) is not None:",  # Space after :
            "if (value : = some_function()) is not None:",  # Spaces on both sides
        ]

        for code in malformed_cases:
            with pytest.raises(SyntaxError):
                ast.parse(code)


class TestPythonSyntaxIntegrity:
    """Test various Python syntax patterns that could be broken by formatters."""

    def test_no_malformed_regex_quantifiers(self) -> None:
        """Test that regex patterns don't have spaces in quantifiers like {n, m}."""
        project_root = Path(__file__).parent.parent

        # Check the regex_patterns file specifically since it had these issues
        regex_patterns_file = (
            project_root / "crackerjack" / "services" / "regex_patterns.py"
        )

        if regex_patterns_file.exists():
            content = regex_patterns_file.read_text(encoding="utf-8")

            # Look for common malformed quantifier patterns
            malformed_patterns = [
                r"{\d+, }",  # {n, } instead of {n,}
                r"{ \d+,}",  # { n,} instead of {n,}
                r"{\d+, \d+}",  # {n, m} instead of {n,m}
            ]

            import re

            issues = []
            lines = content.split("\n")

            for pattern in malformed_patterns:
                for i, line in enumerate(lines, 1):
                    matches = re.findall(pattern, line)
                    if matches:
                        issues.append(f"Line {i}: {line.strip()}")

            if issues:
                error_msg = f"Found malformed regex quantifiers in {regex_patterns_file.name}:\n"
                error_msg += "\n".join(issues)
                pytest.fail(error_msg)

    def test_no_malformed_regex_character_classes(self) -> None:
        """Test that regex character classes don't have extra spaces."""
        project_root = Path(__file__).parent.parent
        regex_patterns_file = (
            project_root / "crackerjack" / "services" / "regex_patterns.py"
        )

        if regex_patterns_file.exists():
            content = regex_patterns_file.read_text(encoding="utf-8")

            # Look for malformed character class patterns
            import re

            issues = []
            lines = content.split("\n")

            # Pattern for character classes with spaces: [^, ] instead of [^,]
            malformed_char_class_pattern = r"\[\^[^]]*,\s+[^]]*\]"

            for i, line in enumerate(lines, 1):
                if re.search(malformed_char_class_pattern, line):
                    issues.append(f"Line {i}: {line.strip()}")

            if issues:
                error_msg = f"Found malformed regex character classes in {regex_patterns_file.name}:\n"
                error_msg += "\n".join(issues)
                pytest.fail(error_msg)

    def test_no_extra_spaces_in_string_formatting(self) -> None:
        """Test that string formatting doesn't have unwanted extra spaces."""
        project_root = Path(__file__).parent.parent
        crackerjack_dir = project_root / "crackerjack"

        python_files = list(crackerjack_dir.rglob("*.py"))
        issues = []

        for py_file in python_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    # Check for common f-string formatting issues
                    if ": ." in line and 'f"' in line:
                        # This might be a malformed f-string like f"{value: .2f}" instead of f"{value:.2f}"
                        issues.append(
                            f"{py_file.relative_to(project_root)}:{i}: {line.strip()}"
                        )

            except UnicodeDecodeError:
                continue

        # Don't fail for this one, just warn, as some spacing in f-strings might be intentional
        if issues:
            print(
                "Warning: Found potential malformed f-string formatting:\n"
                + "\n".join(issues)
            )

    def test_filesystem_service_integration(self) -> None:
        """Test that FileSystemService can handle files with walrus operators."""
        # Create a test file with walrus operators
        test_content = """
def test_function():
    if (value := get_value()) is not None:
        return value
    return None

def another_test():
    data = [x for x in items if (processed := process(x)) is not None]
    return data
"""

        # Use FileSystemService to validate the content would be handled correctly
        fs_service = FileSystemService()

        # This should not raise any exceptions
        cleaned_content = fs_service.clean_trailing_whitespace_and_newlines(
            test_content
        )

        # The walrus operators should remain intact
        assert ":=" in cleaned_content
        assert ": =" not in cleaned_content

        # Should still be valid Python
        try:
            ast.parse(cleaned_content)
        except SyntaxError as e:
            pytest.fail(f"FileSystemService corrupted walrus operator syntax: {e}")


class TestCodeCleanerSafety:
    """Test that code cleaning operations don't break syntax."""

    def test_validate_all_crackerjack_files_after_cleaning(self) -> None:
        """Integration test: ensure all files remain syntactically valid after potential cleaning."""
        project_root = Path(__file__).parent.parent
        crackerjack_dir = project_root / "crackerjack"

        python_files = list(crackerjack_dir.rglob("*.py"))

        # Track files that should have walrus operators
        files_with_walrus = []

        for py_file in python_files:
            try:
                content = py_file.read_text(encoding="utf-8")

                # First, ensure the file parses correctly as-is
                try:
                    ast.parse(content, filename=str(py_file))
                except SyntaxError as e:
                    rel_path = py_file.relative_to(project_root)
                    pytest.fail(f"Syntax error in {rel_path}:{e.lineno}: {e.msg}")

                # Track files with walrus operators
                if ":=" in content:
                    files_with_walrus.append(py_file)

                    # Ensure no malformed walrus operators
                    if ": =" in content:
                        rel_path = py_file.relative_to(project_root)
                        pytest.fail(f"Malformed walrus operator in {rel_path}")

            except UnicodeDecodeError:
                continue

        # Ensure we're actually testing files with walrus operators
        assert len(files_with_walrus) > 0, (
            "No files with walrus operators found for validation"
        )

        print(
            f"Successfully validated {len(files_with_walrus)} files containing walrus operators"
        )
