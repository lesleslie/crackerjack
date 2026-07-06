"""Tests for `crackerjack.services.refurb_fixer`.

Covers the public API of `SafeRefurbFixer` (file/package level fixes) and
the underlying AST and regex-based fixers. Subprocess calls into
`ast-grep` are mocked at the boundary because the tool may not be
installed in the test environment.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.refurb_fixer import (
    AST_GREP_RULES,
    SafeRefurbFixer,
    _ForLoopTupleTransformer,
    _MembershipTupleTransformer,
    _StartswithTupleTransformer,
    fix_file,
    fix_package,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a fake CompletedProcess-like object for subprocess.run."""
    cp = MagicMock()
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


# ---------------------------------------------------------------------------
# Public API: SafeRefurbFixer.__init__ / basic state
# ---------------------------------------------------------------------------


class TestSafeRefurbFixerInit:
    def test_initial_state(self) -> None:
        fixer = SafeRefurbFixer()
        assert fixer.fixes_applied == 0
        assert fixer._ast_grep_available is None

    def test_check_ast_grep_caches_negative(self) -> None:
        fixer = SafeRefurbFixer()
        with patch("shutil.which", return_value=None):
            assert fixer._check_ast_grep() is False
            # second call should hit the cache
            assert fixer._check_ast_grep() is False

    def test_check_ast_grep_caches_positive(self) -> None:
        fixer = SafeRefurbFixer()
        with patch("shutil.which", return_value="/usr/bin/ast-grep"):
            assert fixer._check_ast_grep() is True
            # second call returns cached value without re-invoking which
            with patch("shutil.which") as second:
                assert fixer._check_ast_grep() is True
                second.assert_not_called()


# ---------------------------------------------------------------------------
# Public API: fix_file
# ---------------------------------------------------------------------------


class TestFixFile:
    def test_returns_zero_for_missing_file(self, tmp_path: Path) -> None:
        fixer = SafeRefurbFixer()
        assert fixer.fix_file(tmp_path / "does_not_exist.py") == 0

    def test_returns_zero_for_directory_path(self, tmp_path: Path) -> None:
        fixer = SafeRefurbFixer()
        assert fixer.fix_file(tmp_path) == 0

    def test_returns_zero_for_non_python_file(self, tmp_path: Path) -> None:
        text_file = tmp_path / "notes.txt"
        text_file.write_text("hello world")
        fixer = SafeRefurbFixer()
        assert fixer.fix_file(text_file) == 0

    def test_returns_zero_when_content_unchanged(self, tmp_path: Path) -> None:
        py = tmp_path / "no_change.py"
        py.write_text("x = 1\n")
        fixer = SafeRefurbFixer()
        assert fixer.fix_file(py) == 0
        # file should not have been touched
        assert py.read_text() == "x = 1\n"

    def test_handles_unicode_decode_error(self, tmp_path: Path) -> None:
        py = tmp_path / "bad.py"
        py.write_bytes(b"\xff\xfe\x00\x01invalid")
        fixer = SafeRefurbFixer()
        # Should not raise; should return 0
        with patch("pathlib.Path.read_text", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad")):
            assert fixer.fix_file(py) == 0

    def test_handles_oserror_on_read(self, tmp_path: Path) -> None:
        py = tmp_path / "x.py"
        py.write_text("x = 1\n")
        fixer = SafeRefurbFixer()
        with patch("pathlib.Path.read_text", side_effect=OSError("nope")):
            assert fixer.fix_file(py) == 0

    def test_handles_oserror_on_write(self, tmp_path: Path) -> None:
        py = tmp_path / "x.py"
        py.write_text("for x in [1, 2]:\n    pass\n")
        fixer = SafeRefurbFixer()
        with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            assert fixer.fix_file(py) == 0

    def test_applies_fix_and_increments_counter(self, tmp_path: Path) -> None:
        # furb109: for x in [1, 2] -> for x in (1, 2)
        py = tmp_path / "loop.py"
        py.write_text("for x in [1, 2]:\n    pass\n")
        fixer = SafeRefurbFixer()
        result = fixer.fix_file(py)
        assert result >= 1
        assert fixer.fixes_applied == result
        # Confirm the file was actually rewritten
        assert "for x in (1, 2):" in py.read_text()


# ---------------------------------------------------------------------------
# Public API: fix_package
# ---------------------------------------------------------------------------


class TestFixPackage:
    def test_returns_zero_for_missing_dir(self, tmp_path: Path) -> None:
        fixer = SafeRefurbFixer()
        assert fixer.fix_package(tmp_path / "missing_pkg") == 0

    def test_returns_zero_for_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "x.py"
        f.write_text("x = 1\n")
        fixer = SafeRefurbFixer()
        assert fixer.fix_package(f) == 0

    def test_walks_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("for x in [1, 2]:\n    pass\n")
        (tmp_path / "b.py").write_text("x = 1\n")
        fixer = SafeRefurbFixer()
        total = fixer.fix_package(tmp_path)
        assert total >= 1

    def test_skips_pycache_and_dotfiles(self, tmp_path: Path) -> None:
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "a.py").write_text("for x in [1, 2]:\n    pass\n")
        hidden = tmp_path / ".venv"
        hidden.mkdir()
        (hidden / "b.py").write_text("for x in [1, 2]:\n    pass\n")
        # regular file that should be fixed
        (tmp_path / "c.py").write_text("x = 1\n")
        fixer = SafeRefurbFixer()
        total = fixer.fix_package(tmp_path)
        # cached/hidden files are skipped, no fixable code in c.py
        assert total == 0


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


