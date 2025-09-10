"""
Test suite for the validate_regex_patterns pre-commit hook tool.

This ensures the hook correctly identifies regex issues when crackerjack
is installed in other projects and verifies path resolution works properly.
"""

import tempfile
import textwrap
from pathlib import Path

from crackerjack.tools.validate_regex_patterns import main, validate_file


class TestValidateRegexPatternsTool:
    """Test the validate_regex_patterns tool functionality."""

    def test_detects_raw_regex_usage(self) -> None:
        """Test that the tool detects raw re.sub() usage."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                textwrap.dedent("""
                import re

                def bad_function():
                    text = "hello world"
                    result = re.sub(r"hello", "hi", text)
                    return result
            """)
            )
            f.flush()

            issues = validate_file(Path(f.name))
            assert len(issues) == 1
            line_no, message = issues[0]
            assert line_no == 6
            assert "Raw regex usage detected: re.sub()" in message
            assert (
                "Use validated patterns from crackerjack.services.regex_patterns"
                in message
            )

    def test_detects_multiple_regex_functions(self) -> None:
        """Test detection of multiple regex function calls."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                textwrap.dedent("""
                import re

                def multiple_bad_usage():
                    text = "hello 123 world"
                    result1 = re.sub(r"hello", "hi", text)
                    result2 = re.findall(r"\\d+", text)
                    result3 = re.search(r"world", text)
                    return result1, result2, result3
            """)
            )
            f.flush()

            issues = validate_file(Path(f.name))
            assert len(issues) == 3

            # Check each issue
            assert issues[0][0] == 6  # re.sub line
            assert "re.sub()" in issues[0][1]

            assert issues[1][0] == 7  # re.findall line
            assert "re.findall()" in issues[1][1]

            assert issues[2][0] == 8  # re.search line
            assert "re.search()" in issues[2][1]

    def test_detects_bad_replacement_syntax(self) -> None:
        """Test detection of forbidden replacement syntax with spaces."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                textwrap.dedent("""
                import re

                def bad_replacement():
                    text = "foo-bar"
                    # Bad syntax with spaces
                    result = re.sub(r"(\\w+)-(\\w+)", r"\\g<1>_\\g<2>", text)  # REGEX OK: test case
                    return result
            """)
            )
            f.flush()

            issues = validate_file(Path(f.name))
            assert len(issues) == 2  # One for bad syntax, one for raw usage

            # Find the critical syntax issue
            critical_issue = next(
                (issue for issue in issues if "CRITICAL" in issue[1]), None
            )
            assert critical_issue is not None
            assert "Bad replacement syntax detected" in critical_issue[1]
            assert "\\g<1>_\\g<2>" in critical_issue[1]  # REGEX OK: test assertion
            assert (
                "Use \\g<1> not \\g<1>" in critical_issue[1]
            )  # REGEX OK: test assertion

    def test_allows_exempted_files(self) -> None:
        """Test that whitelisted files are allowed to use regex."""
        # Test the regex_patterns.py file itself should be allowed
        test_content = textwrap.dedent("""
            import re

            def validate_pattern():
                # This should be allowed in regex_patterns.py
                result = re.sub(r"test", "validated", "test string")
                return result
        """)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create the proper directory structure
            file_path = (
                Path(temp_dir) / "crackerjack" / "services" / "regex_patterns.py"
            )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(test_content, encoding="utf-8")

            issues = validate_file(file_path)
            assert len(issues) == 0  # Should be allowed

    def test_allows_exemption_comments(self) -> None:
        """Test that # REGEX OK: comments exempt lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                textwrap.dedent("""
                import re

                def exempted_function():
                    text = "hello world"
                    result = re.sub(r"hello", "hi", text)  # REGEX OK: legitimate use case
                    return result
            """)
            )
            f.flush()

            issues = validate_file(Path(f.name))
            assert len(issues) == 0  # Should be exempted by comment

    def test_handles_syntax_errors_gracefully(self) -> None:
        """Test that syntax errors are handled gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import re\n\ndef bad_syntax(\n  # Missing closing parenthesis")
            f.flush()

            issues = validate_file(Path(f.name))
            assert len(issues) == 1
            assert "Syntax error" in issues[0][1]

    def test_handles_file_read_errors(self) -> None:
        """Test that file read errors are handled gracefully."""
        # Test with non-existent file
        fake_path = Path("/nonexistent/file.py")
        issues = validate_file(fake_path)
        assert len(issues) == 1
        assert "Error reading file" in issues[0][1]

    def test_main_function_with_multiple_files(self) -> None:
        """Test the main function with multiple files."""
        # Create good file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as good_file:
            good_file.write("def clean_function():\n    return 'no regex here'")
            good_file.flush()

        # Create bad file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as bad_file:
            bad_file.write("import re\ndef bad():\n    return re.sub('a', 'b', 'abc')")
            bad_file.flush()

        # Test main function
        exit_code = main([good_file.name, bad_file.name])
        assert exit_code == 1  # Should fail due to bad file

    def test_main_function_all_clean(self) -> None:
        """Test main function with all clean files returns 0."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def clean_function():\n    return 'no regex here'")
            f.flush()

        exit_code = main([f.name])
        assert exit_code == 0

    def test_skips_non_python_files(self) -> None:
        """Test that non-Python files are skipped."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("import re\nre.sub('bad', 'stuff', 'here')")
            f.flush()

        exit_code = main([f.name])
        assert exit_code == 0  # Should skip and return success

    def test_skips_nonexistent_files(self) -> None:
        """Test that nonexistent files are skipped gracefully."""
        exit_code = main(["/nonexistent/file.py"])
        assert exit_code == 0  # Should skip and return success

    def test_validates_regex_import_detection(self) -> None:
        """Test that the tool properly detects regex module imports."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                textwrap.dedent("""
                import re

                def uses_regex_module():
                    # This will be detected as re.sub
                    result = re.sub(r"test", "replacement", "test string")
                    return result
            """)
            )
            f.flush()

            issues = validate_file(Path(f.name))
            assert len(issues) >= 1
            # Should detect re.sub() usage

    def test_integration_with_external_project_paths(self) -> None:
        """Test that the tool works correctly when installed in external projects."""
        # This simulates the scenario where crackerjack is installed
        # in another project and the hook runs from that project's directory

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a fake external project structure
            project_dir = Path(temp_dir) / "external_project"
            project_dir.mkdir()

            # Create a Python file with regex issues in the external project
            test_file = project_dir / "external_module.py"
            test_file.write_text(
                textwrap.dedent("""
                import re

                def external_function():
                    # This should be caught by validate_regex_patterns
                    result = re.sub(r"pattern", "replacement", "text")
                    return result
            """),
                encoding="utf-8",
            )

            # Run validation from external project directory
            issues = validate_file(test_file)
            assert len(issues) == 1
            assert "Raw regex usage detected" in issues[0][1]

            # Verify the tool correctly identifies the file path
            assert issues[0][0] == 6  # Line number should be correct


class TestValidateRegexPatternsModuleResolution:
    """Test that the tool can be imported correctly from external projects."""

    def test_tool_module_import(self) -> None:
        """Test that the validate_regex_patterns tool can be imported."""
        from crackerjack.tools.validate_regex_patterns import main, validate_file

        # Verify functions are callable
        assert callable(main)
        assert callable(validate_file)

    def test_tool_can_run_via_module_syntax(self) -> None:
        """Test that 'python -m crackerjack.tools.validate_regex_patterns' works."""
        import subprocess
        import tempfile

        # Create a clean test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def clean_function():\n    return 'no regex here'")
            f.flush()

            # Run via module syntax (as used in pre-commit hook)
            result = subprocess.run(
                ["python", "-m", "crackerjack.tools.validate_regex_patterns", f.name],
                cwd="/tmp",
                capture_output=True,
                text=True,
            )

            # Should complete successfully with clean file
            assert result.returncode == 0
            assert "All regex patterns validated successfully!" in result.stdout
