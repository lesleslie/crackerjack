"""Tests for docstring_extractor module."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.mark.unit
class TestExtractFunctionMarkdown:
    def test_returns_markdown_for_function_with_docstring(self) -> None:
        """Function with a docstring produces markdown output."""

        def example(x: int) -> int:
            """Example function summary.

            Args:
                x: An integer.

            Returns:
                The value unchanged.
            """
            return x

        from crackerjack.documentation.docstring_extractor import (
            extract_function_markdown,
        )

        result = extract_function_markdown(example)
        assert "Example function summary." in result
        assert "Args" in result
        assert "Returns" in result

    def test_returns_placeholder_when_no_docstring(self) -> None:
        """Function with no docstring returns the no-doc placeholder."""

        def undocumented() -> None:
            pass

        from crackerjack.documentation.docstring_extractor import (
            extract_function_markdown,
        )

        result = extract_function_markdown(undocumented)
        assert result == "**No documentation available**"

    def test_renders_code_block_in_docstring(self) -> None:
        """Backticks in docstring are preserved in markdown output."""

        def example() -> None:
            """Run a command.

            Examples:
                ```python
                example()
                ```
            """

        from crackerjack.documentation.docstring_extractor import (
            extract_function_markdown,
        )

        result = extract_function_markdown(example)
        assert "```python" in result

    def test_handles_short_summary_only(self) -> None:
        """Single-line docstring is converted faithfully."""

        def example() -> None:
            """Just a summary."""

        from crackerjack.documentation.docstring_extractor import (
            extract_function_markdown,
        )

        result = extract_function_markdown(example)
        assert "Just a summary." in result


@pytest.mark.unit
class TestExtractClassMarkdown:
    def test_returns_dict_keyed_by_method_name(self) -> None:
        """Public methods become keys in the returned dict."""

        class Sample:
            def alpha(self) -> str:
                """Alpha method."""
                return "a"

            def beta(self) -> str:
                """Beta method."""
                return "b"

        from crackerjack.documentation.docstring_extractor import extract_class_markdown

        result = extract_class_markdown(Sample)
        assert "alpha" in result
        assert "beta" in result
        assert "Alpha method." in result["alpha"]
        assert "Beta method." in result["beta"]

    def test_skips_private_methods(self) -> None:
        """Methods starting with underscore are not in the returned dict."""

        class Sample:
            def public(self) -> str:
                """Public."""
                return "p"

            def _private(self) -> str:
                """Private."""
                return "x"

            def __dunder__(self) -> str:
                """Dunder."""
                return "d"

        from crackerjack.documentation.docstring_extractor import extract_class_markdown

        result = extract_class_markdown(Sample)
        assert "public" in result
        assert "_private" not in result
        assert "__dunder__" not in result

    def test_includes_method_without_docstring_as_placeholder(self) -> None:
        """Public method without docstring gets the no-doc placeholder."""

        class Sample:
            def nodoc(self) -> None:
                pass

        from crackerjack.documentation.docstring_extractor import extract_class_markdown

        result = extract_class_markdown(Sample)
        assert "nodoc" in result
        assert result["nodoc"] == "**No documentation available**"

    def test_handles_class_with_no_public_methods(self) -> None:
        """Class with only private methods returns an empty dict."""

        class Sample:
            def _only_private(self) -> None:
                pass

            def __init__(self) -> None:
                pass

        from crackerjack.documentation.docstring_extractor import extract_class_markdown

        result = extract_class_markdown(Sample)
        assert result == {}

    def test_handles_empty_class(self) -> None:
        """Class without any methods returns an empty dict."""

        class Empty:
            pass

        from crackerjack.documentation.docstring_extractor import extract_class_markdown

        result = extract_class_markdown(Empty)
        assert result == {}


@pytest.mark.unit
class TestExtractModuleMarkdown:
    def test_returns_dict_for_real_python_file(self, tmp_path: Path) -> None:
        """Module-level function and class docstrings are captured."""
        source = textwrap.dedent("""\
            def top_level(x: int) -> int:
                \"\"\"Top level function.

                Args:
                    x: Input.

                Returns:
                    Same value.
                \"\"\"
                return x


            class Thing:
                \"\"\"A thing class.\"\"\"

                def act(self) -> str:
                    \"\"\"Do the thing.\"\"\"
                    return "ok"

                def _hidden(self) -> None:
                    \"\"\"Hidden.\"\"\"
                    pass
        """)
        py_file = tmp_path / "module.py"
        py_file.write_text(source)

        from crackerjack.documentation.docstring_extractor import (
            extract_module_markdown,
        )

        result = extract_module_markdown(py_file)

        assert "top_level" in result
        assert "Top level function." in result["top_level"]
        assert "Thing" in result
        assert "A thing class." in result["Thing"]
        assert "Thing.act" in result
        assert "Do the thing." in result["Thing.act"]
        assert "Thing._hidden" not in result

    def test_skips_module_level_imports_and_statements(self, tmp_path: Path) -> None:
        """Imports and assignments do not become entries in the docs dict."""
        source = textwrap.dedent("""\
            import os
            from pathlib import Path

            CONSTANT = 42
            NAMES = ["a", "b"]


            def documented() -> None:
                \"\"\"A documented function.\"\"\"
        """)
        py_file = tmp_path / "module.py"
        py_file.write_text(source)

        from crackerjack.documentation.docstring_extractor import (
            extract_module_markdown,
        )

        result = extract_module_markdown(py_file)

        assert "os" not in result
        assert "Path" not in result
        assert "CONSTANT" not in result
        assert "NAMES" not in result
        assert "documented" in result
        assert len(result) == 1

    def test_returns_error_key_on_syntax_error(self, tmp_path: Path) -> None:
        """Invalid Python produces a dict with a single 'error' key."""
        py_file = tmp_path / "broken.py"
        py_file.write_text("def broken(:\n    pass\n")

        from crackerjack.documentation.docstring_extractor import (
            extract_module_markdown,
        )

        result = extract_module_markdown(py_file)

        assert "error" in result
        assert "Syntax error" in result["error"]
        assert "broken.py" in result["error"]

    def test_skips_private_module_level_functions(self, tmp_path: Path) -> None:
        """Module-level functions starting with _ are skipped."""
        source = textwrap.dedent("""\
            def public_func() -> None:
                \"\"\"Public.\"\"\"


            def _private_func() -> None:
                \"\"\"Private.\"\"\"
        """)
        py_file = tmp_path / "module.py"
        py_file.write_text(source)

        from crackerjack.documentation.docstring_extractor import (
            extract_module_markdown,
        )

        result = extract_module_markdown(py_file)

        assert "public_func" in result
        assert "_private_func" not in result

    def test_handles_module_with_only_imports(self, tmp_path: Path) -> None:
        """A module with only imports yields an empty dict."""
        py_file = tmp_path / "imports_only.py"
        py_file.write_text("import os\nfrom pathlib import Path\n")

        from crackerjack.documentation.docstring_extractor import (
            extract_module_markdown,
        )

        result = extract_module_markdown(py_file)

        assert result == {}

    def test_handles_class_without_docstring(self, tmp_path: Path) -> None:
        """Class without a docstring is skipped (only methods with docs kept)."""
        source = textwrap.dedent("""\
            class NoDoc:
                def method(self) -> None:
                    \"\"\"A method.\"\"\"
        """)
        py_file = tmp_path / "module.py"
        py_file.write_text(source)

        from crackerjack.documentation.docstring_extractor import (
            extract_module_markdown,
        )

        result = extract_module_markdown(py_file)

        assert "NoDoc" not in result
        assert "NoDoc.method" in result


@pytest.mark.unit
class TestExtractForZensical:
    def test_returns_combined_markdown_when_symbol_name_is_none(
        self, tmp_path: Path
    ) -> None:
        """Without a symbol, all entries are joined with ## headings."""
        source = textwrap.dedent("""\
            def alpha() -> None:
                \"\"\"Alpha doc.\"\"\"


            def beta() -> None:
                \"\"\"Beta doc.\"\"\"
        """)
        py_file = tmp_path / "module.py"
        py_file.write_text(source)

        from crackerjack.documentation.docstring_extractor import extract_for_zensical

        result = extract_for_zensical(py_file)

        assert "## alpha" in result
        assert "## beta" in result
        assert "Alpha doc." in result
        assert "Beta doc." in result

    def test_returns_single_symbol_when_present(self, tmp_path: Path) -> None:
        """When symbol_name is provided and exists, only that entry is returned."""
        source = textwrap.dedent("""\
            def alpha() -> None:
                \"\"\"Alpha doc.\"\"\"


            def beta() -> None:
                \"\"\"Beta doc.\"\"\"
        """)
        py_file = tmp_path / "module.py"
        py_file.write_text(source)

        from crackerjack.documentation.docstring_extractor import extract_for_zensical

        result = extract_for_zensical(py_file, symbol_name="alpha")

        assert "Alpha doc." in result
        assert "Beta doc." not in result
        assert "## beta" not in result

    def test_returns_not_found_message_for_unknown_symbol(self, tmp_path: Path) -> None:
        """Unknown symbol_name yields a 'No documentation found' message."""
        source = textwrap.dedent("""\
            def alpha() -> None:
                \"\"\"Alpha doc.\"\"\"
        """)
        py_file = tmp_path / "module.py"
        py_file.write_text(source)

        from crackerjack.documentation.docstring_extractor import extract_for_zensical

        result = extract_for_zensical(py_file, symbol_name="missing")

        assert "missing" in result
        assert "No documentation found" in result

    def test_propagates_syntax_error_message(self, tmp_path: Path) -> None:
        """Syntax errors propagate as an error key in the joined output."""
        py_file = tmp_path / "broken.py"
        py_file.write_text("def broken(:\n    pass\n")

        from crackerjack.documentation.docstring_extractor import extract_for_zensical

        result = extract_for_zensical(py_file)

        assert "Syntax error" in result
        assert "broken.py" in result


