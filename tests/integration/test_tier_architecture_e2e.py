"""End-to-end integration test for the tier-1 (mechanical) auto-fix
architecture.

Exercises the tier-1 architecture against a real Python file with
multiple ty errors of different categories:

* ``unresolved-reference`` for ``time`` (tier 1, fixed by ty_imports)
* ``unsupported-operator`` for ``"x" in tool_name`` where
  ``tool_name: str | None`` (tier 1, fixed by ty_narrow)
* ``not-subscriptable`` for ``value["k"]`` where
  ``value: dict | None`` (tier 1, fixed by ty_narrow subscript)
* ``unresolved-attribute`` for ``name.lower()`` where
  ``name: str | None`` (no mechanical fix exists — left untouched)

Tier-1 fixers are applied directly so the test stays self-contained
without invoking the heavy ``crackerjack run`` command.

NOTE: this file previously also exercised the tier-3
(``IterativeFixAgent``/``tier3_factory``) wiring. That AI-dispatch
machinery was removed by the ai-fix-removal-extraction SDD plan
(Task 24b); the tier-3-specific tests/imports were removed from this
file accordingly, leaving only the tier-1 mechanical-fixer coverage
below.

Fixture structure: all error sites live at module top level (no
indentation, no enclosing expressions). This sidesteps two known
sharp edges in the narrow fixers:

* The mechanical rewrite drops leading whitespace, so indented
  code (e.g. inside a function body) would lose its indent.
* The subscript fixer's regex requires the LHS to be a *bare*
  identifier (``value["k"]``), not a more complex expression
  (``result_sub = value["k"]``) — those need LLM reasoning.

The tier-1 architecture and the post-fix AST/ty validation are what
this test exercises; the indentation and chained-expression cases are
covered separately by ``tests/tools/test_ty_narrow.py``.

Line-number accounting (original, pre-fix fixture):

    line 1  docstring
    line 3  from typing import Optional
    line 5  tool_name: Optional[str] = "default-tool"
    line 6  "x" in tool_name                  # tier-1 unsupported-operator
    line 8  value: Optional[dict] = {"k": "v"}
    line 9  value["k"]                        # tier-1 not-subscriptable
    line 11 name: Optional[str] = "World"
    line 12 name.lower()                     # tier-2/3 unresolved-attribute
    line 14 delay = time.sleep(0)            # tier-1 unresolved-reference

After ``apply_import_fix`` adds ``import time`` at line 4, all
subsequent lines shift by +1.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

from crackerjack.tools.ty_imports import (
    FixSite,
    fix_unresolved_references,
    resolve_symbol,
)
from crackerjack.tools.ty_narrow import (
    UnsupportedOperatorSite,
    find_in_operator_candidates,
    find_subscript_candidates,
    fix_not_subscriptable,
    fix_unsupported_operators,
)

# ---------------------------------------------------------------------------
# Constants — line numbers in the original fixture file
# ---------------------------------------------------------------------------

# Original (pre-fix) line numbers for the four ty-error sites.
_ORIG_LINE_TIME = 14  # ``delay = time.sleep(0)``
_ORIG_LINE_IN = 6  # ``result = "x" in tool_name``
_ORIG_LINE_SUBSCRIPT = 9  # ``result = value["k"]``


def _post_import_line(orig_line: int) -> int:
    """After ``import time`` is inserted at line 4, every line below
    it shifts by +1."""
    return orig_line + 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_file(tmp_path: Path) -> Path:
    """Write a small Python file containing four representative ty errors.

    Module-level layout with bare-identifier RHS for the narrow
    fixers — see module docstring.
    """
    target = tmp_path / "broken.py"
    target.write_text(
        '"""Fixture file with four ty errors of different categories."""\n'
        "\n"
        "from typing import Optional\n"
        "\n"
        'tool_name: Optional[str] = "default-tool"\n'
        '"x" in tool_name\n'
        "\n"
        'value: Optional[dict] = {"k": "v"}\n'
        'value["k"]\n'
        "\n"
        'name: Optional[str] = "World"\n'
        "name.lower()\n"
        "\n"
        "delay = time.sleep(0)  # unresolved-reference for `time`\n"
    )
    return target


@pytest.fixture
def no_tier3_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear MCP URLs so the factory uses the local fallback path."""
    monkeypatch.delenv("MAHAVISHNU_MCP_URL", raising=False)
    monkeypatch.delenv("SESSION_BUDDY_MCP_URL", raising=False)


def _apply_all_tier1_fixes(fixture_file: Path) -> str:
    """Apply all three mechanical tier-1 fixes in order.

    Returns the post-fix file content.
    """
    # Tier 1a: ty_imports — original line number.
    fix_unresolved_references(
        fixture_file,
        [FixSite(file=fixture_file, line=_ORIG_LINE_TIME, col=12, symbol="time")],
    )

    # Tier 1b: ty_narrow ``in`` — line shifts by +1 after the import.
    fix_unsupported_operators(
        fixture_file,
        [
            UnsupportedOperatorSite(
                file=fixture_file,
                line=_post_import_line(_ORIG_LINE_IN),
                col=18,
                operator="in",
                lhs_type='Literal["x"]',
                rhs_type="str | None",
            )
        ],
    )

    # Tier 1c: ty_narrow subscript — line also shifts by +1.
    fix_not_subscriptable(
        fixture_file,
        [
            (
                _post_import_line(_ORIG_LINE_SUBSCRIPT),
                "dict[str, str] | None",
            )
        ],
    )

    return fixture_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tier 1 orchestration: real file, four ty errors, three mechanically fixed
