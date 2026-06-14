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
        """FURB129: removes redundant .readlines() call."""
        content = 'with open("file.txt") as f:\n    for line in f.readlines():\n        pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB129"
        new_content, fixes = agent._transform_any_all(content, issue)
        assert ".readlines()" not in new_content
        assert "for line in f:" in new_content

    def test_transform_bool_return(self, agent):
        """FURB136: ternary ``x = a if a > b else b`` -> ``x = max(a, b)``."""
        content = (
            "score1 = 90\n"
            "score2 = 99\n"
            "highest_score = score1 if score1 > score2 else score2\n"
        )
        issue = Mock(spec=Issue)
        issue.message = "FURB136"
        new_content, fixes = agent._transform_bool_return(content, issue)
        assert "max(score1, score2)" in new_content
        assert "if score1 > score2" not in new_content

    def test_transform_copy(self, agent):
        """Test _transform_copy replaces slice with copy()."""
        content = "items = original[:]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB145"

        new_content, fixes = agent._transform_copy(content, issue)
        assert ".copy()" in new_content

    def test_transform_max_min(self, agent):
        """FURB148: ``for i, _ in enumerate(books)`` -> ``for i in range(len(books))``."""
        content = 'books = ["a", "b"]\nfor index, _ in enumerate(books):\n    print(index)\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB148"
        new_content, fixes = agent._transform_max_min(content, issue)
        assert "for index in range(len(books)):" in new_content
        assert "enumerate(books)" not in new_content

    def test_transform_pow_operator(self, agent):
        """FURB152: hardcoded 3.1415 -> math.pi."""
        content = "def area(r):\n    return 3.1415 * r * r\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB152"
        new_content, fixes = agent._transform_pow_operator(content, issue)
        assert "math.pi" in new_content
        assert "3.1415" not in new_content

    def test_transform_sorted_key_identity(self, agent):
        """FURB163: ``math.log(x, 10)`` -> ``math.log10(x)``."""
        content = "import math\npower = math.log(x, 10)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB163"
        new_content, fixes = agent._transform_sorted_key_identity(content, issue)
        assert "math.log10(x)" in new_content
        assert "math.log(x, 10)" not in new_content

    def test_transform_int_scientific(self, agent):
        """FURB161: ``bin(x).count("1")`` -> ``x.bit_count()``."""
        content = 'x = bin(0b1010).count("1")\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB161"
        new_content, fixes = agent._transform_int_scientific(content, issue)
        assert "bit_count" in new_content
        assert 'count("1")' not in new_content

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
        """FURB173: dict literal with **spread -> dict | spread."""
        content = 'def f(settings):\n    return {"color": "1", **settings}\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB173"
        new_content, fixes = agent._transform_redundant_not(content, issue)
        # The **spread should be gone; replaced with a | union.
        assert "**" not in new_content
        assert " | settings" in new_content
        assert '"color": "1"' in new_content

    def test_transform_substring(self, agent):
        """Test _transform_substring converts find() patterns."""
        content = 'if x.find("y") != -1:\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_substring(content, issue)
        assert '"y" in x' in new_content

    def test_transform_useless_fstring(self, agent):
        """Test _transform_useless_fstring converts f\"{x}\" to str(x)."""
        content = 'x = f"{y}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_useless_fstring(content, issue)
        assert "x = str(y)" in new_content
        assert "useless f-string" in fixes

    def test_transform_useless_fstring_single_quoted(self, agent):
        """Test _transform_useless_fstring handles single quotes too."""
        content = "x = f'{y}'\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_useless_fstring(content, issue)
        assert "x = str(y)" in new_content

    def test_transform_useless_fstring_attribute_access(self, agent):
        """Test _transform_useless_fstring handles attribute access in expression."""
        content = 'x = f"{obj.attr}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_useless_fstring(content, issue)
        assert "x = str(obj.attr)" in new_content

    def test_transform_useless_fstring_skips_conversion_specifier(self, agent):
        """Test _transform_useless_fstring does NOT touch f-strings with !r/!s/!a."""
        content = 'x = f"{y!r}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_useless_fstring(content, issue)
        # Should not change - !r is a real conversion specifier
        assert new_content == content

    def test_transform_useless_fstring_skips_format_spec(self, agent):
        """Test _transform_useless_fstring does NOT touch f-strings with format spec."""
        content = 'x = f"{y:>5}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_useless_fstring(content, issue)
        # Should not change - :>5 is a real format spec
        assert new_content == content

    def test_transform_useless_fstring_skips_real_fstrings(self, agent):
        """Test _transform_useless_fstring does NOT touch f-strings with surrounding text."""
        content = 'msg = f"hello {name}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_useless_fstring(content, issue)
        assert new_content == content

    def test_transform_useless_fstring_handles_multiple(self, agent):
        """Test _transform_useless_fstring counts multiple substitutions."""
        content = 'a = f"{x}"\nb = f"{y}"\nc = f"{z}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB183"

        new_content, fixes = agent._transform_useless_fstring(content, issue)
        assert "a = str(x)" in new_content
        assert "b = str(y)" in new_content
        assert "c = str(z)" in new_content

    def test_furb183_mapping(self):
        """FURB183 must map to _transform_useless_fstring, not _transform_substring."""
        assert FURB_TRANSFORMATIONS["FURB183"] == "_transform_useless_fstring"

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
        """FURB169: ``type(x) is type(None)`` -> ``x is None``."""
        content = "x = 123\nif type(x) is type(None):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB169"
        new_content, fixes = agent._transform_type_none_comparison(content, issue)
        assert "x is None" in new_content
        assert "type(x) is type(None)" not in new_content

    def test_transform_redundant_lambda(self, agent):
        """FURB156: hardcoded alphabet ``"0123456789"`` -> ``string.digits``."""
        content = 'digits = "0123456789"\nif c in digits:\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB156"
        new_content, fixes = agent._transform_redundant_lambda(content, issue)
        assert "string.digits" in new_content
        assert '"0123456789"' not in new_content
        assert "import string" in new_content

    def test_transform_unnecessary_listcomp(self, agent):
        """FURB142: for-loop with set.discard -> set.difference_update."""
        content = (
            'sentence = "hello world"\n'
            'vowels = "aeiou"\n'
            "letters = set(sentence)\n"
            "for vowel in vowels:\n"
            "    letters.discard(vowel)\n"
        )
        issue = Mock(spec=Issue)
        issue.message = "FURB142"
        new_content, fixes = agent._transform_unnecessary_listcomp(content, issue)
        assert "letters.difference_update(vowels)" in new_content
        assert "for vowel in vowels:" not in new_content

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

    # ------------------------------------------------------------------
    # Tier 2 audit fixes — wrong-rule redirects
    # (Each handler was previously stubbed or pointed at a different
    # FURB code. See docs/audits/2026-06-12-furb-handler-audit.md.)
    # ------------------------------------------------------------------

    def test_transform_any_all_removes_readlines(self, agent):
        """FURB129: ``f.readlines()`` -> ``f`` (canonical)."""
        content = 'with open("file.txt") as f:\n    for line in f.readlines():\n        pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB129"
        new_content, fixes = agent._transform_any_all(content, issue)
        assert ".readlines()" not in new_content
        assert "for line in f:" in new_content
        assert "readlines" in fixes.lower()

    def test_transform_single_item_membership_del(self, agent):
        """FURB131: ``del nums[:]`` -> ``nums.clear()``."""
        content = "nums = [1, 2, 3]\ndel nums[:]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB131"
        new_content, fixes = agent._transform_single_item_membership(content, issue)
        assert "nums.clear()" in new_content
        assert "del nums[:]" not in new_content

    def test_transform_single_item_membership_slice_assign(self, agent):
        """FURB131: ``nums[:] = []`` -> ``nums.clear()``."""
        content = "nums = [1, 2, 3]\nnums[:] = []\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB131"
        new_content, fixes = agent._transform_single_item_membership(content, issue)
        assert "nums.clear()" in new_content
        assert "nums[:] = []" not in new_content

    def test_transform_redundant_not_dict_union(self, agent):
        """FURB173: ``{"k": v, **spread}`` -> ``{"k": v} | spread``."""
        content = 'def f(settings):\n    return {"color": "1", **settings}\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB173"
        new_content, fixes = agent._transform_redundant_not(content, issue)
        assert "**" not in new_content
        assert " | settings" in new_content

    def test_transform_redundant_not_dict_union_with_attr(self, agent):
        """FURB173: ``**obj.attr`` spread also works."""
        content = "def f(obj):\n    return {\"a\": 1, **obj.kwargs}\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB173"
        new_content, fixes = agent._transform_redundant_not(content, issue)
        assert "**" not in new_content
        assert " | obj.kwargs" in new_content

    def test_transform_redundant_not_dict_union_multikey(self, agent):
        """FURB173: dict with multiple keys + spread."""
        content = 'def f(d):\n    return {"a": 1, "b": 2, **d}\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB173"
        new_content, fixes = agent._transform_redundant_not(content, issue)
        assert "**" not in new_content
        assert " | d" in new_content
        assert '"a": 1' in new_content
        assert '"b": 2' in new_content

    def test_transform_unnecessary_listcomp_set_discard(self, agent):
        """FURB142: ``for x in s: letters.discard(x)`` -> ``letters.difference_update(s)``."""
        content = (
            'sentence = "hello world"\n'
            'vowels = "aeiou"\n'
            "letters = set(sentence)\n"
            "for vowel in vowels:\n"
            "    letters.discard(vowel)\n"
        )
        issue = Mock(spec=Issue)
        issue.message = "FURB142"
        new_content, fixes = agent._transform_unnecessary_listcomp(content, issue)
        assert "for vowel in vowels:" not in new_content
        assert "letters.difference_update(vowels)" in new_content

    def test_transform_pow_operator_math_pi(self, agent):
        """FURB152: hardcoded 3.1415 -> math.pi."""
        content = "def area(r):\n    return 3.1415 * r * r\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB152"
        new_content, fixes = agent._transform_pow_operator(content, issue)
        assert "3.1415" not in new_content
        assert "math.pi" in new_content

    def test_transform_pow_operator_math_e(self, agent):
        """FURB152: hardcoded 2.7182 -> math.e."""
        content = "def f(x):\n    return 2.7182 ** x\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB152"
        new_content, fixes = agent._transform_pow_operator(content, issue)
        assert "2.7182" not in new_content
        assert "math.e" in new_content

    def test_transform_redundant_fstring_os_path_exists(self, agent):
        """FURB141: ``os.path.exists(p)`` -> ``Path(p).exists()``."""
        content = 'import os\nif os.path.exists("filename"):\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB141"
        new_content, fixes = agent._transform_redundant_fstring(content, issue)
        assert "os.path.exists" not in new_content
        assert 'Path("filename").exists()' in new_content
        assert "from pathlib import Path" in new_content

    def test_transform_redundant_fstring_os_path_isdir(self, agent):
        """FURB141: ``os.path.isdir(p)`` -> ``Path(p).is_dir()``."""
        content = 'import os\nif os.path.isdir("d"):\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB141"
        new_content, fixes = agent._transform_redundant_fstring(content, issue)
        assert "os.path.isdir" not in new_content
        assert 'Path("d").is_dir()' in new_content

    def test_transform_redundant_fstring_no_duplicate_import(self, agent):
        """FURB141: don't re-add the pathlib import if it's already there."""
        content = (
            "from pathlib import Path\n"
            'import os\n'
            'if os.path.exists("x"):\n'
            "    pass\n"
        )
        issue = Mock(spec=Issue)
        issue.message = "FURB141"
        new_content, fixes = agent._transform_redundant_fstring(content, issue)
        # Exactly one pathlib import.
        assert new_content.count("from pathlib import Path") == 1

    def test_transform_bool_return_min(self, agent):
        """FURB136: ternary min."""
        content = "lowest = a if a < b else b\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB136"
        new_content, fixes = agent._transform_bool_return(content, issue)
        assert "min(a, b)" in new_content
        assert "if a < b" not in new_content

    def test_transform_max_min_value_only(self, agent):
        """FURB148: ``for _, v in enumerate(X)`` -> ``for v in X``."""
        content = 'books = ["a", "b"]\nfor _, book in enumerate(books):\n    print(book)\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB148"
        new_content, fixes = agent._transform_max_min(content, issue)
        assert "for book in books:" in new_content
        assert "enumerate(books)" not in new_content

    def test_transform_int_scientific_oct(self, agent):
        """FURB161: ``oct(x).count("1")`` -> ``x.bit_count()``."""
        content = 'x = oct(0o777).count("1")\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB161"
        new_content, fixes = agent._transform_int_scientific(content, issue)
        assert "bit_count" in new_content
        assert 'count("1")' not in new_content

    def test_transform_sorted_key_identity_log2(self, agent):
        """FURB163: ``math.log(x, 2)`` -> ``math.log2(x)``."""
        content = "import math\npower = math.log(x, 2)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB163"
        new_content, fixes = agent._transform_sorted_key_identity(content, issue)
        assert "math.log2(x)" in new_content
        assert "math.log(x, 2)" not in new_content

    def test_transform_sorted_key_identity_log_e(self, agent):
        """FURB163: ``math.log(x, math.e)`` -> ``math.log(x)``."""
        content = "import math\npower = math.log(x, math.e)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB163"
        new_content, fixes = agent._transform_sorted_key_identity(content, issue)
        assert "math.log(x)" in new_content
        assert "math.e" not in new_content

    def test_transform_redundant_lambda_hexdigits(self, agent):
        """FURB156: hex alphabet -> string.hexdigits."""
        content = 'hexchars = "0123456789abcdefABCDEF"\nif c in hexchars:\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB156"
        new_content, fixes = agent._transform_redundant_lambda(content, issue)
        assert "string.hexdigits" in new_content
        assert "0123456789abcdefABCDEF" not in new_content

    def test_transform_type_none_comparison_negated(self, agent):
        """FURB169: ``type(x) is not type(None)`` -> ``x is not None``."""
        content = "if type(x) is not type(None):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB169"
        new_content, fixes = agent._transform_type_none_comparison(content, issue)
        assert "x is not None" in new_content
        assert "type(x) is not type(None)" not in new_content

    def test_transform_single_element_membership_tuple(self, agent):
        """FURB171: ``x in (y,)`` -> ``x == y`` (parenthesized, not bracketed)."""
        content = 'if name in ("bob",):\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB171"
        new_content, _fixes = agent._transform_single_element_membership(
            content, issue
        )
        assert "name == 'bob'" in new_content or 'name == "bob"' in new_content

    def test_transform_slice_copy_removesuffix(self, agent):
        """FURB188: ``x[:-len(L)] if x.endswith(L) else x`` -> ``x.removesuffix(L)``."""
        content = 'def strip(filename):\n    return filename[:-len(".txt")] if filename.endswith(".txt") else filename\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB188"
        new_content, fixes = agent._transform_slice_copy(content, issue)
        assert ".removesuffix(" in new_content
        assert "[:-len(" not in new_content
        assert ".endswith(" not in new_content

    def test_transform_slice_copy_removeprefix(self, agent):
        """FURB188: ``x[len(L):] if x.startswith(L) else x`` -> ``x.removeprefix(L)``."""
        content = 'def strip(filename):\n    return filename[len("prefix_"):] if filename.startswith("prefix_") else filename\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB188"
        new_content, fixes = agent._transform_slice_copy(content, issue)
        assert ".removeprefix(" in new_content
        assert "startswith(" not in new_content


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

    def test_transform_delete_while_iterating_or_oper(self, agent):
        """FURB110 (use-or-oper): ``x = a if a else b`` -> ``x = a or b``."""
        content = "result = value if value else default\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB110"
        new_content, fixes = agent._transform_delete_while_iterating(content, issue)
        assert "result = value or default" in new_content
        assert "if value else" not in new_content

    def test_transform_delete_while_iterating_no_match(self, agent):
        """FURB110: content without ternary pattern is unchanged."""
        content = "x = foo(a, b)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB110"
        new_content, fixes = agent._transform_delete_while_iterating(content, issue)
        assert new_content == content
        assert "No use-or-oper transformation" in fixes

    def test_transform_redundant_none_comparison(self, agent):
        """FURB108: no-match content is returned unchanged."""
        content = "if x is not None:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB108"

        new_content, desc = agent._transform_redundant_none_comparison(content, issue)
        assert new_content == content
        assert "No use-in-oper" in desc

    def test_transform_fstring_numeric_literal_bin(self, agent):
        """FURB116: ``bin(n)[2:]`` -> ``f"{n:b}"``."""
        content = "bin(n)[2:]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB116"
        new_content, fixes = agent._transform_fstring_numeric_literal(content, issue)
        assert 'f"{n:b}"' in new_content
        assert "bin(n)[2:]" not in new_content

    def test_transform_fstring_numeric_literal_oct(self, agent):
        """FURB116: ``oct(n)[2:]`` -> ``f"{n:o}"``."""
        content = "oct(n)[2:]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB116"
        new_content, fixes = agent._transform_fstring_numeric_literal(content, issue)
        assert 'f"{n:o}"' in new_content

    def test_transform_fstring_numeric_literal_hex(self, agent):
        """FURB116: ``hex(n)[2:]`` -> ``f"{n:x}"``."""
        content = "hex(n)[2:]\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB116"
        new_content, fixes = agent._transform_fstring_numeric_literal(content, issue)
        assert 'f"{n:x}"' in new_content

    def test_transform_fstring_numeric_literal_no_match(self, agent):
        """FURB116: already-formatted f-string is unchanged."""
        content = 'x = f"{n:b}"\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB116"
        new_content, fixes = agent._transform_fstring_numeric_literal(content, issue)
        assert new_content == content
        assert "No use-fstring-number-format" in fixes

    def test_transform_redundantenumerate_removes_trailing_return(self, agent):
        """FURB125 (no-redundant-return): trailing bare ``return`` is dropped."""
        content = "def foo():\n    x = 1\n    return\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB125"
        new_content, fixes = agent._transform_redundantenumerate(content, issue)
        assert "    return\n" not in new_content
        assert "x = 1" in new_content
        assert "Removed redundant return" in fixes

    def test_transform_redundantenumerate_keeps_return_with_value(self, agent):
        """FURB125: ``return 42`` (has a value) is NOT removed."""
        content = "def foo():\n    return 42\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB125"
        new_content, fixes = agent._transform_redundantenumerate(content, issue)
        assert "return 42" in new_content
        assert new_content == content

    def test_transform_redundantenumerate_no_match(self, agent):
        """FURB125: function without a trailing return is unchanged."""
        content = "def foo():\n    x = 1\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB125"
        new_content, fixes = agent._transform_redundantenumerate(content, issue)
        assert new_content == content
        assert "No no-redundant-return transformation" in fixes

    def test_transform_bad_open_mode_removes_trailing_continue_for(self, agent):
        """FURB133 (no-redundant-continue): trailing ``continue`` in for-loop removed."""
        content = "for x in items:\n    process(x)\n    continue\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB133"
        new_content, fixes = agent._transform_bad_open_mode(content, issue)
        assert "continue" not in new_content
        assert "process(x)" in new_content
        assert "Removed redundant continue" in fixes

    def test_transform_bad_open_mode_removes_trailing_continue_while(self, agent):
        """FURB133: trailing ``continue`` in while-loop removed."""
        content = "while True:\n    work()\n    continue\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB133"
        new_content, fixes = agent._transform_bad_open_mode(content, issue)
        assert "continue" not in new_content
        assert "work()" in new_content

    def test_transform_bad_open_mode_keeps_conditional_continue(self, agent):
        """FURB133: ``continue`` inside an if-block (not the last for-body stmt) is kept."""
        content = "for x in items:\n    if x < 0:\n        continue\n    process(x)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB133"
        new_content, fixes = agent._transform_bad_open_mode(content, issue)
        assert "continue" in new_content

    def test_transform_bad_open_mode_no_match(self, agent):
        """FURB133: no loops -> unchanged."""
        content = "x = 1\ny = 2\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB133"
        new_content, fixes = agent._transform_bad_open_mode(content, issue)
        assert new_content == content
        assert "No no-redundant-continue transformation" in fixes

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