@pytest.mark.unit
class TestValidateDocstringQuality:
    def test_detects_bold_text(self) -> None:
        """No 'Missing bold marker' violation when ** appears in the docstring."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality("Some **bold** statement with code:\n\n```python\nx = 1\n```\n")

        assert "Missing bold marker (**)" not in result["violations"]

    def test_detects_missing_bold(self) -> None:
        """Plain prose without ** triggers the bold violation."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality("A plain summary.")

        assert "Missing bold marker (**)" in result["violations"]

    def test_detects_code_blocks(self) -> None:
        """A fenced code block suppresses the code-block violation."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality(
            "**Bold summary.**\n\nExample:\n\n```python\nfoo()\n```\n",
        )

        assert "Missing fenced code block (```)" not in result["violations"]

    def test_detects_example_marker_without_code(self) -> None:
        """The 'Example:' marker satisfies the example check without a code block."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality("**Summary.**\n\nExample: foo bar baz")

        assert (
            "Missing example section (need ``` or 'Example:')"
            not in result["violations"]
        )

    def test_detects_excessive_blanks(self) -> None:
        """Four-or-more consecutive newlines trigger the blank violation."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality(
            "**Bold.**\n\n```python\nfoo()\n```\n\n\n\nMore text.",
        )

        assert "Excessive blank lines (4+ consecutive)" in result["violations"]

    def test_normal_spacing_has_no_blanks_violation(self) -> None:
        """Normal double newlines do NOT trigger the blank violation."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality(
            "**Bold.**\n\n```python\nfoo()\n```\n\nMore text.",
        )

        assert (
            "Excessive blank lines (4+ consecutive)" not in result["violations"]
        )

    def test_empty_docstring_returns_all_violations(self) -> None:
        """An empty string yields every violation."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality("")

        assert "Missing bold marker (**)" in result["violations"]
        assert "Missing fenced code block (```)" in result["violations"]
        assert (
            "Missing example section (need ``` or 'Example:')"
            in result["violations"]
        )

    def test_non_docstring_plain_text(self) -> None:
        """Plain prose with no markers yields bold + code + example violations."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality("A plain prose paragraph with no markers.")

        assert "Missing bold marker (**)" in result["violations"]
        assert "Missing fenced code block (```)" in result["violations"]

    def test_returns_dict_with_expected_keys(self) -> None:
        """Result has exactly one key: 'violations' → list[str]."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality("Anything.")

        assert set(result.keys()) == {"violations"}
        assert isinstance(result["violations"], list)
        assert all(isinstance(v, str) for v in result["violations"])

    def test_complete_docstring_has_no_violations(self) -> None:
        """A docstring with all quality markers returns an empty violations list."""
        from crackerjack.documentation.docstring_extractor import (
            validate_docstring_quality,
        )

        result = validate_docstring_quality(
            "**Summary of the function.**\n\n"
            "Longer description here.\n\n"
            "Example:\n\n"
            "```python\nresult = foo()\n```\n",
        )

        assert result["violations"] == []