# ---------------------------------------------------------------------------


class TestTierArchitectureEndToEnd:
    """Drive the tier-1 mechanical-fixer architecture against a real file.

    Tier-1 fixers run directly (we don't shell out to ``crackerjack run``
    — too heavy for a unit-test). The ``unresolved-attribute`` site has
    no mechanical fix and is left untouched.
    """

    def test_tier1_fixes_three_errors_and_leaves_unresolved_attribute(
        self,
        fixture_file: Path,
        no_tier3_mcp: None,
    ) -> None:
        # --- Tier 1a: ty_imports for unresolved-reference on ``time`` ---
        time_site = FixSite(
            file=fixture_file,
            line=_ORIG_LINE_TIME,
            col=12,
            symbol="time",
        )
        resolved = resolve_symbol(time_site.symbol)
        assert resolved is not None
        assert resolved.module == "time"
        assert resolved.import_line == "import time"

        fixes_applied, unresolved_imports = fix_unresolved_references(
            fixture_file, [time_site]
        )
        assert fixes_applied == 1
        assert unresolved_imports == []

        content_after_imports = fixture_file.read_text(encoding="utf-8")
        assert "import time" in content_after_imports

        # --- Tier 1b: ty_narrow for unsupported-operator on ``in`` ---
        in_line = _post_import_line(_ORIG_LINE_IN)
        in_operator_site = UnsupportedOperatorSite(
            file=fixture_file,
            line=in_line,
            col=18,
            operator="in",
            lhs_type='Literal["x"]',
            rhs_type="str | None",
        )
        in_candidate = find_in_operator_candidates(
            content_after_imports,
            line=in_operator_site.line,
            operator=in_operator_site.operator,
            rhs_type=in_operator_site.rhs_type,
        )
        assert in_candidate is not None, (
            f"Could not find in-candidate at line {in_line} in:\n"
            f"{content_after_imports}"
        )
        assert in_candidate.var_name == "tool_name"
        assert in_candidate.default_value == '""'

        in_fixes, unresolved_in = fix_unsupported_operators(
            fixture_file, [in_operator_site]
        )
        assert in_fixes == 1
        assert unresolved_in == []

        content_after_in = fixture_file.read_text(encoding="utf-8")
        assert '"x" in (tool_name or "")' in content_after_in

        # --- Tier 1c: ty_narrow subscript for not-subscriptable ---
        sub_line = _post_import_line(_ORIG_LINE_SUBSCRIPT)
        sub_candidate = find_subscript_candidates(
            content_after_in,
            line=sub_line,
            rhs_type="dict[str, str] | None",
        )
        assert sub_candidate is not None, (
            f"Could not find subscript candidate at line {sub_line} in:\n"
            f"{content_after_in}"
        )
        assert sub_candidate.var_name == "value"
        assert sub_candidate.default_value == "{}"

        subscript_fixes, unresolved_sub = fix_not_subscriptable(
            fixture_file,
            [(sub_line, "dict[str, str] | None")],
        )
        assert subscript_fixes == 1
        assert unresolved_sub == []

        content_after_all_t1 = fixture_file.read_text(encoding="utf-8")
        assert '(value or {})["k"]' in content_after_all_t1

        # The ``name.lower()`` site was untouched by tier-1 — no
        # mechanical fix exists. It stays for human/manual handling.
        assert "name.lower()" in content_after_all_t1
        assert "(name or" not in content_after_all_t1  # narrow fixer untouched it

    def test_file_remains_valid_python_after_all_tier1_fixes(
        self,
        fixture_file: Path,
        no_tier3_mcp: None,
    ) -> None:
        """All three tier-1 fixes must produce syntactically valid Python.

        ``ast.parse`` raises ``SyntaxError`` on invalid code; we assert
        the file parses cleanly. If ty is on PATH we also run it as a
        real type check, but fall back to ``ast.parse`` otherwise.
        """
        source = _apply_all_tier1_fixes(fixture_file)

        # --- ast.parse gate (always available) ---
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(
                f"File is not valid Python after tier-1 fixes: {exc}\n"
                f"--- source ---\n{source}\n--- end source ---"
            )

        # --- Optional: real ty check if the binary is on PATH ---
        # We don't assert ty returns 0 — it may still report the
        # ``unresolved-attribute`` site (tier-2/3 territory). We do
        # assert the three tier-1 errors are gone.
        if shutil.which("ty") is None:
            return
        try:
            proc = subprocess.run(
                ["ty", "check", str(fixture_file), "--output-format", "concise"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return  # ty vanished between shutil.which and run

        ty_output = proc.stdout + proc.stderr
        assert "unresolved-reference" not in ty_output, (
            f"ty still reports unresolved-reference after tier-1:\n{ty_output}"
        )
        assert "unsupported-operator" not in ty_output, (
            f"ty still reports unsupported-operator after tier-1:\n{ty_output}"
        )
        assert "not-subscriptable" not in ty_output, (
            f"ty still reports not-subscriptable after tier-1:\n{ty_output}"
        )
