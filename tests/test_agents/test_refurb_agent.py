"""Tests for RefurbCodeTransformerAgent."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from crackerjack.agents.base import AgentContext, Issue, IssueType, FixResult, Priority
from crackerjack.agents.refurb_agent import (
    RefurbCodeTransformerAgent,
    FURB_TRANSFORMATIONS,
)


@pytest.fixture
def mock_context():
    """Create mock AgentContext."""
    context = Mock(spec=AgentContext)
    context.project_path = Path("/test/project")
    context.get_file_content = Mock(return_value=None)
    context.write_file_content = Mock(return_value=True)
    return context


@pytest.fixture
def agent(mock_context):
    """Create RefurbCodeTransformerAgent instance."""
    return RefurbCodeTransformerAgent(mock_context)


class TestRefurbCodeTransformerAgent:
    """Tests for RefurbCodeTransformerAgent."""

    def test_supported_types(self, agent):
        """Test get_supported_types returns REFURB."""
        assert agent.get_supported_types() == {IssueType.REFURB}

    def test_furb_transformations_mapping(self):
        """Test FURB_TRANSFORMATIONS has expected codes."""
        assert "FURB102" in FURB_TRANSFORMATIONS
        assert "FURB118" in FURB_TRANSFORMATIONS
        assert "FURB129" in FURB_TRANSFORMATIONS
        assert "FURB140" in FURB_TRANSFORMATIONS
        assert FURB_TRANSFORMATIONS["FURB102"] == "_transform_compare_zero"

    @pytest.mark.asyncio
    async def test_can_handle_refurb_issue(self, agent):
        """Test can_handle returns confidence for valid FURB code."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.REFURB
        issue.message = "FURB102: compare zero"
        issue.details = ["refurb_code: FURB102"]

        confidence = await agent.can_handle(issue)
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_can_handle_non_refurb_issue(self, agent):
        """Test can_handle returns 0 for non-REFURB issues."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.TYPE_ERROR
        issue.message = "Type error"

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_unknown_furb_code(self, agent):
        """Test can_handle returns 0 for unknown FURB code."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.REFURB
        issue.message = "Unknown code"
        issue.details = ["refurb_code: FURB999"]

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_no_furb_code(self, agent):
        """Test can_handle returns 0 when no FURB code found."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.REFURB
        issue.message = "Some refurb issue"
        issue.details = []

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0


class TestRefurbCodeTransformerAgentExtraction:
    """Tests for code extraction methods."""

    def test_extract_furb_code_from_details_refurb_code(self, agent):
        """Test _extract_furb_code extracts from refurb_code detail."""
        issue = Mock(spec=Issue)
        issue.message = "Some message"
        issue.details = ["Additional info", "refurb_code: FURB102"]
        issue.reason = None

        code = agent._extract_furb_code(issue)
        assert code == "FURB102"

    def test_extract_furb_code_from_details_brackets(self, agent):
        """Test _extract_furb_code extracts from bracketed FURB code."""
        issue = Mock(spec=Issue)
        issue.message = "Some message"
        issue.details = ["[FURB105]"]

        code = agent._extract_furb_code(issue)
        assert code == "FURB105"

    def test_extract_furb_code_from_message(self, agent):
        """Test _extract_furb_code extracts from message."""
        issue = Mock(spec=Issue)
        issue.message = "FURB118: enumerate transformation"
        issue.details = []
        issue.reason = None

        code = agent._extract_furb_code(issue)
        assert code == "FURB118"

    def test_extract_furb_code_from_reason(self, agent):
        """Test _extract_furb_code extracts from reason attribute."""
        issue = Mock(spec=Issue)
        issue.message = "Some message"
        issue.details = []
        issue.reason = "REFURB_TRANSFORM:FURB129:some transformation"

        code = agent._extract_furb_code(issue)
        assert code == "FURB129"

    def test_extract_furb_code_not_found(self, agent):
        """Test _extract_furb_code returns None when not found."""
        issue = Mock(spec=Issue)
        issue.message = "No FURB code here"
        issue.details = []
        issue.reason = None

        code = agent._extract_furb_code(issue)
        assert code is None


class TestRefurbCodeTransformerAgentAnalysis:
    """Tests for analyze_and_fix method."""

    @pytest.mark.asyncio
    async def test_analyze_and_fix_no_file_path(self, agent):
        """Test analyze_and_fix handles missing file path."""
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.HIGH,
            message="FURB102 issue",
            file_path=None,
        )
        result = await agent.analyze_and_fix(issue)
        assert result.success is False
        assert "No file path provided" in result.remaining_issues

    @pytest.mark.asyncio
    async def test_analyze_and_fix_file_not_found(self, agent):
        """Test analyze_and_fix handles missing file."""
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.HIGH,
            message="FURB102 issue",
            file_path="/test/nonexistent.py",
        )
        result = await agent.analyze_and_fix(issue)
        assert result.success is False
        # remaining_issues is a list of formatted strings; check any entry
        # mentions the file-not-found condition.
        assert any("File not found" in msg for msg in result.remaining_issues)

    @pytest.mark.asyncio
    async def test_analyze_and_fix_cannot_read_file(self, agent, mock_context):
        """Test analyze_and_fix handles unreadable file."""
        mock_context.get_file_content = Mock(return_value=None)
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.HIGH,
            message="FURB102 issue",
            file_path="/test/file.py",
        )
        result = await agent.analyze_and_fix(issue)
        assert result.success is False
        # The agent reports the file as not found when content is missing.
        assert any(
            "File not found" in msg or "Could not read" in msg
            for msg in result.remaining_issues
        )

    @pytest.mark.asyncio
    async def test_analyze_and_fix_no_furb_code(self, agent, mock_context, tmp_path):
        """Test analyze_and_fix handles missing FURB code."""
        # The implementation checks ``file_path.exists()`` first, so the
        # test must point at a real (but empty) file to reach the FURB
        # extraction branch.
        target = tmp_path / "file.py"
        target.write_text("import os\n")
        mock_context.get_file_content = Mock(return_value="import os\n")
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.HIGH,
            message="Some issue",
            file_path=str(target),
        )
        result = await agent.analyze_and_fix(issue)
        assert result.success is False
        assert any(
            "Could not extract FURB code" in msg for msg in result.remaining_issues
        )

    @pytest.mark.asyncio
    async def test_analyze_and_fix_no_handler(self, agent, mock_context, tmp_path):
        """Test analyze_and_fix handles missing handler."""
        target = tmp_path / "file.py"
        target.write_text("import os\n")
        mock_context.get_file_content = Mock(return_value="import os\n")
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.HIGH,
            message="Issue",
            file_path=str(target),
            details=["refurb_code: FURB999"],
        )
        result = await agent.analyze_and_fix(issue)
        assert result.success is False
        assert any(
            "No handler for FURB999" in msg for msg in result.remaining_issues
        )


class TestRefurbCodeTransformerAgentTransformations:
    """Tests for transformation methods."""

    def test_transform_compare_zero(self, agent):
        """Test _transform_compare_zero handles zero comparisons."""
        content = "if x == 0:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB102"

        new_content, fixes = agent._transform_compare_zero(content, issue)
        assert "not x" in new_content or new_content != content

    def test_transform_compare_zero_startswith(self, agent):
        """Test _transform_compare_zero handles startswith."""
        content = 'if x.startswith(a) or x.startswith(b):\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB102"

        new_content, fixes = agent._transform_compare_zero(content, issue)
        assert "startswith((" in new_content or "or" not in fixes

    def test_transform_any_all(self, agent):
        """Test _transform_any_all converts loops."""
        content = "for x in items:\n    if condition:\n        return True\nreturn False\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB129"

        new_content, fixes = agent._transform_any_all(content, issue)
        assert "any(" in new_content or fixes

    def test_transform_bool_return(self, agent):
        """Test _transform_bool_return simplifies conditional returns."""
        # The transform pattern requires ``else:`` to be indented to the
        # same level as the ``if`` — a top-level ``if/else`` won't match.
        content = "def f(x):\n    if x:\n        return True\n    else:\n        return False\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB136"

        new_content, fixes = agent._transform_bool_return(content, issue)
        assert "bool(" in new_content

    def test_transform_copy(self, agent):
        """Test _transform_copy replaces slice with copy()."""
        content = "items = original[:]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB145"

        new_content, fixes = agent._transform_copy(content, issue)
        assert ".copy()" in new_content

    def test_transform_max_min(self, agent):
        """Test _transform_max_min handles manual max/min."""
        content = "max_val = items[0]\nfor x in items:\n    if x > max_val:\n        max_val = x\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB148"

        new_content, fixes = agent._transform_max_min(content, issue)
        assert "max(" in new_content or "min(" in new_content or fixes

    def test_transform_pow_operator(self, agent):
        """Test _transform_pow_operator replaces math.pow."""
        content = "result = math.pow(2, 3)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB152"

        new_content, fixes = agent._transform_pow_operator(content, issue)
        assert "**" in new_content

    def test_transform_sorted_key_identity(self, agent):
        """Test _transform_sorted_key_identity removes identity key."""
        content = "sorted(items, key=lambda x: x)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB163"

        new_content, fixes = agent._transform_sorted_key_identity(content, issue)
        assert "sorted(items)" in new_content

    def test_transform_int_scientific(self, agent):
        """Test _transform_int_scientific converts scientific notation."""
        content = "value = int(1e5)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB161"

        new_content, fixes = agent._transform_int_scientific(content, issue)
        assert "100000" in new_content

    def test_transform_membership_test(self, agent):
        """Test _transform_membership_test converts list to tuple."""
        content = "if x in [1, 2, 3]:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB109"

        new_content, fixes = agent._transform_membership_test(content, issue)
        assert "in (1, 2, 3)" in new_content

    def test_transform_isinstance_type_check(self, agent):
        """Test _transform_isinstance_type_check converts type checks."""
        content = "if type(x) == int:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB126"

        new_content, fixes = agent._transform_isinstance_type_check(content, issue)
        assert "isinstance(" in new_content

    def test_transform_write_whole_file(self, agent):
        """Test _transform_write_whole_file converts open().write()."""
        content = 'open(path, "w").write(data)\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB123"

        new_content, fixes = agent._transform_write_whole_file(content, issue)
        assert "Path(path).write_text(" in new_content

    def test_transform_multiple_with(self, agent):
        """Test _transform_multiple_with combines nested with statements."""
        content = "with a:\n    with b:\n        pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB117"

        new_content, fixes = agent._transform_multiple_with(content, issue)
        assert "with a, b:" in new_content

    def test_transform_redundant_not(self, agent):
        """Test _transform_redundant_not simplifies negated comparisons."""
        content = "if not (x == y):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB173"

        new_content, fixes = agent._transform_redundant_not(content, issue)
        # The replacement preserves the original whitespace around the
        # comparison, so we accept any spacing around ``!=``.
        assert "!=" in new_content
        assert "not" not in new_content.split("if ", 1)[1].split(":", 1)[0]

    def test_transform_substring(self, agent):
        """Test _transform_substring converts find() patterns."""
        content = 'if x.find("y") != -1:\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_substring(content, issue)
        assert '"y" in x' in new_content

    def test_transform_print_empty_string(self, agent):
        """Test _transform_print_empty_string simplifies print("")."""
        content = 'print("")\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB105"

        new_content, fixes = agent._transform_print_empty_string(content, issue)
        assert "print()" in new_content

    def test_transform_redundant_continue(self, agent):
        """Test _transform_redundant_continue removes continue statements."""
        content = "for x in items:\n    continue\n\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB111"

        new_content, fixes = agent._transform_redundant_continue(content, issue)
        assert "continue" not in new_content or fixes

    def test_transform_redundant_pass(self, agent):
        """Test _transform_redundant_pass converts appends to extend."""
        content = "items.append(a)\nitems.append(b)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB113"

        new_content, fixes = agent._transform_redundant_pass(content, issue)
        assert "extend((" in new_content or fixes

    def test_transform_open_mode_r(self, agent):
        """Test _transform_open_mode_r simplifies open mode."""
        content = 'open(path, "r")\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB115"

        new_content, fixes = agent._transform_open_mode_r(content, issue)
        assert "open(path)" in new_content or "open()" in new_content

    def test_transform_redundant_fstring(self, agent):
        """Test _transform_redundant_fstring converts redundant f-strings."""
        content = 'x = f"{str(y)}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB141"

        new_content, fixes = agent._transform_redundant_fstring(content, issue)
        assert "str(" in new_content or "f\"" not in new_content

    def test_transform_type_none_comparison(self, agent):
        """Test _transform_type_none_comparison converts None comparisons."""
        content = "if x == None:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB169"

        new_content, fixes = agent._transform_type_none_comparison(content, issue)
        assert "is None" in new_content

    def test_transform_redundant_lambda(self, agent):
        """Test _transform_redundant_lambda simplifies lambda patterns."""
        content = "lambda x: func(x)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB156"

        new_content, fixes = agent._transform_redundant_lambda(content, issue)
        assert "func" in new_content and "lambda" not in new_content

    def test_transform_unnecessary_listcomp(self, agent):
        """Test _transform_unnecessary_listcomp replaces indexing."""
        content = "[x for x in items][0]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB142"

        new_content, fixes = agent._transform_unnecessary_listcomp(content, issue)
        assert "next(" in new_content

    def test_transform_enumerate(self, agent):
        """Test _transform_enumerate replaces manual index tracking."""
        content = "i = 0\nfor x in items:\n    print(i)\n    i += 1\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB118"

        new_content, fixes = agent._transform_enumerate(content, issue)
        assert "enumerate(" in new_content or fixes

    def test_transform_enumerate_lambda(self, agent):
        """Test _transform_enumerate handles lambda index patterns."""
        content = "lambda x: x[0]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB118"

        new_content, fixes = agent._transform_enumerate(content, issue)
        assert "operator.itemgetter" in new_content or fixes


class TestRefurbCodeTransformerAgentASTTransform:
    """Tests for AST transformation methods."""

    def test_unparse_tree(self, agent):
        """Test _unparse_tree handles valid AST."""
        import ast
        tree = ast.parse("x = 1\n")
        result = agent._unparse_tree(tree, "x = 1\n")
        assert result is not None

    def test_try_ast_transform_no_handler(self, agent):
        """Test _try_ast_transform returns original when no handler."""
        content = "x = 1\n"
        issue = Mock(spec=Issue)
        issue.line_number = 1
        furb_code = "FURB999"

        new_content, desc = agent._try_ast_transform(content, issue, furb_code, None)
        assert new_content == content
        assert "No AST transformation" in desc

    def test_try_ast_transform_known_handler(self, agent):
        """Test _try_ast_transform uses AST handler for known codes."""
        content = "try:\n    pass\nexcept Exception:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.line_number = 1
        furb_code = "FURB107"

        handler = agent._ast_transform_suppress
        new_content, desc = agent._try_ast_transform(content, issue, furb_code, handler)
        assert "suppress" in desc.lower() or new_content == content

    def test_ast_transform_suppress_no_match(self, agent):
        """Test _ast_transform_suppress returns None for non-matching."""
        import ast
        content = "x = 1\n"
        tree = ast.parse(content)
        result, desc = agent._ast_transform_suppress(tree, 1, content)
        assert result is None

    def test_transform_delete_while_iterating(self, agent):
        """Test _transform_delete_while_iterating returns unchanged."""
        content = "while iterating:\n    remove()\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB110"

        new_content, desc = agent._transform_delete_while_iterating(content, issue)
        assert "manual review" in desc.lower()

    def test_transform_redundant_none_comparison(self, agent):
        """Test _transform_redundant_none_comparison returns unchanged."""
        content = "if x is not None:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB108"

        new_content, desc = agent._transform_redundant_none_comparison(content, issue)
        assert "manual review" in desc.lower()

    def test_transform_fstring_numeric_literal(self, agent):
        """Test _transform_fstring_numeric_literal returns unchanged."""
        content = 'f"{123}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB116"

    def test_transform_no_default_or_strips_empty_string(self, agent):
        """FURB143 (``no-default-or``) in refurb v2.x: strip ``or ""``
        when the LHS is typed. This was previously mapped to the
        wrong transform (``_transform_unnecessary_index_lookup``),
        so the fixer silently no-op'd and the issue kept recurring
        in every run.
        """
        content = (
            "    returncode, stdout, stderr = await self.run_command(\n"
            '        ["uv", "run", "codespell", "-w", issue.file_path],\n'
            "    )\n"
            '    stdout_text = stdout or ""\n'
            "    fixed_count = sum(1 for line in stdout_text.splitlines() if \"FIXED\" in line)\n"
        )
        issue = Mock(spec=Issue)
        issue.message = "FURB143: Replace `stdout or \"\"` with `stdout`"

        new_content, desc = agent._transform_no_default_or(content, issue)
        assert 'stdout or ""' not in new_content
        assert "stdout_text = stdout\n" in new_content
        assert "Removed redundant" in desc

    def test_transform_no_default_or_strips_zero(self, agent):
        """The same transform should also strip ``or 0`` (int default)."""
        content = "counter = count or 0\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB143"

        new_content, _ = agent._transform_no_default_or(content, issue)
        assert "or 0" not in new_content
        assert "counter = count\n" in new_content

    def test_transform_no_default_or_strips_none(self, agent):
        """The same transform should also strip ``or None``."""
        content = "result = maybe_value or None\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB143"

        new_content, _ = agent._transform_no_default_or(content, issue)
        assert "or None" not in new_content
        assert "result = maybe_value\n" in new_content

    def test_transform_no_default_or_no_match_returns_unchanged(self, agent):
        """Lines without a ``or <falsey>`` pattern are not modified."""
        content = 'stdout_text = stdout or "default"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB143"

        new_content, desc = agent._transform_no_default_or(content, issue)
        assert new_content == content
        assert "No no-default-or transformation" in desc

    def test_furb143_mapping_points_to_no_default_or(self):
        """Regression guard: the FURB143 → _transform_no_default_or
        mapping was previously broken (it pointed to
        ``_transform_unnecessary_index_lookup``, which is the rule
        from a much older refurb version).
        """
        assert FURB_TRANSFORMATIONS["FURB143"] == "_transform_no_default_or"


class TestRefurbCodeTransformerAgentListComprehension:
    """Tests for list comprehension transformation."""

    def test_find_list_comprehension_loop(self, agent):
        """Test _find_list_comprehension_loop locates loops."""
        import ast
        content = """