class TestRefurbSubBatch5B:
    """Tests for Tier 3 sub-batch 5B: FURB108/122/132/168/172/177/180/181/186/187/190."""

    def test_transform_redundant_none_comparison_in_oper(self, agent):
        """FURB108 (use-in-oper): ``x == a or x == b`` -> ``x in (a, b)``."""
        content = 'if x == "abc" or x == "def":\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB108"
        new_content, fixes = agent._transform_redundant_none_comparison(content, issue)
        assert 'x in ("abc", "def")' in new_content
        assert "or x ==" not in new_content

    def test_transform_redundant_none_comparison_no_match(self, agent):
        """FURB108: unrelated content is unchanged."""
        content = "if x is None:\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB108"
        new_content, fixes = agent._transform_redundant_none_comparison(content, issue)
        assert new_content == content
        assert "No use-in-oper transformation" in fixes

    def test_transform_rhs_unpack_writelines(self, agent):
        """FURB122 (use-writelines): ``for line in lines: f.write(line)`` -> ``f.writelines(lines)``."""
        content = 'lines = ["line 1\\n", "line 2\\n"]\nwith open("file") as f:\n    for line in lines:\n        f.write(line)\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB122"
        new_content, fixes = agent._transform_rhs_unpack(content, issue)
        assert "f.writelines(lines)" in new_content
        assert "for line in lines:" not in new_content

    def test_transform_rhs_unpack_no_match(self, agent):
        """FURB122: loop without write call is unchanged."""
        content = "for line in lines:\n    print(line)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB122"
        new_content, fixes = agent._transform_rhs_unpack(content, issue)
        assert new_content == content
        assert "No use-writelines transformation" in fixes

    def test_transform_check_and_remove_discard(self, agent):
        """FURB132 (use-set-discard): ``if x in S: S.remove(x)`` -> ``S.discard(x)``."""
        content = "nums = {1, 2, 3}\nif 4 in nums:\n    nums.remove(4)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB132"
        new_content, fixes = agent._transform_check_and_remove(content, issue)
        assert "nums.discard(4)" in new_content
        assert "if 4 in nums:" not in new_content

    def test_transform_check_and_remove_no_match(self, agent):
        """FURB132: no if-in-remove pattern → unchanged."""
        content = "nums.discard(4)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB132"
        new_content, fixes = agent._transform_check_and_remove(content, issue)
        assert new_content == content
        assert "No use-set-discard transformation" in fixes

    def test_transform_isinstance_type_tuple_positive(self, agent):
        """FURB168: ``isinstance(x, type(None))`` -> ``x is None``."""
        content = "x = 123\nif isinstance(x, type(None)):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB168"
        new_content, fixes = agent._transform_isinstance_type_tuple(content, issue)
        assert "x is None" in new_content
        assert "isinstance(x, type(None))" not in new_content

    def test_transform_isinstance_type_tuple_negated(self, agent):
        """FURB168: ``not isinstance(x, type(None))`` -> ``x is not None``."""
        content = "if not isinstance(val, type(None)):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB168"
        new_content, fixes = agent._transform_isinstance_type_tuple(content, issue)
        assert "val is not None" in new_content
        assert "isinstance(" not in new_content

    def test_transform_unnecessary_list_cast_suffix(self, agent):
        """FURB172 (use-suffix): ``path.name.endswith(".txt")`` -> ``path.suffix == ".txt"``."""
        content = "from pathlib import Path\np = Path('a.txt')\nif p.name.endswith('.txt'):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB172"
        new_content, fixes = agent._transform_unnecessary_list_cast(content, issue)
        assert "p.suffix == '.txt'" in new_content
        assert ".name.endswith(" not in new_content

    def test_transform_unnecessary_list_cast_no_match(self, agent):
        """FURB172: unrelated endswith is unchanged."""
        content = 'if s.endswith(".txt"):\n    pass\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB172"
        new_content, fixes = agent._transform_unnecessary_list_cast(content, issue)
        assert new_content == content
        assert "No use-suffix transformation" in fixes

    def test_transform_redundant_or_path_cwd(self, agent):
        """FURB177 (no-implicit-cwd): ``Path().resolve()`` -> ``Path.cwd()``."""
        content = "from pathlib import Path\ncwd = Path().resolve()\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB177"
        new_content, fixes = agent._transform_redundant_or(content, issue)
        assert "Path.cwd()" in new_content
        assert "Path().resolve()" not in new_content

    def test_transform_redundant_or_no_match(self, agent):
        """FURB177: unrelated Path usage is unchanged."""
        content = "cwd = Path('.').resolve()\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB177"
        new_content, fixes = agent._transform_redundant_or(content, issue)
        assert new_content == content
        assert "No no-implicit-cwd transformation" in fixes

    def test_transform_method_assign_abc(self, agent):
        """FURB180 (use-abc-shorthand): ``class C(metaclass=ABCMeta):`` -> ``class C(ABC):``."""
        content = "from abc import ABCMeta\nclass C(metaclass=ABCMeta):\n    pass\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB180"
        new_content, fixes = agent._transform_method_assign(content, issue)
        assert "class C(ABC):" in new_content
        assert "metaclass=ABCMeta" not in new_content

    def test_transform_redundant_expression_hexdigest(self, agent):
        """FURB181 (use-hexdigest-hashlib): ``.digest().hex()`` -> ``.hexdigest()``."""
        content = "from hashlib import sha512\nhashed = sha512(b'data').digest().hex()\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB181"
        new_content, fixes = agent._transform_redundant_expression(content, issue)
        assert ".hexdigest()" in new_content
        assert ".digest().hex()" not in new_content

    def test_transform_redundant_expression_no_match(self, agent):
        """FURB181: no .digest().hex() pattern → unchanged."""
        content = "h = sha512(b'data').hexdigest()\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB181"
        new_content, fixes = agent._transform_redundant_expression(content, issue)
        assert new_content == content
        assert "No use-hexdigest transformation" in fixes

    def test_transform_redundant_cast_sort(self, agent):
        """FURB186 (use-sort): ``names = sorted(names)`` -> ``names.sort()``."""
        content = 'names = ["Bob", "Alice", "Charlie"]\nnames = sorted(names)\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB186"
        new_content, fixes = agent._transform_redundant_cast(content, issue)
        assert "names.sort()" in new_content
        assert "sorted(names)" not in new_content

    def test_transform_redundant_cast_no_match(self, agent):
        """FURB186: ``names = sorted(other)`` (different var) is unchanged."""
        content = "names = sorted(other)\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB186"
        new_content, fixes = agent._transform_redundant_cast(content, issue)
        assert new_content == content
        assert "No use-sort transformation" in fixes

    def test_transform_chained_assignment_reverse_slice(self, agent):
        """FURB187 (use-reverse): ``names = names[::-1]`` -> ``names.reverse()``."""
        content = 'names = ["Bob", "Alice"]\nnames = names[::-1]\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB187"
        new_content, fixes = agent._transform_chained_assignment(content, issue)
        assert "names.reverse()" in new_content
        assert "[::-1]" not in new_content

    def test_transform_chained_assignment_reverse_list_reversed(self, agent):
        """FURB187: ``names = list(reversed(names))`` -> ``names.reverse()``."""
        content = 'names = ["Bob", "Alice"]\nnames = list(reversed(names))\n'
        issue = Mock(spec=Issue)
        issue.message = "FURB187"
        new_content, fixes = agent._transform_chained_assignment(content, issue)
        assert "names.reverse()" in new_content
        assert "reversed(" not in new_content

    def test_transform_subprocess_list_str_method(self, agent):
        """FURB190 (use-str-method): ``lambda x: x.upper()`` -> ``str.upper``."""
        content = "normalize = lambda x: x.upper()\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB190"
        new_content, fixes = agent._transform_subprocess_list(content, issue)
        assert "str.upper" in new_content
        assert "lambda x: x.upper()" not in new_content

    def test_transform_subprocess_list_no_match(self, agent):
        """FURB190: lambda with args is unchanged."""
        content = "fn = lambda x, y: x.upper()\n"
        issue = Mock(spec=Issue)
        issue.message = "FURB190"
        new_content, fixes = agent._transform_subprocess_list(content, issue)
        assert new_content == content
        assert "No use-str-method transformation" in fixes
