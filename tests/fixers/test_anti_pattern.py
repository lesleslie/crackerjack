"""Tests for crackerjack.fixers.anti_pattern.

No pre-existing dedicated test file exists for
``crackerjack.agents.anti_pattern_agent.AntiPatternAgent`` (confirmed via
``find tests -iname "*anti_pattern*agent*"`` -- no results; the only test
hits for "anti_pattern" anywhere in ``tests/`` are a single mocked call to
``identify_anti_patterns`` in ``tests/unit/agents/test_analysis_coordinator.py``,
which exercises coordinator dispatch, not real detection logic, and
``tests/unit/services/test_pattern_detector.py``, which tests an unrelated
``crackerjack.services.pattern_detector`` module). These tests are therefore
newly written directly against the ported module, exercising real detection
behavior on real code strings rather than mocks -- including five
pre-existing behavioral quirks/bugs preserved verbatim from the original
``AntiPatternAgent`` (see the module docstring of
``crackerjack/fixers/anti_pattern.py`` for the full rationale), each pinned
by an explicit test below.
"""

from __future__ import annotations

import asyncio

import pytest

from crackerjack.fixers import anti_pattern


class TestCheckDuplicateDefinitions:
    def test_no_duplicates_returns_empty_list(self) -> None:
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n"

        assert anti_pattern._check_duplicate_definitions(code) == []

    def test_duplicate_top_level_function_is_reported(self) -> None:
        code = "def foo():\n    pass\n\ndef foo():\n    pass\n"

        result = anti_pattern._check_duplicate_definitions(code)

        assert result == [
            "Duplicate top-level definition of 'foo' at line 4 (previous at line 1)"
        ]

    def test_duplicate_top_level_class_is_reported(self) -> None:
        code = "class Foo:\n    pass\n\nclass Foo:\n    pass\n"

        result = anti_pattern._check_duplicate_definitions(code)

        assert result == [
            "Duplicate top-level definition of 'Foo' at line 4 (previous at line 1)"
        ]

    def test_invalid_syntax_returns_empty_list(self) -> None:
        code = "def foo(:\n    pass\n"

        assert anti_pattern._check_duplicate_definitions(code) == []

    def test_only_first_duplicate_is_reported_not_all_pre_existing_bug(self) -> None:
        """The loop returns immediately on the first duplicate found, so a
        third occurrence (or a second, unrelated duplicate name) is never
        even examined. Preserved verbatim from AntiPatternAgent per
        CLAUDE.md Rule 7 -- not fixed."""
        code = (
            "def foo():\n"
            "    pass\n"
            "\n"
            "def foo():\n"
            "    pass\n"
            "\n"
            "def foo():\n"
            "    pass\n"
            "\n"
            "def baz():\n"
            "    pass\n"
            "\n"
            "def baz():\n"
            "    pass\n"
        )

        result = anti_pattern._check_duplicate_definitions(code)

        assert result == [
            "Duplicate top-level definition of 'foo' at line 4 (previous at line 1)"
        ]

    def test_nested_method_same_name_as_module_function_not_flagged_pre_existing_bug(
        self,
    ) -> None:
        """Only ``tree.body`` (top-level statements) is inspected, not
        ``ast.walk(tree)`` -- a method nested inside a class is never
        compared against a module-level function of the same name.
        Preserved verbatim from AntiPatternAgent per CLAUDE.md Rule 7 --
        not fixed."""
        code = (
            "def helper():\n    pass\n\nclass C:\n    def helper(self):\n        pass\n"
        )

        assert anti_pattern._check_duplicate_definitions(code) == []


class TestCheckUnclosedBrackets:
    def test_balanced_brackets_returns_none(self) -> None:
        code = "x = (1 + 2) * [3, 4] + {5: 6}"

        assert anti_pattern._check_unclosed_brackets(code) is None

    def test_unclosed_paren_is_reported(self) -> None:
        code = "x = (1 + 2"

        result = anti_pattern._check_unclosed_brackets(code)

        assert result == "Unclosed '(' at position 4"

    def test_unmatched_closing_bracket_is_reported(self) -> None:
        code = "x = 1)"

        result = anti_pattern._check_unclosed_brackets(code)

        assert result == "Unmatched closing ')' at position 5"

    def test_mismatched_bracket_types_are_reported(self) -> None:
        code = "x = (1 + 2]"

        result = anti_pattern._check_unclosed_brackets(code)

        assert result == "Mismatched brackets: expected ')' but got ']' at position 10"

    def test_paren_inside_string_literal_is_misreported_pre_existing_bug(self) -> None:
        """The scanner has no string/comment awareness -- it treats every
        character in the source, including characters inside string
        literals, as a real bracket token. A syntactically valid one-line
        string containing a lone ``(`` is misreported as an unclosed
        bracket. Preserved verbatim from AntiPatternAgent per CLAUDE.md
        Rule 7 -- not fixed."""
        code = 'x = "("'

        result = anti_pattern._check_unclosed_brackets(code)

        assert result == "Unclosed '(' at position 5"