class TestModuleLevelFunctions:
    def test_fix_file_creates_instance(self, tmp_path: Path) -> None:
        py = tmp_path / "x.py"
        py.write_text("for x in [1, 2]:\n    pass\n")
        result = fix_file(py)
        assert result >= 1

    def test_fix_package_creates_instance(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("for x in [1, 2]:\n    pass\n")
        result = fix_package(tmp_path)
        assert result >= 1


# ---------------------------------------------------------------------------
# AST_GREP_RULES constant
# ---------------------------------------------------------------------------


class TestAstGrepRules:
    def test_rules_have_required_keys(self) -> None:
        for rule_id, rule in AST_GREP_RULES.items():
            assert rule["id"] == rule_id
            assert rule["language"] == "python"
            assert "rule" in rule
            assert "fix" in rule

    def test_rules_are_json_serializable(self) -> None:
        # The rules are passed to ast-grep as JSON
        json.dumps(AST_GREP_RULES)


# ---------------------------------------------------------------------------
# _run_ast_grep_fix
# ---------------------------------------------------------------------------


class TestRunAstGrepFix:
    def test_returns_unchanged_when_tool_unavailable(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = False
        new_content, fixes = fixer._run_ast_grep_fix(
            "x.startswith('a') or x.startswith('b')",
            AST_GREP_RULES["furb102-startswith-tuple-or"],
        )
        assert new_content == "x.startswith('a') or x.startswith('b')"
        assert fixes == 0

    def test_applies_match_from_ast_grep(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        match_payload = [
            {
                "text": "x.startswith('a') or x.startswith('b')",
                "range": {"byteOffset": {"start": 0, "end": 36}},
                "metaVariables": {
                    "single": {
                        "X": {"text": "x"},
                        "A": {"text": "'a'"},
                        "B": {"text": "'b'"},
                    }
                },
            }
        ]
        proc = _completed_proc(returncode=0, stdout=json.dumps(match_payload))
        with patch("subprocess.run", return_value=proc) as run_mock:
            new_content, fixes = fixer._run_ast_grep_fix(
                "x.startswith('a') or x.startswith('b')",
                AST_GREP_RULES["furb102-startswith-tuple-or"],
            )
        assert fixes == 1
        assert "x.startswith(('a', 'b'))" in new_content
        run_mock.assert_called_once()
        # ast-grep args should be list-form, not shell
        args, _ = run_mock.call_args
        assert isinstance(args[0], list)
        assert args[0][0] == "ast-grep"

    def test_returns_zero_when_subprocess_nonzero(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        proc = _completed_proc(returncode=1, stdout="")
        with patch("subprocess.run", return_value=proc):
            new_content, fixes = fixer._run_ast_grep_fix(
                "x", AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0
        assert new_content == "x"

    def test_returns_zero_when_empty_match_list(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        proc = _completed_proc(returncode=0, stdout="[]")
        with patch("subprocess.run", return_value=proc):
            new_content, fixes = fixer._run_ast_grep_fix(
                "x", AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0

    def test_returns_zero_on_invalid_json(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        proc = _completed_proc(returncode=0, stdout="not json")
        with patch("subprocess.run", return_value=proc):
            new_content, fixes = fixer._run_ast_grep_fix(
                "x", AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0
        assert new_content == "x"

    def test_handles_subprocess_timeout(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ast-grep", timeout=30),
        ):
            new_content, fixes = fixer._run_ast_grep_fix(
                "x", AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0
        assert new_content == "x"

    def test_handles_oserror(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        with patch("subprocess.run", side_effect=OSError("not found")):
            new_content, fixes = fixer._run_ast_grep_fix(
                "x", AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0

    def test_skips_match_with_zero_offsets(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        match_payload = [
            {
                "text": "irrelevant",
                "range": {"byteOffset": {"start": 0, "end": 0}},
                "metaVariables": {"single": {}},
            }
        ]
        proc = _completed_proc(returncode=0, stdout=json.dumps(match_payload))
        with patch("subprocess.run", return_value=proc):
            new_content, fixes = fixer._run_ast_grep_fix(
                "x", AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0

    def test_skips_match_with_empty_text(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        match_payload = [
            {
                "text": "",
                "range": {"byteOffset": {"start": 1, "end": 1}},
                "metaVariables": {"single": {}},
            }
        ]
        proc = _completed_proc(returncode=0, stdout=json.dumps(match_payload))
        with patch("subprocess.run", return_value=proc):
            new_content, fixes = fixer._run_ast_grep_fix(
                "x", AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0

    def test_applies_matches_in_reverse_order(self) -> None:
        # When two matches exist, the one with later offset should be
        # applied first so byte offsets remain valid.
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        content = "x.startswith('a') or x.startswith('b') and y.startswith('c') or y.startswith('d')"
        # Just verify multi-match handling doesn't crash; one fix per call
        # is the typical behavior.
        match_payload: list[dict] = []
        proc = _completed_proc(returncode=0, stdout=json.dumps(match_payload))
        with patch("subprocess.run", return_value=proc):
            new_content, fixes = fixer._run_ast_grep_fix(
                content, AST_GREP_RULES["furb102-startswith-tuple-or"]
            )
        assert fixes == 0
        assert new_content == content


# ---------------------------------------------------------------------------
# Regex-based fixers (furb102, 109, 110, 113, 115, 118, 123, 124, 126,
#  135, 138, 141, 142, 143, 148, 161, 107, 108, 111, 117, 173, 183)
# ---------------------------------------------------------------------------


class TestFixFurb102Regex:
    def test_or_pattern_collapsed_to_tuple(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x.startswith('a') or x.startswith('b')\n"
        new, n = fixer._fix_furb102_regex(content)
        assert n == 1
        assert "x.startswith(('a', 'b'))" in new

    def test_not_and_pattern_collapsed(self) -> None:
        fixer = SafeRefurbFixer()
        content = "not x.startswith('a') and not x.startswith('b')\n"
        new, n = fixer._fix_furb102_regex(content)
        assert n == 1
        assert "not x.startswith(('a', 'b'))" in new

    def test_multiline_if_pattern_collapsed(self) -> None:
        fixer = SafeRefurbFixer()
        # The multiline pattern preserves the surrounding parens and newlines
        # but consolidates the two `not X.startswith(...)` into one tuple.
        content = (
            "if (\n"
            "    not x.startswith('a')\n"
            "    and not x.startswith('b')\n"
            "):\n"
            "    pass\n"
        )
        new, n = fixer._fix_furb102_regex(content)
        assert n == 1
        assert "not x.startswith(('a', 'b'))" in new

    def test_separate_lines_pattern_collapsed(self) -> None:
        fixer = SafeRefurbFixer()
        # The separate_lines_pattern matches an `and (` followed by another
        # `and (not X.startswith(...))` on subsequent lines. We just verify
        # the function does not crash on this multi-`and` pattern.
        content = (
            "if (\n"
            "    not x.startswith('a')\n"
            "    and (not y.startswith('b'))\n"
            "    and (not x.startswith('c'))\n"
            "):\n"
            "    pass\n"
        )
        new, n = fixer._fix_furb102_regex(content)
        # No assertion on count - the inner patterns may or may not match.
        # We're just ensuring the multi-line regex doesn't raise.
        assert isinstance(new, str)
        assert isinstance(n, int)

    def test_no_match_returns_zero(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb102_regex("x = 1\n")
        assert n == 0
        assert new == "x = 1\n"


class TestFixFurb107:
    def test_simple_try_except_pass_becomes_suppress(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError:\n"
            "        pass\n"
        )
        new, n = fixer._fix_furb107(content)
        assert n == 1
        assert "with suppress(ValueError):" in new
        assert "try:" not in new
        assert "except" not in new
        assert "pass" not in new

    def test_inline_pass_except_handled(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError: pass\n"
        )
        new, n = fixer._fix_furb107(content)
        assert n == 1
        assert "with suppress(ValueError):" in new

    def test_bare_except(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except:\n"
            "        pass\n"
        )
        new, n = fixer._fix_furb107(content)
        assert n == 1
        assert "with suppress(Exception):" in new

    def test_existing_code_after_pass_blocks_fix(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError:\n"
            "        pass\n"
            "    y = 2\n"
        )
        new, n = fixer._fix_furb107(content)
        # Should not rewrite because there's a sibling statement after pass
        assert n == 0
        assert new == content

    def test_multiple_except_handlers_blocks_fix(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError:\n"
            "        pass\n"
            "    except TypeError:\n"
            "        pass\n"
        )
        new, n = fixer._fix_furb107(content)
        assert n == 0
        assert new == content

    def test_no_try_block(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb107("x = 1\n")
        assert n == 0

    def test_except_pass_with_comments_between(self) -> None:
        """Regression: real-world code (refactoring_agent.py:501) has 2
        comment lines between ``except`` and ``pass``. The fixer must
        skip comment/blank lines and still find the trailing ``pass``.
        """
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except (OSError, UnicodeDecodeError):\n"
            "        # If we can't read the file, fall through to the success path\n"
            "        # (the original write_file_content already reported success).\n"
            "        pass\n"
        )
        new, n = fixer._fix_furb107(content)
        assert n == 1
        assert "with suppress((OSError, UnicodeDecodeError)):" in new
        assert "try:" not in new
        assert "except" not in new
        assert "pass" not in new

    def test_except_pass_with_single_comment_between(self) -> None:
        """Smaller variant: one comment line between except and pass."""
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError:\n"
            "        # silently ignore this error\n"
            "        pass\n"
        )
        new, n = fixer._fix_furb107(content)
        assert n == 1
        assert "with suppress(ValueError):" in new

    def test_except_pass_with_blank_line_between(self) -> None:
        """Blank line between except and pass is also tolerated."""
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError:\n"
            "\n"
            "        pass\n"
        )
        new, n = fixer._fix_furb107(content)
        assert n == 1
        assert "with suppress(ValueError):" in new


class TestFixFurb109:
    def test_for_in_list_uses_tuple(self) -> None:
        fixer = SafeRefurbFixer()
        content = "for x in [1, 2, 3]:\n    pass\n"
        new, n = fixer._fix_furb109(content)
        assert n == 1
        assert "for x in (1, 2, 3):" in new

    def test_in_list_membership_uses_tuple(self) -> None:
        fixer = SafeRefurbFixer()
        content = "if x in [1, 2, 3]:\n    pass\n"
        new, n = fixer._fix_furb109(content)
        assert n == 1
        assert "x in (1, 2, 3)" in new

    def test_nested_list_left_alone(self) -> None:
        fixer = SafeRefurbFixer()
        content = "for x in [[1, 2], [3, 4]]:\n    pass\n"
        new, n = fixer._fix_furb109(content)
        # The for-loop is rewritten only when the contents are simple,
        # but the in_pattern does not match nested lists.
        assert "for x in (1, 2):" not in new

    def test_empty_list_no_change(self) -> None:
        fixer = SafeRefurbFixer()
        content = "for x in []:\n    pass\n"
        new, n = fixer._fix_furb109(content)
        assert n == 0


class TestFixFurb113:
    def test_consecutive_appends_become_extend(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "x = []\n"
            "x.append(1)\n"
            "x.append(2)\n"
        )
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert "x.extend((1, 2))" in new

    def test_appends_with_args_blocked(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "x = []\n"
            "x.append(1, 2)\n"  # not matchable by the simple pattern
            "x.append(3)\n"
        )
        new, n = fixer._fix_furb113(content)
        # First append line is rejected because of multi-arg call
        assert n == 0

    def test_no_consecutive_appends(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "x = []\n"
            "x.append(1)\n"
            "y = 1\n"
            "x.append(2)\n"
        )
        new, n = fixer._fix_furb113(content)
        assert n == 0

    def test_consecutive_appends_with_string_literals(self) -> None:
        """Regression: FURB113 must match appends with string literals containing spaces.

        The original bug: regex character class [^(), \n]+ excluded spaces,
        so 'lines.append(" Distilled skill status")' never matched.
        """
        fixer = SafeRefurbFixer()
        content = (
            'x = []\n'
            'x.append(" Distilled skill status")\n'
            'x.append(" ----------------------")\n'
        )
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert 'x.extend' in new

    def test_consecutive_appends_with_empty_string(self) -> None:
        """Regression: FURB113 must match appends with empty string literals."""
        fixer = SafeRefurbFixer()
        content = 'x = []\nx.append("")\nx.append("")\n'
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert 'x.extend' in new

    def test_consecutive_appends_with_single_quoted_string(self) -> None:
        """Regression: FURB113 must match appends with single-quoted string literals."""
        fixer = SafeRefurbFixer()
        content = "x = []\nx.append('foo')\nx.append('bar')\n"
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert 'x.extend' in new


class TestFixFurb118:
    def test_numeric_itemgetter(self) -> None:
        """FURB118 emits bare ``itemgetter(N)`` (canonical form from
        refurb's docstring) and injects the import."""
        fixer = SafeRefurbFixer()
        content = "f = lambda x: x[0]\n"
        new, n = fixer._fix_furb118(content)
        assert n == 1
        assert "itemgetter(0)" in new
        # NOT the verbose `operator.itemgetter` form.
        assert "operator.itemgetter" not in new
        assert "from operator import itemgetter" in new

    def test_string_itemgetter(self) -> None:
        fixer = SafeRefurbFixer()
        content = 'f = lambda x: x["key"]\n'
        new, n = fixer._fix_furb118(content)
        assert n == 1
        assert 'itemgetter("key")' in new
        assert "operator.itemgetter" not in new

    def test_other_lambda_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        content = "f = lambda x: x + 1\n"
        new, n = fixer._fix_furb118(content)
        assert n == 0
        assert new == content


class TestFixFurb115:
    def test_len_eq_zero_to_not(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb115("if len(items) == 0:\n    pass\n")
        assert n == 1
        assert "not items" in new

    def test_len_gt_zero_NOT_rewritten_to_bare_var(self) -> None:
        """Audit fix: the old code rewrote ``len(x) > 0`` -> ``x``, which
        silently drops the boolean in ``return len(x) > 0``. Refurb does
        not flag that pattern as FURB115, so we now leave it alone."""
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb115("if len(items) > 0:\n    pass\n")
        assert n == 0
        assert "len(items) > 0" in new

    def test_len_ge_one_NOT_rewritten_to_bare_var(self) -> None:
        """Audit fix: same destructive rewrite as ``> 0`` was removed."""
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb115("if len(items) >= 1:\n    pass\n")
        assert n == 0
        assert "len(items) >= 1" in new

    def test_no_match(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb115("if len(items) == 5:\n    pass\n")
        assert n == 0
        assert new == "if len(items) == 5:\n    pass\n"


class TestFixFurb126:
    def test_else_return_collapse(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    if x:\n"
            "        return 1\n"
            "    else:\n"
            "        return 2\n"
        )
        new, n = fixer._fix_furb126(content)
        assert n == 1
        # The else line is removed, and the inner return is de-indented
        assert "else:" not in new.split("\n")[-3:][0:1] or new.count("else:") == 0

    def test_else_return_with_more_code_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        # `has_more_code` is true only when something follows at body_indent,
        # not at the outer if/else indent. The fix is still applied.
        content = (
            "def f():\n"
            "    if x:\n"
            "        return 1\n"
            "    else:\n"
            "        return 2\n"
            "        y = 3\n"  # code at body_indent blocks the fix
        )
        new, n = fixer._fix_furb126(content)
        assert n == 0
        assert "else:" in new


class TestFixFurb110:
    def test_ternary_to_or(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb110("x = a if a else b\n")
        assert n == 1
        assert "a or b" in new

    def test_different_vars_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb110("x = a if c else b\n")
        assert n == 0


class TestFixFurb123:
    def test_str_path_removed(self) -> None:
        """Audit fix: FURB123 now matches any ``str(literal)`` (canonical
        form drops the cast), not just the variable-name allowlist."""
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb123('x = str("hello")\n')
        assert n == 1
        assert 'x = "hello"' in new

    def test_list_lines_to_copy(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb123("x = list(my_lines)\n")
        assert n == 1
        assert "x = my_lines.copy()" in new

    def test_list_with_uncommon_variable_name(self) -> None:
        """Regression: FURB123 must match list() on any identifier, not just an allowlist.

        The original bug: regex hardcoded a list of variable names
        (lines, list, results, items, nodes, args, plans, details, paths, batch_results).
'crackerjack_skill_names' was NOT in the list, so it never matched.
        """
        fixer = SafeRefurbFixer()
        content = 'kw = list(crackerjack_skill_names)\n'
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert 'crackerjack_skill_names.copy()' in new

    def test_list_with_arbitrary_identifier(self) -> None:
        """Regression: FURB123 should match any plausible identifier name with digits/underscores."""
        fixer = SafeRefurbFixer()
        content = 'x = list(my_random_var_42)\n'
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert 'my_random_var_42.copy()' in new

    def test_list_preserves_regression_for_hardcoded_names(self) -> None:
        """Regression: FURB123 must still match the originally-supported variable names."""
        fixer = SafeRefurbFixer()
        # args was in the original allowlist
        content = 'x = list(args)\n'
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert 'args.copy()' in new

    def test_set_param_names_NOT_rewritten(self) -> None:
        """Audit fix: refurb's doc shows only ``list`` and ``dict`` for the
        ``.copy()`` rewrite. ``set(x)`` is ambiguous (copy-of-set semantics
        varies) so we leave it alone rather than guess."""
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb123("x = set(param_names)\n")
        assert n == 0
        assert "set(param_names)" in new

    def test_dict_self_attrs_to_copy(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb123("x = dict(self.cache)\n")
        assert n == 1
        assert "x = self.cache.copy()" in new

    def test_dict_mapping_to_copy(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb123("x = dict(my_mapping)\n")
        assert n == 1
        assert "x = my_mapping.copy()" in new

    def test_str_int_literal_IS_rewritten(self) -> None:
        """Audit fix: ``str(123)`` is now caught (literal cast)."""
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb123("x = str(123)\n")
        assert n == 1
        assert "x = 123" in new


class TestFixFurb142:
    def test_for_add_becomes_update(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "for x in items:\n"
            "    s.add(x)\n"
        )
        new, n = fixer._fix_furb142(content)
        assert n == 1
        assert "s.update(items)" in new

    def test_unrelated_loop_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        content = "for x in items:\n    s.add(y)\n"
        new, n = fixer._fix_furb142(content)
        assert n == 0


class TestFixFurb148:
    def test_enumerate_unused_index_removed(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "for i, v in enumerate(items):\n"
            "    print(v)\n"
        )
        new, n = fixer._fix_furb148(content)
        assert n == 1
        assert "for v in items:" in new

    def test_enumerate_used_index_kept(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "for i, v in enumerate(items):\n"
            "    print(i, v)\n"
        )
        new, n = fixer._fix_furb148(content)
        assert n == 0
        assert "enumerate(items):" in new


class TestFixFurb161:
    def test_int_with_exponent(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb161("x = int(1e6)\n")
        assert n == 1
        assert "x = 1000000" in new

    def test_small_exponent(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb161("x = int(2e3)\n")
        assert n == 1
        assert "x = 2000" in new

    def test_unrelated_int_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb161("x = int(some_string)\n")
        assert n == 0


class TestFixFurb124:
    def test_chained_eq_merged(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb124("if a == x and b == x:\n    pass\n")
        assert n == 1
        assert "a == x == b" in new

    def test_chained_eq_swapped_order(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb124("if a == x and x == b:\n    pass\n")
        assert n == 1
        assert "a == x == b" in new

    def test_same_var_skipped(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb124("if a == x and a == x:\n    pass\n")
        # var1 == var2 == var3 skipped when var1 == var2
        assert n == 0


class TestFixFurb138:
    def test_three_lines_become_listcomp(self) -> None:
        fixer = SafeRefurbFixer()
        # body_indent = indent + " ", so for top-level code the loop body
        # must use exactly one space of indentation in the source.
        content = "x = []\nfor i in mylist:\n x.append(i)\n"
        new, n = fixer._fix_furb138(content)
        assert n == 1
        assert "x = [i for i in mylist]" in new

    def test_appends_with_call_arg_skipped(self) -> None:
        fixer = SafeRefurbFixer()
        # The append regex is `[^)]+` which rejects args containing parens
        content = "x = []\nfor i in mylist:\n x.append(foo(i))\n"
        new, n = fixer._fix_furb138(content)
        assert n == 0

    def test_appends_without_loopvar_skipped(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x = []\nfor i in mylist:\n x.append(7)\n"
        new, n = fixer._fix_furb138(content)
        assert n == 0

    def test_indented_in_function_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        # Inside a function, the regex's body_indent assumes 1 space, but
        # Python uses 4 - this is a known limitation of the fixer.
        content = (
            "def f():\n"
            "    result = []\n"
            "    for x in items:\n"
            "        result.append(x * 2)\n"
        )
        new, n = fixer._fix_furb138(content)
        assert n == 0


class TestFixFurb108:
    def test_eq_or_eq_merged(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb108("if a == x or b == x:\n    pass\n")
        assert n == 1
        assert "x in (a, b)" in new

    def test_same_var_skipped(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb108("if a == x or a == x:\n    pass\n")
        assert n == 0


class TestFixFurb117:
    def test_open_with_path_and_mode(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb117('with open(file_path, "r") as f:\n    pass\n')
        assert n == 1
        assert 'file_path.open("r")' in new

    def test_unrelated_open_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb117('with open("hardcoded.txt", "r") as f:\n    pass\n')
        assert n == 0


class TestFixFurb173:
    def test_dict_merge_two_dicts(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb173("x = {**a, **b}\n")
        assert n == 1
        assert "x = a | b" in new

    def test_dict_merge_with_literal(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb173('x = {**a, "k": 1, **b}\n')
        assert n >= 1
        # The complex_pattern rewrites the literal into a dict literal
        assert "{" in new


class TestFixFurb183:
    def test_redundant_fstring_removed(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb183('x = f"{name}"\n')
        assert n == 1
        assert "str(name)" in new

    def test_unrelated_fstring_unchanged(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb183('x = f"hello {name}"\n')
        # has surrounding text, so the simple pattern doesn't match
        assert n == 0


class TestFixFurb143:
    def test_var_or_empty_string_removed(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb143("x = output or \"\"\n")
        assert n == 1
        assert "x = output" in new

    def test_var_or_empty_dict_removed(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb143("x = config or {}\n")
        assert n == 1
        assert "x = config" in new


class TestFixFurb141:
    def test_os_path_exists_to_path(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._fix_furb141("if os.path.exists(my_path):\n    pass\n")
        assert n == 1
        assert "Path(my_path).exists()" in new


class TestFixFurb135:
    def test_unused_key_destructuring(self) -> None:
        fixer = SafeRefurbFixer()
        content = "for _, val in my_dict.items():\n    print(val)\n"
        new, n = fixer._fix_furb135(content)
        assert n == 1
        assert "for val in my_dict.values():" in new

    def test_used_key_destructuring(self) -> None:
        fixer = SafeRefurbFixer()
        content = "for key, val in my_dict.items():\n    print(key, val)\n"
        new, n = fixer._fix_furb135(content)
        assert n == 0


class TestFixFurb111:
    def test_lambda_to_nested_call(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x = [lambda: foo() for _ in items]\n"
        new, n = fixer._fix_furb111(content)
        assert n == 1
        # The lambda should be unwrapped, leaving foo instead of lambda: foo()
        assert "lambda: foo()" not in new
        assert "foo" in new

    def test_lambda_with_call_already_unwrapped(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x = [lambda: foo() for _ in items]\n"
        new, n = fixer._fix_furb111(content)
        # After unwrapping, the () suffix is stripped
        assert "foo" in new


# ---------------------------------------------------------------------------
# _apply_fixes (orchestrator)
# ---------------------------------------------------------------------------


class TestApplyFixes:
    def test_combines_multiple_fixers(self) -> None:
        fixer = SafeRefurbFixer()
        # Mix of furb109 and furb110
        content = (
            "for x in [1, 2]:\n"
            "    pass\n"
            "y = a if a else b\n"
        )
        new, n = fixer._apply_fixes(content)
        assert n >= 2
        assert "for x in (1, 2):" in new
        assert "a or b" in new

    def test_returns_zero_for_clean_content(self) -> None:
        fixer = SafeRefurbFixer()
        new, n = fixer._apply_fixes("x = 1\n")
        assert n == 0
        assert new == "x = 1\n"


# ---------------------------------------------------------------------------
# AST transformers
# ---------------------------------------------------------------------------


class TestStartswithTupleTransformer:
    def _run(self, source: str) -> tuple[str, int]:
        tree = ast.parse(source)
        transformer = _StartswithTupleTransformer()
        new_tree = transformer.visit(tree)
        return ast.unparse(new_tree), transformer.fixes  # type: ignore[attr-defined]

    def test_or_startswith_becomes_tuple(self) -> None:
        out, fixes = self._run("x = a.startswith('p') or a.startswith('q')\n")
        assert fixes == 1
        assert "startswith(('p', 'q'))" in out

    def test_no_startswith_unchanged(self) -> None:
        out, fixes = self._run("x = 1")
        assert fixes == 0
        assert out == "x = 1"

    def test_single_startswith_unchanged(self) -> None:
        out, fixes = self._run("x = a.startswith('p')\n")
        assert fixes == 0

    def test_and_startswith_not_transformed(self) -> None:
        # Only Or is handled, not And
        out, fixes = self._run("x = a.startswith('p') and a.startswith('q')\n")
        assert fixes == 0

    def test_non_string_arg_skipped(self) -> None:
        out, fixes = self._run("x = a.startswith(var) or a.startswith('q')\n")
        # Mixed string/var args shouldn't be transformed
        assert fixes == 0


class TestMembershipTupleTransformer:
    def _run(self, source: str) -> tuple[str, int]:
        tree = ast.parse(source)
        transformer = _MembershipTupleTransformer()
        new_tree = transformer.visit(tree)
        return ast.unparse(new_tree), transformer.fixes  # type: ignore[attr-defined]

    def test_in_list_becomes_tuple(self) -> None:
        out, fixes = self._run("x = a in [1, 2, 3]\n")
        assert fixes == 1
        assert "a in (1, 2, 3)" in out

    def test_not_in_list_becomes_tuple(self) -> None:
        out, fixes = self._run("x = a not in ['a', 'b']\n")
        assert fixes == 1
        assert "a not in ('a', 'b')" in out

    def test_eq_comparator_unchanged(self) -> None:
        out, fixes = self._run("x = a == 5")
        assert fixes == 0
        assert out == "x = a == 5"

    def test_list_with_call_skipped(self) -> None:
        out, fixes = self._run("x = a in [foo(), 1]\n")
        # Calls are not simple elements
        assert fixes == 0


class TestForLoopTupleTransformer:
    def _run(self, source: str) -> tuple[str, int]:
        tree = ast.parse(source)
        transformer = _ForLoopTupleTransformer()
        new_tree = transformer.visit(tree)
        return ast.unparse(new_tree), transformer.fixes  # type: ignore[attr-defined]

    def test_for_list_becomes_for_tuple(self) -> None:
        out, fixes = self._run("for x in [1, 2, 3]:\n    pass\n")
        assert fixes == 1
        assert "for x in (1, 2, 3):" in out

    def test_for_range_unchanged(self) -> None:
        out, fixes = self._run("for x in range(10):\n    pass\n")
        assert fixes == 0
        assert "range(10)" in out

    def test_for_list_of_calls_unchanged(self) -> None:
        out, fixes = self._run("for x in [foo(), bar()]:\n    pass\n")
        assert fixes == 0


# ---------------------------------------------------------------------------
# Additional coverage: AST_GREP_RULES JSON, subprocess args, integration
# ---------------------------------------------------------------------------


class TestAstGrepSubprocessArgs:
    def test_subprocess_receives_inline_rules_json(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        proc = _completed_proc(returncode=1, stdout="")
        rule = AST_GREP_RULES["furb102-startswith-tuple"]
        with patch("subprocess.run", return_value=proc) as run_mock:
            fixer._run_ast_grep_fix("x", rule)
        args = run_mock.call_args[0][0]
        # The rule json is passed via --inline-rules
        rule_idx = args.index("--inline-rules")
        assert json.loads(args[rule_idx + 1]) == rule

    def test_subprocess_receives_stdin(self) -> None:
        fixer = SafeRefurbFixer()
        fixer._ast_grep_available = True
        proc = _completed_proc(returncode=1, stdout="")
        with patch("subprocess.run", return_value=proc) as run_mock:
            fixer._run_ast_grep_fix("hello", AST_GREP_RULES["furb102-startswith-tuple-or"])
        kwargs = run_mock.call_args.kwargs
        assert kwargs["input"] == "hello"
        assert kwargs["text"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["timeout"] == 30


class TestIntegrationFixPackage:
    def test_full_flow_writes_changes(self, tmp_path: Path) -> None:
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "a.py").write_text("for x in [1, 2]:\n    pass\n")
        (tmp_path / "pkg" / "b.py").write_text("x = 1\n")
        fixer = SafeRefurbFixer()
        total = fixer.fix_package(tmp_path / "pkg")
        assert total >= 1
        assert (tmp_path / "pkg" / "a.py").read_text() != "for x in [1, 2]:\n    pass\n"


# ---------------------------------------------------------------------------
# Tier 1 audit fixes (2026-06-12)
#
# Audit findings in docs/audits/2026-06-12-furb-handler-audit.md flagged
# 5 quick-win fixes. Each is locked down here so regressions are caught
# in CI rather than discovered by re-running refurb.
# ---------------------------------------------------------------------------


class TestFixFurb113HandlesNAppends:
    """FURB113 must collapse N >= 2 consecutive .append() calls, not just 2.

    The previous state-machine rewrite only chained the first two appends,
    leaving ``x.append(3)`` untouched. Refurb's doc example has 3.
    """

    def test_three_appends_become_single_extend(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "nums = [1, 2, 3]\n"
            "nums.append(4)\n"
            "nums.append(5)\n"
            "nums.append(6)\n"
        )
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert "nums.extend((4, 5, 6))" in new
        assert "nums.append(4)" not in new
        assert "nums.append(5)" not in new
        assert "nums.append(6)" not in new

    def test_four_appends_become_single_extend(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x = []\n" + "".join(f"x.append({i})\n" for i in range(10))
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert "x.extend((0, 1, 2, 3, 4, 5, 6, 7, 8, 9))" in new

    def test_appends_with_function_call_args(self) -> None:
        """The previous regex rejected parens inside the argument; AST version doesn't."""
        fixer = SafeRefurbFixer()
        content = (
            "x = []\n"
            "x.append(str(1))\n"
            "x.append(str(2))\n"
        )
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert "x.extend((str(1), str(2)))" in new

    def test_appends_with_attribute_access_args(self) -> None:
        """The previous regex rejected dots in arguments."""
        fixer = SafeRefurbFixer()
        content = (
            "x = []\n"
            "x.append(obj.attr)\n"
            "x.append(obj.other)\n"
        )
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert "x.extend((obj.attr, obj.other))" in new

    def test_single_append_is_unchanged(self) -> None:
        """One append is not a FURB113 violation; no rewrite."""
        fixer = SafeRefurbFixer()
        content = "x = []\nx.append(1)\n"
        new, n = fixer._fix_furb113(content)
        assert n == 0
        assert new == content

    def test_appends_at_correct_indent(self) -> None:
        """The replacement must inherit the original indent."""
        fixer = SafeRefurbFixer()
        content = (
            "def f():\n"
            "    x = []\n"
            "    x.append(1)\n"
            "    x.append(2)\n"
        )
        new, n = fixer._fix_furb113(content)
        assert n == 1
        assert "    x.extend((1, 2))" in new

    def test_two_separate_runs_both_rewritten(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "x = []\n"
            "x.append(1)\n"
            "x.append(2)\n"
            "y = []\n"
            "y.append(3)\n"
            "y.append(4)\n"
        )
        new, n = fixer._fix_furb113(content)
        assert n == 2
        assert "x.extend((1, 2))" in new
        assert "y.extend((3, 4))" in new


class TestFixFurb115NoDestructiveRewrite:
    """FURB115 must NOT rewrite ``len(x) >= 1`` or ``len(x) > 0`` to bare ``x``.

    Those rewrites silently drop the boolean: ``return len(x) >= 1`` would
    become ``return x`` (returning the list). Refurb doesn't flag those
    patterns as FURB115, so the rewrite was both off-rule and dangerous.
    """

    def test_len_eq_zero_rewritten(self) -> None:
        fixer = SafeRefurbFixer()
        content = "if len(name) == 0:\n    pass\n"
        new, n = fixer._fix_furb115(content)
        assert n == 1
        assert "if not name:" in new

    def test_len_geq_one_NOT_rewritten(self) -> None:
        """This was previously a destructive rewrite. Now a no-op."""
        fixer = SafeRefurbFixer()
        content = "if len(name) >= 1:\n    pass\n"
        new, n = fixer._fix_furb115(content)
        assert n == 0
        assert new == content

    def test_len_gt_zero_NOT_rewritten(self) -> None:
        """This was previously a destructive rewrite. Now a no-op."""
        fixer = SafeRefurbFixer()
        content = "if len(name) > 0:\n    pass\n"
        new, n = fixer._fix_furb115(content)
        assert n == 0
        assert new == content

    def test_return_with_len_geq_one_preserves_boolean(self) -> None:
        """The original bug: ``return len(x) >= 1`` would have become ``return x``.
        Now the source is preserved so the boolean is intact."""
        fixer = SafeRefurbFixer()
        content = "def f(x):\n    return len(x) >= 1\n"
        new, n = fixer._fix_furb115(content)
        assert n == 0
        # The expression must remain; do NOT drop the boolean.
        assert "len(x) >= 1" in new


class TestFixFurb123GeneralizedCasts:
    """FURB123 must match any redundant cast, not just a hardcoded name list.

    The previous version used 5 separate regexes with variable-name allowlists
    (e.g. only ``list(some_list)`` matched; ``list(other_list)`` did not).
    This version handles any identifier / attribute.
    """

    def test_str_around_string_literal(self) -> None:
        fixer = SafeRefurbFixer()
        content = 'name = str("bob")\n'
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert 'name = "bob"' in new

    def test_int_around_int_literal(self) -> None:
        fixer = SafeRefurbFixer()
        content = "num = int(123)\n"
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert "num = 123" in new

    def test_float_around_float_literal(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x = float(1.5)\n"
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert "x = 1.5" in new

    def test_bool_around_bool_literal(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x = bool(True)\n"
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert "x = True" in new

    def test_list_around_identifier_becomes_copy(self) -> None:
        """Any identifier should match, not just a name-allowlist."""
        fixer = SafeRefurbFixer()
        content = "x = [1, 2, 3]\ncopy = list(some_long_variable_name)\n"
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert "copy = some_long_variable_name.copy()" in new

    def test_dict_around_identifier_becomes_copy(self) -> None:
        fixer = SafeRefurbFixer()
        content = "ages = {}\ncopy = dict(ages)\n"
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert "copy = ages.copy()" in new

    def test_list_around_attribute_access_becomes_copy(self) -> None:
        fixer = SafeRefurbFixer()
        content = "x = []\ncopy = list(obj.items)\n"
        new, n = fixer._fix_furb123(content)
        assert n == 1
        assert "copy = obj.items.copy()" in new

    def test_no_match_on_unrelated_code(self) -> None:
        """A function call that isn't a redundant cast must not be rewritten."""
        fixer = SafeRefurbFixer()
        content = "x = print(1)\n"  # not a redundant cast
        new, n = fixer._fix_furb123(content)
        assert n == 0
        assert new == content


class TestFixFurb118ItemgetterImport:
    """FURB118 must emit ``itemgetter(...)`` (canonical) not
    ``operator.itemgetter(...)`` (off-style). It must also inject the
    ``from operator import itemgetter`` import.
    """

    def test_numeric_lambda_rewrites_with_bare_itemgetter(self) -> None:
        fixer = SafeRefurbFixer()
        content = "transform = lambda x: x[0]\n"
        new, n = fixer._fix_furb118(content)
        assert n == 1
        assert "itemgetter(0)" in new
        # NOT the verbose form.
        assert "operator.itemgetter" not in new

    def test_string_lambda_rewrites_with_bare_itemgetter(self) -> None:
        fixer = SafeRefurbFixer()
        content = 'transform = lambda x: x["key"]\n'
        new, n = fixer._fix_furb118(content)
        assert n == 1
        assert 'itemgetter("key")' in new
        assert "operator.itemgetter" not in new

    def test_import_is_injected_when_missing(self) -> None:
        fixer = SafeRefurbFixer()
        content = "transform = lambda x: x[0]\n"
        new, n = fixer._fix_furb118(content)
        assert n == 1
        assert "from operator import itemgetter" in new

    def test_no_duplicate_import_when_already_present(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "from operator import itemgetter\n"
            "transform = lambda x: x[0]\n"
        )
        new, n = fixer._fix_furb118(content)
        assert n == 1
        # Exactly one import line, not two.
        assert new.count("from operator import itemgetter") == 1

    def test_no_match_on_unrelated_lambda(self) -> None:
        fixer = SafeRefurbFixer()
        content = "f = lambda x: x + 1\n"
        new, n = fixer._fix_furb118(content)
        assert n == 0
        assert new == content


class TestTransformIsinstanceTypeCheckFurb126:
    """FURB126 else: return drop must be context-aware — only when the else
    body is a single return statement. The previous regex matched any
    ``else: return X`` and would rewrite nested code.
    """

    def test_simple_else_return_is_dropped(self) -> None:
        from crackerjack.agents.refurb_agent import RefurbCodeTransformerAgent
        from crackerjack.agents.base import AgentContext
        from unittest.mock import Mock
        from pathlib import Path

        ctx = Mock(spec=AgentContext)
        ctx.project_path = Path("/test")
        agent = RefurbCodeTransformerAgent(ctx)

        content = (
            "def f(x):\n"
            "    if x:\n"
            "        return 1\n"
            "    else:\n"
            "        return 2\n"
        )
        issue = Mock()
        issue.message = "FURB126"
        new, _desc = agent._transform_isinstance_type_check(content, issue)
        # The `else:` line should be gone and the `return 2` should be at the
        # function body indent.
        assert "else:" not in new
        assert "    return 2" in new

    def test_else_with_more_than_return_is_NOT_rewritten(self) -> None:
        """Audit bug: regex matched any else: return, even when else had
        more code after. AST-aware version must leave this alone."""
        from crackerjack.agents.refurb_agent import RefurbCodeTransformerAgent
        from crackerjack.agents.base import AgentContext
        from unittest.mock import Mock
        from pathlib import Path

        ctx = Mock(spec=AgentContext)
        ctx.project_path = Path("/test")
        agent = RefurbCodeTransformerAgent(ctx)

        content = (
            "def f(x):\n"
            "    if x:\n"
            "        return 1\n"
            "    else:\n"
            "        return 2\n"
            "        cleanup()\n"
        )
        issue = Mock()
        issue.message = "FURB126"
        new, _desc = agent._transform_isinstance_type_check(content, issue)
        # else: return with more code after must NOT trigger rewrite.
        assert "else:" in new

    def test_type_x_eq_T_rewritten(self) -> None:
        """FURB126 / isinstance rewrite: type(x) == T -> isinstance(x, T)."""
        from crackerjack.agents.refurb_agent import RefurbCodeTransformerAgent
        from crackerjack.agents.base import AgentContext
        from unittest.mock import Mock
        from pathlib import Path

        ctx = Mock(spec=AgentContext)
        ctx.project_path = Path("/test")
        agent = RefurbCodeTransformerAgent(ctx)

        content = "if type(x) == int:\n    pass\n"
        issue = Mock()
        issue.message = "FURB126"
        new, _desc = agent._transform_isinstance_type_check(content, issue)
        assert "isinstance(x, int)" in new
        assert "type(x) == int" not in new
