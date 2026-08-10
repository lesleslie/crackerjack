"""Tests for crackerjack.fixers.planning.

Ported from tests/unit/agents/test_planning_agent_fixes.py, keeping every
test -- all 25 exercise (a)-classified mechanical "Issue -> ChangeSpec"
construction (``_fix_import``, ``_apply_style_fix``, ``_fix_documentation``,
``_validate_change_spec``, ``_validate_fragment_syntax``,
``_determine_approach``, ``_generate_changes``), none touch dropped
``SubAgent``/delegator/debugger orchestration -- so nothing was dropped in
this port. Call sites are updated from ``PlanningAgent(str(project_root))``
instance methods to the new plain-function form in
``crackerjack.fixers.planning``, with ``project_path``/``project_root``
threaded explicitly where the ported function needs it (``_fix_import``,
``_fix_documentation``, ``_generate_changes``), and omitted where it
doesn't (``_apply_style_fix``, ``_validate_change_spec``,
``_validate_fragment_syntax``, ``_determine_approach``).

One new test is added (not present in the original suite):
``test_fix_name_defined_error_import_branch_is_dead_due_to_context_bug``,
which pins a pre-existing bug discovered while porting (see
``crackerjack/fixers/planning.py``'s module docstring for the full
writeup): ``_fix_name_defined_error``/``_fix_arg_type_error`` read
``context.get("file_content", "")``, but the ``context`` dict they actually
receive (built by ``_get_type_error_context``) never has a
``"file_content"`` key, so the "insert the missing import automatically"
branch is permanently unreachable and the function always falls back to a
plain ``# type: ignore`` comment. This fires on every call through this
path (not a rare edge case), which per Task 14's precedent makes it a
Critical finding. Preserved verbatim, not fixed, per CLAUDE.md Rule 7.
"""

from __future__ import annotations

from crackerjack.fixers import planning
from crackerjack.models.fix_plan import ChangeSpec
from crackerjack.models.issues import Issue, IssueType, Priority


