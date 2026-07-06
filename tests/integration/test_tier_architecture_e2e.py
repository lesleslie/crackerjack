"""End-to-end integration test for the full auto-fix tier architecture.

Exercises the tier-1 + tier-2 + tier-3 architecture against a real
Python file with multiple ty errors of different categories:

* ``unresolved-reference`` for ``time`` (tier 1, fixed by ty_imports)
* ``unsupported-operator`` for ``"x" in tool_name`` where
  ``tool_name: str | None`` (tier 1, fixed by ty_narrow)
* ``not-subscriptable`` for ``value["k"]`` where
  ``value: dict | None`` (tier 1, fixed by ty_narrow subscript)
* ``unresolved-attribute`` for ``name.lower()`` where
  ``name: str | None`` (tier 2/3 — no mechanical fix exists)

The test demonstrates the architecture works, even though tier-2
(LLM one-shot) and tier-3 (worker pool / Claude subprocess) are
stubbed: tier-3 is wired via ``build_iterative_agent`` with mocked
env vars so the local fallback path is exercised (no LLM calls);
tier-1 fixers are applied directly so the test stays self-contained
without invoking the heavy ``crackerjack run`` command.

Fixture structure: all error sites live at module top level (no
indentation, no enclosing expressions). This sidesteps two known
sharp edges in the narrow fixers:

* The mechanical rewrite drops leading whitespace, so indented
  code (e.g. inside a function body) would lose its indent.
* The subscript fixer's regex requires the LHS to be a *bare*
  identifier (``value["k"]``), not a more complex expression
  (``result_sub = value["k"]``) — those need LLM reasoning.

The tier-1 architecture, the factory wiring, and the post-fix
AST/ty validation are what this test exercises; the indentation
and chained-expression cases are covered separately by
``tests/tools/test_ty_narrow.py``.

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

from crackerjack.agents.iterative_fix_agent import (
    InMemorySkillStore,
    IterativeFixAgent,
    LocalClaudeSubprocess,
)
from crackerjack.core.tier3_factory import build_iterative_agent
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
# Tier 3: factory returns a usable IterativeFixAgent on the local path
# ---------------------------------------------------------------------------


class TestTier3FactoryLocalPath:
    """``build_iterative_agent`` should yield a working agent when only
    the local fallback implementations are available (no Mahavishnu,
    no Session-Buddy). The agent would dispatch to a ``claude``
    subprocess — but the integration tests never let the subprocess
    actually run; the agent is built purely to prove the wiring."""

    def test_factory_returns_iterative_fix_agent(
        self, no_tier3_mcp: None, tmp_path: Path
    ) -> None:
        agent = build_iterative_agent(tmp_path)
        assert isinstance(agent, IterativeFixAgent)
        # Local fallback pool + in-memory store — both stamped on the
        # agent's attributes so callers can introspect the wiring.
        assert isinstance(agent.pool, LocalClaudeSubprocess)
        assert isinstance(agent.skill_store, InMemorySkillStore)

    def test_factory_skips_tier3_when_no_claude_binary(
        self, no_tier3_mcp: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When neither Mahavishnu nor the ``claude`` binary is on PATH,
        ``build_iterative_agent`` returns None — the caller must NOT
        attach tier-3 to the FixerCoordinator.
        """
        monkeypatch.setattr(
            "crackerjack.core.tier3_factory._has_claude_binary",
            lambda: False,
        )
        agent = build_iterative_agent(tmp_path)
        assert agent is None


# ---------------------------------------------------------------------------
# Tier 1 + tier 3 orchestration: real file, four ty errors, three fixed
# ---------------------------------------------------------------------------


class TestTierArchitectureEndToEnd:
    """Drive the full tier-1 + tier-3 architecture against a real file.

    Tier-1 fixers run directly (we don't shell out to ``crackerjack run``
    — too heavy for a unit-test). Tier-3 (the IterativeFixAgent
    built above) is wired into the architecture but is not invoked
    for the three mechanically-fixable errors; it would be invoked
    for the ``unresolved-attribute`` case which has no mechanical
    fix.

    The point of this test is to demonstrate the seams work, not to
    prove tier-3 can actually fix anything — tier-3 is stubbed here.
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

        # --- Tier 3 wiring: build the agent so the architecture's
        # tier-3 seam is exercised. We do NOT actually dispatch —
        # the subprocess isn't reachable from this test environment
        # in a meaningful way (we'd be paying LLM cost). The point
        # is to prove the factory yields the right wiring.
        agent = build_iterative_agent(fixture_file.parent)
        assert agent is not None
        assert isinstance(agent.pool, LocalClaudeSubprocess)
        assert isinstance(agent.skill_store, InMemorySkillStore)

        # The ``name.lower()`` site was untouched by tier-1 — no
        # mechanical fix exists. It stays for human/tier-2/tier-3
        # handling.
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

    def test_tier3_factory_wiring_is_consistent_with_tier1_fixes(
        self,
        fixture_file: Path,
        no_tier3_mcp: None,
    ) -> None:
        """Demonstrates the tier escalation boundary: tier-1 handles
        the three mechanically-fixable errors, leaving tier-3 to
        address the remaining ``unresolved-attribute``. We assert
        that the factory yields a usable agent and that tier-1
        mutations to the file are observable by the agent.
        """
        # Apply all three tier-1 fixers so the file is partially fixed.
        content_before_agent = _apply_all_tier1_fixes(fixture_file)

        # The architecture's tier-3 seam: build the same agent the
        # ai-fix hook would attach to its FixerCoordinator. Verify
        # the wiring is consistent with what tier-1 just did.
        agent = build_iterative_agent(fixture_file.parent)
        assert agent is not None

        # Agent's skill store starts empty — first encounter of any
        # signature will dispatch. After tier-1 succeeded, the
        # remaining diagnostic would be the ``unresolved-attribute``
        # site — that's exactly what tier-3 exists for.
        assert len(agent.skill_store) == 0

        # Tier-1 mutations are visible to the agent (same cwd, same
        # file path). This isn't a strong invariant — it's a sanity
        # check that we're not racing or working on stale state.
        current = fixture_file.read_text(encoding="utf-8")
        assert current == content_before_agent
        assert "import time" in current
        assert '"x" in (tool_name or "")' in current
        assert '(value or {})["k"]' in current