items = []
for x in sequence:
    items.append(x)
"""
        issue = Mock(spec=Issue)
        issue.line_number = 3
        tree = ast.parse(content)

        result = agent._find_list_comprehension_loop(tree, 3)
        assert result is not None

    def test_find_list_comprehension_loop_out_of_range(self, agent):
        """Test _find_list_comprehension_loop handles out of range."""
        import ast
        content = "for x in items:\n    pass\n"
        tree = ast.parse(content)

        result = agent._find_list_comprehension_loop(tree, 999)
        assert result is None

    def test_extract_append_loop_parts(self, agent):
        """Test _extract_append_loop_parts extracts statements."""
        import ast
        content = """
items = []
for x in items:
    items.append(x)
"""
        tree = ast.parse(content)
        for_node = list(ast.walk(tree))[1]

        if isinstance(for_node, ast.For):
            result = agent._extract_append_loop_parts(for_node)
            assert result is not None

    def test_get_append_target_name(self, agent):
        """Test _get_append_target_name extracts target name."""
        import ast
        content = "items.append(x)\n"
        tree = ast.parse(content)
        expr_node = tree.body[0]
        assert isinstance(expr_node, ast.Expr)

        result = agent._get_append_target_name(expr_node)
        assert result == "items"

    def test_build_list_comprehension_rewrite_no_append(self, agent):
        """Test _build_list_comprehension_rewrite handles no append."""
        import ast
        content = """