def test_fix_import_adds_typing_alias_for_undefined_t(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "from __future__ import annotations\n\n"
        "def build() -> list[t.Any]:\n"
        "    return []\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F821 Undefined name `t`",
        file_path=str(target_file),
        line_number=3,
    )

    change = planning._fix_import(
        issue, target_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    assert "import typing as t" in change.new_code
    assert change.line_range == (1, 5)


def test_fix_import_reorders_future_import(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "import os\n"
        "from __future__ import annotations\n\n"
        "def build() -> None:\n"
        "    return None\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F404 `from __future__` imports must occur at the beginning of the file",
        file_path=str(target_file),
        line_number=2,
    )

    change = planning._fix_import(
        issue, target_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    assert change.new_code.startswith("from __future__ import annotations\nimport os")


def test_fix_import_suppresses_star_import_lint(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "from dhara.core.connection import *\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F403 `from dhara.core.connection import *` used; unable to detect undefined names",
        file_path=str(target_file),
        line_number=1,
    )

    change = planning._fix_import(
        issue, target_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    assert "# noqa: F403" in change.new_code


def test_apply_style_fix_rewrites_up031_percent_format(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text('msg = "%s %s" % (left, right)\n', encoding="utf-8")

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="UP031 Use format specifiers instead of percent format",
        file_path=str(target_file),
        line_number=1,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert change.new_code.startswith("msg = f")
    assert "%s" not in change.new_code
    assert "# noqa: UP031" not in change.new_code


def test_apply_style_fix_rewrites_up031_multiline_expression(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        'yield "finished %s, %d live objects, %d removed" % (\n'
        "    datetime.now(),\n"
        "    len(alive),\n"
        "    len(dead),\n"
        ")\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="UP031 Use format specifiers instead of percent format",
        file_path=str(target_file),
        line_number=1,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert change.line_range == (1, 5)
    assert change.new_code.startswith("yield f")
    assert "%s" not in change.new_code
    assert "%d" not in change.new_code
    assert "# noqa: UP031" not in change.new_code


def test_apply_style_fix_rewrites_bare_except(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="E722 Do not use bare `except`",
        file_path=str(target_file),
        line_number=3,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "except Exception:" in change.new_code


def test_apply_style_fix_rewrites_multiline_bare_except(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "try:\n"
        "    do_work()\n"
        "except:\n"
        "    pass\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="E722 Do not use bare `except`",
        file_path=str(target_file),
        line_number=3,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert change.line_range == (1, 4)
    assert "except Exception:" in change.new_code


def test_fix_import_adds_project_import_for_missing_symbol(tmp_path) -> None:
    project_root = tmp_path
    source_file = project_root / "src" / "config.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "class DependencyConfig:\n"
        "    pass\n",
        encoding="utf-8",
    )

    target_file = project_root / "consumer.py"
    target_file.write_text(
        "def build() -> DependencyConfig:\n"
        "    return DependencyConfig()\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F821 Undefined name `DependencyConfig`",
        file_path=str(target_file),
        line_number=1,
    )

    change = planning._fix_import(
        issue, target_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    assert "from src.config import DependencyConfig" in change.new_code


def test_fix_documentation_rewrites_broken_relative_link(tmp_path) -> None:
    project_root = tmp_path
    docs_dir = project_root / "docs" / "reference"
    docs_dir.mkdir(parents=True)

    source_file = docs_dir / "service-dependencies.md"
    source_file.write_text(
        "- [README](../README.md)\n",
        encoding="utf-8",
    )
    (project_root / "README.md").write_text("# Readme\n", encoding="utf-8")

    issue = Issue(
        type=IssueType.DOCUMENTATION,
        severity=Priority.MEDIUM,
        message="Broken link: ../README.md - File not found: ../README.md",
        file_path=str(source_file),
        line_number=1,
        details=["Target file: ../README.md"],
    )

    change = planning._fix_documentation(
        issue, source_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    assert "../../README.md" in change.new_code


def test_fix_documentation_strips_unresolved_broken_link(tmp_path) -> None:
    project_root = tmp_path
    docs_dir = project_root / "docs" / "guides"
    docs_dir.mkdir(parents=True)

    source_file = docs_dir / "operational-modes.md"
    source_file.write_text(
        "- [Configuration Reference](../reference/config.md) - Complete configuration options\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.DOCUMENTATION,
        severity=Priority.MEDIUM,
        message="Broken link: ../reference/config.md - File not found: ../reference/config.md",
        file_path=str(source_file),
        line_number=1,
        details=["Target file: ../reference/config.md"],
    )

    change = planning._fix_documentation(
        issue, source_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    assert "Configuration Reference" in change.new_code
    assert "(" not in change.new_code


def test_validate_change_spec_allows_documentation_link_edits() -> None:
    change = ChangeSpec(
        line_range=(1, 1),
        old_code="- [Configuration Reference](../reference/config.md) - Complete configuration options",
        new_code="- Configuration Reference - Complete configuration options",
        reason="Removed broken documentation link: ../reference/config.md",
    )

    assert planning._validate_change_spec(change) is change


def test_fix_import_adds_project_imports_for_all_undefined_all_exports(
    tmp_path,
) -> None:
    project_root = tmp_path
    core_dir = project_root / "oneiric" / "core"
    core_dir.mkdir(parents=True)

    (core_dir / "ulid_collision.py").write_text(
        "class CollisionError(Exception):\n"
        "    pass\n\n"
        "def generate_with_retry() -> str:\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    (core_dir / "ulid_resolution.py").write_text(
        "def export_registry() -> dict[str, dict]:\n"
        "    return {}\n\n"
        "def register_reference() -> None:\n"
        "    return None\n",
        encoding="utf-8",
    )

    target_file = core_dir / "ulid.py"
    target_file.write_text(
        '"""ULID module."""\n\n'
        "from __future__ import annotations\n\n"
        "__all__ = [\n"
        '    "generate_with_retry",\n'
        '    "CollisionError",\n'
        '    "export_registry",\n'
        '    "register_reference",\n'
        "]\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F822 Undefined name `generate_with_retry` in `__all__`",
        file_path=str(target_file),
        line_number=4,
    )

    change = planning._fix_import(
        issue, target_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    assert "from oneiric.core.ulid_collision import generate_with_retry" in change.new_code
    assert "from oneiric.core.ulid_collision import CollisionError" in change.new_code
    assert "from oneiric.core.ulid_resolution import export_registry" in change.new_code
    assert "from oneiric.core.ulid_resolution import register_reference" in change.new_code
    assert change.new_code.splitlines()[2] == "from __future__ import annotations"


def test_fix_import_keeps_future_import_first_when_adding_project_import(
    tmp_path,
) -> None:
    project_root = tmp_path
    (project_root / "src").mkdir(parents=True)
    (project_root / "src" / "config.py").write_text(
        "class DependencyConfig:\n"
        "    pass\n",
        encoding="utf-8",
    )

    target_file = project_root / "consumer.py"
    target_file.write_text(
        '"""Consumer module."""\n\n'
        "from __future__ import annotations\n\n"
        "def build() -> DependencyConfig:\n"
        "    return DependencyConfig()\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F821 Undefined name `DependencyConfig`",
        file_path=str(target_file),
        line_number=4,
    )

    change = planning._fix_import(
        issue, target_file.read_text(encoding="utf-8"), project_root
    )

    assert change is not None
    lines = change.new_code.splitlines()
    assert lines[2] == "from __future__ import annotations"


def test_generate_changes_keeps_complexity_issue_viable_without_ast_transform(
    tmp_path,
) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "async def get(key: str) -> str:\n"
        "    if key:\n"
        "        return key\n"
        "    return ''\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.MEDIUM,
        message="C901 `get` is too complex (11 > 10)",
        file_path=str(target_file),
        line_number=1,
    )

    changes = planning._generate_changes(
        issue,
        target_file.read_text(encoding="utf-8"),
        "refactor_for_clarity",
        project_root,
    )

    assert len(changes) == 1
    assert changes[0].line_range == (1, 1)
    assert changes[0].old_code == "async def get(key: str) -> str:"
    assert changes[0].new_code == "async def get(key: str) -> str:"
    assert "Complexity fallback" in changes[0].reason


def test_apply_style_fix_adds_targeted_noqa_for_known_rule(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "def run(value: str = Security()):\n"
        "    return value\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="B008 Do not perform function call `Security` in argument defaults",
        file_path=str(target_file),
        line_number=1,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "# noqa: B008" in change.new_code


def test_apply_style_fix_renames_unused_argument(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "def run(ctx):\n"
        "    return 1\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="Unused function argument: `ctx`",
        file_path=str(target_file),
        line_number=1,
        details=["code: ARG001"],
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "def run(_ctx):" in change.new_code
    assert "# noqa: ARG001" not in change.new_code


def test_validate_fragment_syntax_accepts_signature_parameter_fragment() -> None:
    assert planning._validate_fragment_syntax("    _ctx: typer.Context,")


def test_apply_style_fix_adds_exception_chaining_for_b904(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "try:\n"
        "    do_work()\n"
        "except ValueError as err:\n"
        "    raise RuntimeError('bad')\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="B904 Within an except clause, raise exceptions with raise ... from err",
        file_path=str(target_file),
        line_number=4,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "raise RuntimeError('bad') from err" in change.new_code
    assert "# noqa: B904" not in change.new_code


def test_apply_style_fix_adds_exception_chaining_for_multiline_b904(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "try:\n"
        "    do_work()\n"
        "except ValueError as err:\n"
        "    raise HTTPException(\n"
        "        status_code=401,\n"
        "        detail='Token verification failed',\n"
        "    )\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="B904 Within an except clause, raise exceptions with raise ... from err",
        file_path=str(target_file),
        line_number=4,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "from err" in change.new_code
    assert change.line_range == (4, 7)


def test_apply_style_fix_aliases_duplicate_import_for_f811(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "import os\n"
        "import os\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="F811 redefinition of unused `os` from line 1",
        file_path=str(target_file),
        line_number=2,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "import os as _os" in change.new_code
    assert "# noqa: F811" not in change.new_code


def test_apply_style_fix_renames_duplicate_function_for_f811(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "def main() -> None:\n"
        "    return None\n\n"
        "def main() -> None:\n"
        "    return None\n\n"
        'if __name__ == "__main__":\n'
        "    main()\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="F811 Redefinition of unused `main` from line 1: `main` redefined here",
        file_path=str(target_file),
        line_number=4,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "def main_cli() -> None:" in change.new_code
    assert "main_cli()" in change.new_code


def test_apply_style_fix_renames_duplicate_function_without_call_site_for_f811(
    tmp_path,
) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "async def health_check(request: object) -> object:\n"
        "    return request\n\n"
        "async def health_check() -> dict[str, str]:\n"
        '    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="F811 Redefinition of unused `health_check` from line 1",
        file_path=str(target_file),
        line_number=4,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "async def health_check_cli() -> dict[str, str]:" in change.new_code
    assert 'return {"status": "ok"}' in change.new_code


def test_apply_style_fix_aliases_conflicting_import_for_class_f811(
    tmp_path,
) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "from example.models import Foo, N8NError, Bar\n\n"
        "class N8NError(Exception):\n"
        "    pass\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="F811 redefinition of unused `N8NError` from line 1",
        file_path=str(target_file),
        line_number=3,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "N8NError as _N8NError" in change.new_code


def test_apply_style_fix_aliases_multiline_conflicting_import_for_class_f811(
    tmp_path,
) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "from example.models import (\n"
        "    Foo,\n"
        "    N8NError,\n"
        "    Bar,\n"
        ")\n\n"
        "class N8NError(Exception):\n"
        "    pass\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="F811 redefinition of unused `N8NError` from line 1",
        file_path=str(target_file),
        line_number=7,
    )

    change = planning._apply_style_fix(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "N8NError as _N8NError" in change.new_code
    assert "from example.models import (" in change.new_code


def test_determine_approach_routes_sim102_to_style_fix(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "if outer:\n"
        "    if inner:\n"
        "        return True\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.SECURITY,
        severity=Priority.MEDIUM,
        message="SIM102 Use a single `if` statement instead of nested `if` statements",
        file_path=str(target_file),
        line_number=1,
    )

    assert planning._determine_approach(issue, []) == "apply_style_fix"


def test_fix_name_defined_error_import_branch_is_dead_due_to_context_bug(
    tmp_path,
) -> None:
    """Pins a pre-existing bug discovered while porting (not introduced by
    this extraction, not previously flagged by Task 21's classification,
    which audited the (a)/(b) orchestration boundary rather than internal
    correctness). See ``crackerjack/fixers/planning.py``'s module docstring
    for the full writeup.

    ``_fix_type_annotation`` builds ``error_context`` via
    ``_get_type_error_context`` -- a dict that never has a "file_content"
    key -- and passes it through to ``_fix_name_defined_error`` under the
    parameter name ``context``. ``_fix_name_defined_error`` then calls
    ``context.get("file_content", "")``, always getting back ``""``, so the
    "detect an undefined name with a known-safe import spec, check if it's
    already imported, and insert the missing import automatically" branch
    is unreachable -- even for "operator", which has a real entry in
    ``crackerjack.services.import_resolution.SAFE_IMPORT_SPECS``. The
    function always falls through to the plain ``# type: ignore`` fallback
    instead of inserting ``import operator``.
    """
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "def combine(a, b):\n"
        "    return operator(a, b)\n",
        encoding="utf-8",
    )

    issue = Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message='Name "operator" is not defined  [name-defined]',
        file_path=str(target_file),
        line_number=2,
    )

    change = planning._fix_type_annotation(
        issue, target_file.read_text(encoding="utf-8")
    )

    assert change is not None
    assert "import operator" not in change.new_code
    assert "# type: ignore" in change.new_code
