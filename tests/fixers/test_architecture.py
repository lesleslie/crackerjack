"""Tests for crackerjack.fixers.architecture.

Ported from tests/unit/agents/test_architect_agent.py, keeping only the
cases that exercise real, deterministic TYPE_ERROR fixing logic and the
FixPlan/ChangeSpec applicator (``execute_fix_plan``/``_apply_plan_changes``/
``_find_matching_line``).

Dropped entirely (not ported), because the underlying methods no longer
exist in ``crackerjack.fixers.architecture`` -- see that module's docstring
for the full kept/dropped rationale:

- ``TestArchitectAgentInitialization``, ``TestArchitectAgentCanHandle`` --
  ``SubAgent``/coordinator dispatch plumbing (``__init__``,
  ``get_supported_types``, ``can_handle``).
- ``TestArchitectAgentPlanning`` (``plan_before_action``,
  ``_needs_external_specialist``) -- both branches of this dict-building
  planner are dropped: the ``COMPLEXITY``/``DRY_VIOLATION``
  ``external_specialist_guided`` branch has zero independent value once the
  coordinator is gone (explicitly named for dropping in this task's brief),
  and the ``internal_pattern_based`` branch is pure dict-construction with
  no fixing behavior of its own.
- ``TestArchitectAgentPatternRecommendations``,
  ``TestArchitectAgentDependenciesAndRisks``,
  ``TestArchitectAgentCachedPatterns`` -- these all test the same dropped
  dict-building planner helpers (``_get_specialist_approach``,
  ``_get_internal_approach``, ``_get_recommended_patterns``,
  ``_analyze_dependencies``, ``_identify_risks``, ``_get_validation_steps``,
  ``_get_cached_patterns_for_issue``); none of them perform a real fix.
- ``TestArchitectAgentExecution::test_analyze_and_fix_delegates_to_*`` --
  ``analyze_and_fix`` dispatches to other ``SubAgent`` instances
  (``RefactoringAgent``, ``FormattingAgent``); pure coordinator plumbing.
- ``TestArchitectAgentExecution::test_execute_with_plan_type_error`` and
  ``test_execute_with_plan_rejects_specialist_strategy`` -- both exercise
  ``execute_with_plan``, the method explicitly named for dropping in this
  task's brief (it is the method that refuses to act on the
  ``external_specialist_guided`` plan). Its assertion in the first case
  (``result is not None``) is too weak to be worth preserving anyway; real,
  much stronger coverage of the same underlying fix logic is added below as
  ``TestFixTypeErrorWithPlan``.
- ``TestArchitectAgentIntegration`` -- exercises ``plan_before_action``
  end-to-end (already dropped above) and ``get_supported_types``.

Kept and re-targeted at the new module (with mocking replaced by real
``tmp_path`` files/on-disk assertions per this task's real-behavior testing
requirement):

- ``test_execute_fix_plan_applies_type_error_plan_directly``
- ``test_execute_fix_plan_applies_formatting_plan_directly`` (re-targeted:
  since ``execute_fix_plan`` no longer special-cases ``"FORMATTING"`` at
  all -- see the module docstring -- this becomes a plain
  ``_apply_plan_changes`` case, folded into
  ``TestExecuteFixPlan::test_non_type_error_issue_types_apply_directly``)
- ``test_execute_fix_plan_applies_multiple_changes_cumulatively``
- ``test_execute_fix_plan_replaces_only_target_line_range``

New tests were added for:

- ``apply_type_error_fixes`` and its five sub-fixers (no direct-behavior
  tests existed in the original suite at all -- the only original coverage
  of this logic was the weak, mock-based
  ``test_execute_with_plan_type_error``, which only asserted
  ``result is not None``).
- ``fix_type_error_with_plan``, using real ``tmp_path`` files.
- The ``execute_fix_plan`` TYPE_ERROR fallback path (direct ``ChangeSpec``
  application fails -> falls back to ``fix_type_error_with_plan``), which
  had zero coverage in the original suite.
- The fuzzy line-drift recovery in ``_apply_plan_changes``/
  ``_find_matching_line``, which also had zero coverage in the original
  suite.
- Two preserved-quirk pins: ``_fix_path_str_conversion`` (permanent no-op)
  and ``_add_await_keyword`` (always produces syntactically invalid output
  for the only shape of line it ever fires on -- see the module docstring).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.fixers import architecture
from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "type": IssueType.TYPE_ERROR,
        "severity": Priority.MEDIUM,
        "message": "type error",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


def _plan(**kwargs: object) -> FixPlan:
    defaults: dict[str, object] = {
        "file_path": "/tmp/does-not-matter.py",
        "issue_type": "TYPE_ERROR",
        "risk_level": "low",
        "validated_by": "test",
        "rationale": "test rationale",
        "changes": [],
    }
    defaults.update(kwargs)
    return FixPlan(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# apply_type_error_fixes and its sub-fixers
# ---------------------------------------------------------------------------


class TestFixMissingTypingImports:
    def test_adds_new_typing_import_line(self) -> None:
        content = "def foo(x):\n    return x\n"
        fixed, fixes = architecture.apply_type_error_fixes(
            content, "Name 'Any' is not defined"
        )

        assert fixed == "from typing import Any\ndef foo(x):\n    return x\n"
        assert fixes == ["Added typing imports: Any"]

    def test_merges_into_existing_typing_import(self) -> None:
        content = "from typing import List\n\ndef foo(x):\n    return x\n"
        fixed, fixes = architecture.apply_type_error_fixes(content, "Dict is needed")

        assert fixed == "from typing import List, Dict\n\ndef foo(x):\n    return x\n"
        assert fixes == ["Added typing imports: Dict"]

    def test_no_duplicate_when_import_already_present(self) -> None:
        content = "from typing import Any\n\ndef foo(x):\n    return x\n"
        fixed, fixes = architecture.apply_type_error_fixes(
            content, "Any type expected here"
        )

        assert fixed == content
        assert fixes == []

    def test_no_fix_when_no_typing_keyword_in_message(self) -> None:
        content = "def foo(x):\n    return x\n"
        fixed, fixes = architecture.apply_type_error_fixes(content, "unrelated error")

        assert fixed == content
        assert fixes == []


class TestFixAnyBuiltinType:
    def test_fixes_lowercase_any_to_Any(self) -> None:
        content = "value: any\n"
        fixed, fixes = architecture.apply_type_error_fixes(
            content, "invalid builtin any usage"
        )

        assert fixed == "value: Any\n"
        assert fixes == ["Fixed `any` → `Any` in type annotations"]

    def test_no_fix_without_builtin_keyword(self) -> None:
        content = "value: any\n"
        fixed, fixes = architecture.apply_type_error_fixes(content, "any type issue")

        assert fixed == content
        assert fixes == []


class TestFixMissingAnnotationsType:
    def test_adds_none_return_annotation(self) -> None:
        content = "def foo(x):\n    pass\n"
        fixed, fixes = architecture.apply_type_error_fixes(
            content, "missing annotation for foo"
        )

        assert fixed == "def foo(x) -> None:\n    pass\n"
        assert fixes == ["Added missing type annotations"]

    def test_does_not_annotate_function_with_real_return(self) -> None:
        content = "def foo(x):\n    return x\n"
        fixed, fixes = architecture.apply_type_error_fixes(
            content, "missing annotation for foo"
        )

        assert fixed == content
        assert fixes == []


class TestFixPathStrConversion:
    """Pins the permanent no-op in ``_fix_path_str_conversion``.

    See the module docstring's "Preserved quirks" section, item 1: the
    original ``if`` body is a bare ``pass``, and ``content`` is returned
    unconditionally regardless of whether the condition matched.
    """

    def test_never_changes_content_even_when_trigger_words_present(self) -> None:
        content = "def foo(p: Path) -> str:\n    return str(p)\n"
        fixed, fixes = architecture.apply_type_error_fixes(
            content, "expected str, got Path in conversion"
        )

        assert fixed == content
        assert fixes == []

    def test_helper_is_a_direct_no_op(self) -> None:
        content = "anything at all"
        assert (
            architecture._fix_path_str_conversion(content, "path str error")
            == content
        )


class TestAddAwaitKeyword:
    """Pins a second preserved bug: the await insertion point is wrong.

    ``_add_await_keyword`` only ever fires on lines containing ``=`` (the
    ``"=" in line`` guard), i.e. assignment statements -- but it always
    splices ``"await "`` in at the start of the (unindented) statement,
    not immediately before the matched call. For every real match this
    produces syntactically invalid Python (``await result = x.start()``
    instead of ``result = await x.start()``). See the module docstring's
    "Preserved quirks" section.
    """

    def test_await_is_inserted_at_line_start_not_before_the_call(self) -> None:
        content = "result = obj.start()\n"
        fixed, fixes = architecture.apply_type_error_fixes(content, "missing await")

        assert fixed == "await result = obj.start()\n"
        assert fixes == ["Added `await` keyword before async calls"]

    def test_no_fix_when_line_already_has_await(self) -> None:
        content = "result = await obj.start()\n"
        fixed, fixes = architecture.apply_type_error_fixes(content, "missing await")

        assert fixed == content
        assert fixes == []

    def test_no_fix_without_await_or_coroutine_keyword(self) -> None:
        content = "result = obj.start()\n"
        fixed, fixes = architecture.apply_type_error_fixes(content, "unrelated error")

        assert fixed == content
        assert fixes == []


class TestApplyTypeErrorFixesPipeline:
    def test_no_fixes_for_unmatched_message(self) -> None:
        content = "def foo(x):\n    return x\n"
        fixed, fixes = architecture.apply_type_error_fixes(content, "totally unrelated")

        assert fixed == content
        assert fixes == []

    def test_multiple_fixers_can_fire_in_sequence(self) -> None:
        content = "value: any\n"
        fixed, fixes = architecture.apply_type_error_fixes(
            content, "Any is not defined; invalid builtin any usage"
        )

        # typing-import fixer runs first (adds `from typing import Any`),
        # then the any->Any builtin fixer runs against the *updated*
        # content (order matters -- both fixers see the same error_message
        # but chain content sequentially).
        assert fixed == "from typing import Any\nvalue: Any\n"
        assert fixes == [
            "Added typing imports: Any",
            "Fixed `any` → `Any` in type annotations",
        ]


# ---------------------------------------------------------------------------
# fix_type_error_with_plan
# ---------------------------------------------------------------------------


class TestFixTypeErrorWithPlan:
    def test_missing_file_path_fails(self) -> None:
        issue = _issue(file_path=None)

        result = architecture.fix_type_error_with_plan(issue, {})

        assert result.success is False
        assert result.confidence == 0.0
        assert "without file path" in result.remaining_issues[0]

    def test_file_not_found_fails(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.py"
        issue = _issue(file_path=str(missing), message="Any is not defined")

        result = architecture.fix_type_error_with_plan(issue, {})

        assert result.success is False
        assert "Could not read file" in result.remaining_issues[0]

    def test_no_applicable_fix_reports_recommendations(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("def foo(x):\n    return x\n")
        issue = _issue(file_path=str(target), message="totally unrelated error")

        result = architecture.fix_type_error_with_plan(issue, {})

        assert result.success is False
        assert result.confidence == 0.5
        assert result.remaining_issues == ["Type error: totally unrelated error"]
        assert result.recommendations
        assert target.read_text() == "def foo(x):\n    return x\n"

    def test_successful_fix_writes_real_file(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("def foo(x):\n    return x\n")
        issue = _issue(file_path=str(target), message="Name 'Any' is not defined")

        result = architecture.fix_type_error_with_plan(issue, {})

        assert result.success is True
        assert result.confidence == 0.5
        assert result.fixes_applied == ["Added typing imports: Any"]
        assert result.files_modified == [str(target)]
        assert target.read_text() == (
            "from typing import Any\ndef foo(x):\n    return x\n"
        )

    def test_plan_argument_is_accepted_but_unused(self, tmp_path: Path) -> None:
        """Pins that ``plan`` has no effect on the result (dead parameter,
        preserved verbatim from ``ArchitectAgent._fix_type_error_with_plan``
        -- see the module docstring)."""
        target = tmp_path / "module.py"
        target.write_text("def foo(x):\n    return x\n")
        issue = _issue(file_path=str(target), message="Name 'Any' is not defined")

        result_empty_plan = architecture.fix_type_error_with_plan(issue, {})
        target.write_text("def foo(x):\n    return x\n")
        result_other_plan = architecture.fix_type_error_with_plan(
            issue, {"strategy": "anything", "unrelated": 123}
        )

        assert result_empty_plan.fixes_applied == result_other_plan.fixes_applied


# ---------------------------------------------------------------------------
# execute_fix_plan / _apply_plan_changes / _find_matching_line
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExecuteFixPlan:
    async def test_no_changes_returns_failure(self) -> None:
        plan = _plan(changes=[])

        result = await architecture.execute_fix_plan(plan)

        assert result.success is False
        assert result.remaining_issues == ["Plan has no changes to apply"]

    async def test_type_error_direct_apply_success_does_not_use_fallback(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "type_error.py"
        file_path.write_text("def foo(x):\n    return x")

        plan = _plan(
            file_path=str(file_path),
            issue_type="TYPE_ERROR",
            changes=[
                ChangeSpec(
                    line_range=(1, 2),
                    old_code="def foo(x):\n    return x",
                    new_code="def foo(x: int) -> int:\n    return x",
                    reason="Add type annotations",
                ),
            ],
        )

        with patch.object(
            architecture,
            "fix_type_error_with_plan",
            side_effect=AssertionError(
                "TYPE_ERROR plans with a matching ChangeSpec should use direct "
                "application, not the heuristic fallback"
            ),
        ):
            result = await architecture.execute_fix_plan(plan)

        assert result.success is True
        assert file_path.read_text() == "def foo(x: int) -> int:\n    return x"
        assert result.fixes_applied == ["Change 0: Add type annotations"]
        assert result.files_modified == [str(file_path)]

    async def test_type_error_falls_back_to_heuristic_fix_on_mismatch(
        self, tmp_path: Path
    ) -> None:
        """When the planned ``old_code`` cannot be matched anywhere near the
        target line (so direct application fails), ``execute_fix_plan``
        falls back to ``fix_type_error_with_plan`` using ``plan.rationale``
        as the issue message -- this is the rewired equivalent of the
        original's ``self.execute_with_plan(issue, plan_dict)`` call,
        without resurrecting the dropped ``execute_with_plan`` router."""
        file_path = tmp_path / "needs_await.py"
        file_path.write_text("value = 1\nresult = obj.start()\n")

        plan = _plan(
            file_path=str(file_path),
            issue_type="TYPE_ERROR",
            rationale="missing await keyword",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 999",  # does not match file content
                    new_code="value = 2",
                    reason="bogus change that will never match",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is True
        assert result.fixes_applied == ["Added `await` keyword before async calls"]
        assert file_path.read_text() == "value = 1\nawait result = obj.start()\n"

    async def test_type_error_fallback_severity_is_high_past_line_30(
        self, tmp_path: Path
    ) -> None:
        """Pins the ``and``/``or`` pseudo-ternary severity quirk in the
        TYPE_ERROR fallback: ``Priority.HIGH`` when the failed change's
        first line is past 30, else ``Priority.MEDIUM``."""
        file_path = tmp_path / "module.py"
        file_path.write_text("x = 1\n")

        plan = _plan(
            file_path=str(file_path),
            issue_type="TYPE_ERROR",
            rationale="rationale text",
            changes=[
                ChangeSpec(
                    line_range=(50, 50),
                    old_code="does not exist",
                    new_code="new",
                    reason="bogus",
                ),
            ],
        )

        with patch.object(
            architecture,
            "fix_type_error_with_plan",
            return_value=FixResult(success=True, confidence=0.5),
        ) as mock_fix:
            await architecture.execute_fix_plan(plan)

        called_issue = mock_fix.call_args[0][0]
        assert called_issue.severity == Priority.HIGH
        assert called_issue.message == "rationale text"
        assert called_issue.file_path == str(file_path)

    async def test_non_type_error_issue_types_apply_directly(
        self, tmp_path: Path
    ) -> None:
        """``execute_fix_plan`` no longer special-cases ``COMPLEXITY``/
        ``FORMATTING``/``SECURITY`` by delegating to a different agent's
        ``execute_fix_plan`` -- every non-``TYPE_ERROR`` issue_type now goes
        straight through ``_apply_plan_changes``, same as the original's
        catch-all branch already did for any *other* issue_type. See the
        module docstring."""
        file_path = tmp_path / "formatting.py"
        file_path.write_text("a=1")

        plan = _plan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="a=1",
                    new_code="a = 1",
                    reason="Normalize spacing",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is True
        assert file_path.read_text() == "a = 1"
        assert result.fixes_applied == ["Change 0: Normalize spacing"]

    async def test_complexity_issue_type_no_longer_delegates_to_other_agent(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "complex.py"
        file_path.write_text("x=1")

        plan = _plan(
            file_path=str(file_path),
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="x=1",
                    new_code="x = 1",
                    reason="Normalize spacing",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is True
        assert file_path.read_text() == "x = 1"

    async def test_applies_multiple_changes_cumulatively(self, tmp_path: Path) -> None:
        file_path = tmp_path / "config.yaml"
        file_path.write_text("a: 1\nb: 2\nc: 3")

        plan = _plan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="a: 1",
                    new_code="a:\n  value: 1",
                    reason="Expand a",
                ),
                ChangeSpec(
                    line_range=(2, 2),
                    old_code="b: 2",
                    new_code="b:\n  value: 2",
                    reason="Expand b",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is True
        assert file_path.read_text() == "a:\n  value: 1\nb:\n  value: 2\nc: 3"
        assert result.fixes_applied == ["Change 0: Expand a", "Change 1: Expand b"]
        assert result.files_modified == [str(file_path)]

    async def test_replaces_only_target_line_range_for_repeated_old_code(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "repeated.py"
        file_path.write_text("value = 1\nvalue = 1")

        plan = _plan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(2, 2),
                    old_code="value = 1",
                    new_code="value = 2",
                    reason="Update second value",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is True
        assert file_path.read_text() == "value = 1\nvalue = 2"

    async def test_no_file_path_fails(self) -> None:
        plan = _plan(file_path="", issue_type="FORMATTING")
        plan.changes = [
            ChangeSpec(line_range=(1, 1), old_code="a", new_code="b", reason="r"),
        ]

        result = await architecture.execute_fix_plan(plan)

        assert result.success is False
        assert result.remaining_issues == ["No file path in plan"]

    async def test_unreadable_file_fails_with_exception_message(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "missing.py"
        plan = _plan(
            file_path=str(missing),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(line_range=(1, 1), old_code="a", new_code="b", reason="r"),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is False
        assert "Could not read file" in result.remaining_issues[0]


class TestFindMatchingLine:
    def test_finds_exact_match_within_window(self) -> None:
        lines = ["a", "b", "target line", "c", "d"]

        assert architecture._find_matching_line(lines, "target line", 1, window=5) == 2

    def test_finds_two_line_match(self) -> None:
        lines = ["a", "first part", "second part", "d"]

        result = architecture._find_matching_line(
            lines, "first part\nsecond part", 1, window=5
        )

        assert result == 1

    def test_returns_none_when_not_found(self) -> None:
        lines = ["a", "b", "c"]

        assert architecture._find_matching_line(lines, "nowhere to be found", 1) is None


@pytest.mark.asyncio
class TestApplyPlanChangesLineDrift:
    async def test_recovers_when_target_line_has_drifted_within_window(
        self, tmp_path: Path
    ) -> None:
        """A change planned against line 1 but whose ``old_code`` now sits
        at line 3 (content drifted) is still found and applied, via
        ``_find_matching_line``'s +/-10-line search."""
        file_path = tmp_path / "drifted.py"
        file_path.write_text("# comment 1\n# comment 2\ntarget_line = 1\n")

        plan = _plan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="target_line = 1",
                    new_code="target_line = 2",
                    reason="Drifted update",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is True
        assert file_path.read_text() == "# comment 1\n# comment 2\ntarget_line = 2\n"

    async def test_fails_when_no_match_found_anywhere_in_window(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "nomatch.py"
        file_path.write_text("a = 1\nb = 2\n")

        plan = _plan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="this code does not exist anywhere",
                    new_code="new",
                    reason="bogus",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is False
        assert "did not match target range" in result.remaining_issues[0]
        assert file_path.read_text() == "a = 1\nb = 2\n"

    async def test_invalid_line_range_fails(self, tmp_path: Path) -> None:
        file_path = tmp_path / "short.py"
        file_path.write_text("a = 1\n")

        plan = _plan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(10, 20),
                    old_code="a = 1",
                    new_code="a = 2",
                    reason="out of range",
                ),
            ],
        )

        result = await architecture.execute_fix_plan(plan)

        assert result.success is False
        assert "Invalid line range" in result.remaining_issues[0]