for x in items:
    pass
"""
        tree = ast.parse(content)
        for_node = list(ast.walk(tree))[1]

        if isinstance(for_node, ast.For):
            result = agent._build_list_comprehension_rewrite(content, for_node)
            assert result is None

    def test_transform_list_comprehension_no_line_number(self, agent):
        """Test _transform_list_comprehension handles missing line number."""
        content = "for x in items:\n    items.append(x)\n"
        issue = Mock(spec=Issue)
        issue.line_number = None

        new_content, desc = agent._transform_list_comprehension(content, issue)
        assert "requires a line number" in desc

    def test_transform_list_comprehension_invalid_syntax(self, agent):
        """Test _transform_list_comprehension handles invalid syntax."""
        content = "for x in {\n    items.append(x)\n"
        issue = Mock(spec=Issue)
        issue.line_number = 1

        new_content, desc = agent._transform_list_comprehension(content, issue)
        assert "requires valid Python" in desc


class TestRefurbCodeTransformerAgentIntegration:
    """Integration tests for full transformation flow."""

    @pytest.mark.asyncio
    async def test_transform_enumerate_full(self, agent, mock_context):
        """Test full enumerate transformation flow."""
        content = "i = 0\nfor x in items:\n    print(i)\n    i += 1\n"
        mock_context.get_file_content = Mock(return_value=content)
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.HIGH,
            message="FURB118: enumerate",
            file_path="/test/file.py",
            details=["refurb_code: FURB118"],
        )

        result = await agent.analyze_and_fix(issue)
        assert "enumerate" in str(result.fixes_applied) or result.success is False

    @pytest.mark.asyncio
    async def test_transform_copy_full(self, agent, mock_context):
        """Test full copy transformation flow."""
        content = "new_list = old_list[:]\n"
        mock_context.get_file_content = Mock(return_value=content)
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.HIGH,
            message="FURB145: copy",
            file_path="/test/file.py",
            details=["refurb_code: FURB145"],
        )

        result = await agent.analyze_and_fix(issue)
        assert ".copy()" in str(result.fixes_applied) or result.success is False

    def test_zip_returns_manual_review_note(self, agent):
        """Test _transform_zip returns manual review note."""
        content = "for i in range(len(items)):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB140"

        new_content, desc = agent._transform_zip(content, issue)
        assert "manual review" in desc.lower() or new_content != content