class TestCheckImportPlacement:
    def test_import_within_first_ten_lines_is_not_flagged(self) -> None:
        lines = ["import os"] + [f"# comment {i}" for i in range(9)]
        code = "\n".join(lines)

        assert anti_pattern._check_import_placement(code) is None

    def test_import_after_line_ten_with_no_guard_lines_is_flagged(self) -> None:
        lines = [f"# comment {i}" for i in range(10)]
        lines.append("import os")
        code = "\n".join(lines)

        result = anti_pattern._check_import_placement(code)

        assert result == "Import statement at line 11 appears mid-file"

    def test_def_before_late_import_does_not_suppress_warning_pre_existing_bug(
        self,
    ) -> None:
        """The guard is meant to skip flagging a late import when the file
        already has a docstring/class/def before it, but it is implemented
        as ``x in lines[:i]`` where ``lines[:i]`` is a list of *raw,
        unstripped* lines -- an exact whole-line-equality check, not a
        substring check. A real ``def foo():`` line is never equal to the
        bare string ``"def "``, so this guard never actually fires for
        realistic code. Preserved verbatim from AntiPatternAgent per
        CLAUDE.md Rule 7 -- not fixed."""
        lines = ["def foo():", "    pass"] + [f"# comment {i}" for i in range(9)]
        lines.append("import os")
        code = "\n".join(lines)

        result = anti_pattern._check_import_placement(code)

        assert result == "Import statement at line 12 appears mid-file"

    def test_lone_triple_quote_line_suppresses_warning_pre_existing_bug(self) -> None:
        """A raw source line consisting of *exactly* ``\"\"\"`` (the
        docstring delimiter alone on its own line) happens to satisfy the
        buggy exact-line-equality guard described above, so it does
        suppress the warning -- unlike a real ``class``/``def`` line.
        Preserved verbatim from AntiPatternAgent per CLAUDE.md Rule 7 --
        not fixed."""
        lines = ['"""'] + [f"docstring line {i}" for i in range(8)] + ['"""']
        lines.append("import os")
        code = "\n".join(lines)

        assert anti_pattern._check_import_placement(code) is None


class TestCheckFutureImports:
    def test_standard_future_import_is_never_detected_pre_existing_bug(self) -> None:
        """The trigger condition is
        ``stripped.startswith("__future__")``, but the only valid Python
        syntax for a future import is ``from __future__ import ...``, whose
        stripped form starts with ``"from "``, not ``"__future__"``. This
        function therefore never sets its internal ``future_found`` flag
        for any syntactically valid Python file and never emits either of
        its two warnings against real code. Preserved verbatim from
        AntiPatternAgent per CLAUDE.md Rule 7 -- not fixed."""
        code = (
            "from __future__ import annotations\n"
            "\n"
            "import os\n"
            "\n"
            "\n"
            "def foo():\n"
            "    pass\n"
        )

        assert anti_pattern._check_future_imports(code) == []

    def test_bare_dunder_future_prefix_triggers_detection(self) -> None:
        """Documents the only input shape that actually triggers the
        (otherwise dead) detection path: a stripped line literally starting
        with the bare word ``__future__`` (not preceded by ``from ``, so
        not valid Python for an actual future-import statement)."""
        code = "__future__ import annotations\nimport os\n"

        result = anti_pattern._check_future_imports(code)

        assert result == [
            "Code after __future__ import (line 2) - move __future__ to top of file"
        ]

    def test_multiple_bare_dunder_future_lines_detected(self) -> None:
        code = "__future__ import annotations\n__future__ import division\n"

        result = anti_pattern._check_future_imports(code)

        assert result == ["Multiple __future__ imports detected (line 2)"]

    def test_no_future_marker_returns_empty_list(self) -> None:
        code = "import os\n\n\ndef foo():\n    pass\n"

        assert anti_pattern._check_future_imports(code) == []


class TestIdentifyAntiPatterns:
    def test_no_code_in_context_returns_warning(self) -> None:
        result = asyncio.run(anti_pattern.identify_anti_patterns({}))

        assert result == ["No code content in context"]

    def test_reads_code_key_from_context(self) -> None:
        context = {"code": "def foo():\n    pass\n"}

        result = asyncio.run(anti_pattern.identify_anti_patterns(context))

        assert result == []

    def test_falls_back_to_relevant_code_key(self) -> None:
        context = {"relevant_code": "def foo():\n    pass\n"}

        result = asyncio.run(anti_pattern.identify_anti_patterns(context))

        assert result == []

    def test_falls_back_to_file_content_key(self) -> None:
        context = {"file_content": "def foo():\n    pass\n"}

        result = asyncio.run(anti_pattern.identify_anti_patterns(context))

        assert result == []

    def test_code_key_takes_precedence_over_others(self) -> None:
        context = {
            "code": "def foo():\n    pass\n",
            "relevant_code": "x = (1 + 2",
            "file_content": "x = (1 + 2",
        }

        result = asyncio.run(anti_pattern.identify_anti_patterns(context))

        assert result == []

    def test_aggregates_duplicate_definition_and_bracket_warnings(self) -> None:
        # Note: the unclosed bracket lives inside a string literal so the
        # snippet stays syntactically valid -- an actually-unclosed paren
        # would make ast.parse() fail and _check_duplicate_definitions
        # would silently return [] (see TestCheckDuplicateDefinitions'
        # test_invalid_syntax_returns_empty_list), masking the duplicate
        # warning entirely.
        code = 'def foo():\n    pass\n\ndef foo():\n    x = "("\n'
        context = {"code": code}

        result = asyncio.run(anti_pattern.identify_anti_patterns(context))

        assert (
            "Duplicate top-level definition of 'foo' at line 4 (previous at line 1)"
            in result
        )
        assert any(w.startswith("Unclosed '('") for w in result)

    @pytest.mark.asyncio
    async def test_can_be_awaited_directly(self) -> None:
        result = await anti_pattern.identify_anti_patterns(
            {"code": "def foo():\n    pass\n"}
        )

        assert result == []
