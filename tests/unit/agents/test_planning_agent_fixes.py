from __future__ import annotations

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.agents.planning_agent import PlanningAgent
from crackerjack.models.fix_plan import ChangeSpec


def test_fix_import_adds_typing_alias_for_undefined_t(tmp_path) -> None:
    project_root = tmp_path
    target_file = project_root / "module.py"
    target_file.write_text(
        "from __future__ import annotations\n\n"
        "def build() -> list[t.Any]:\n"
        "    return []\n",
        encoding="utf-8",
    )

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F821 Undefined name `t`",
        file_path=str(target_file),
        line_number=3,
    )

    change = agent._fix_import(issue, target_file.read_text(encoding="utf-8"))

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

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F404 `from __future__` imports must occur at the beginning of the file",
        file_path=str(target_file),
        line_number=2,
    )

    change = agent._fix_import(issue, target_file.read_text(encoding="utf-8"))

    assert change is not None
    assert change.new_code.startswith("from __future__ import annotations\nimport os")


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

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F821 Undefined name `DependencyConfig`",
        file_path=str(target_file),
        line_number=1,
    )

    change = agent._fix_import(issue, target_file.read_text(encoding="utf-8"))

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

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.DOCUMENTATION,
        severity=Priority.MEDIUM,
        message="Broken link: ../README.md - File not found: ../README.md",
        file_path=str(source_file),
        line_number=1,
        details=["Target file: ../README.md"],
    )

    change = agent._fix_documentation(issue, source_file.read_text(encoding="utf-8"))

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

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.DOCUMENTATION,
        severity=Priority.MEDIUM,
        message="Broken link: ../reference/config.md - File not found: ../reference/config.md",
        file_path=str(source_file),
        line_number=1,
        details=["Target file: ../reference/config.md"],
    )

    change = agent._fix_documentation(issue, source_file.read_text(encoding="utf-8"))

    assert change is not None
    assert "Configuration Reference" in change.new_code
    assert "(" not in change.new_code


def test_validate_change_spec_allows_documentation_link_edits() -> None:
    agent = PlanningAgent("/tmp/project")
    change = ChangeSpec(
        line_range=(1, 1),
        old_code="- [Configuration Reference](../reference/config.md) - Complete configuration options",
        new_code="- Configuration Reference - Complete configuration options",
        reason="Removed broken documentation link: ../reference/config.md",
    )

    assert agent._validate_change_spec(change) is change


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

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F822 Undefined name `generate_with_retry` in `__all__`",
        file_path=str(target_file),
        line_number=4,
    )

    change = agent._fix_import(issue, target_file.read_text(encoding="utf-8"))

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

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="F821 Undefined name `DependencyConfig`",
        file_path=str(target_file),
        line_number=4,
    )

    change = agent._fix_import(issue, target_file.read_text(encoding="utf-8"))

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

    agent = PlanningAgent(str(project_root))
    issue = Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.MEDIUM,
        message="C901 `get` is too complex (11 > 10)",
        file_path=str(target_file),
        line_number=1,
    )

    changes = agent._generate_changes(
        issue=issue,
        context={"file_content": target_file.read_text(encoding="utf-8")},
        approach="refactor_for_clarity",
    )

    assert len(changes) == 1
    assert changes[0].line_range == (1, 1)
    assert changes[0].old_code == "async def get(key: str) -> str:"
    assert changes[0].new_code == "async def get(key: str) -> str:"
    assert "Complexity fallback" in changes[0].reason
