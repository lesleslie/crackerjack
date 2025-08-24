import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.import_optimization_agent import ImportOptimizationAgent


@pytest.fixture
def agent_context():
    return AgentContext(
        project_path=Path("/tmp / test"),
        temp_dir=Path("/tmp / test"),
        config={},
    )


@pytest.fixture
def import_agent(agent_context):
    return ImportOptimizationAgent(agent_context)


@pytest.mark.asyncio
async def test_can_handle_import_error(import_agent) -> None:
    issue = Issue(
        id="test - 1",
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="Unused import: typing",
        file_path="test.py",
    )

    can_handle = await import_agent.can_handle(issue)
    assert can_handle > 0.0


@pytest.mark.asyncio
async def test_can_handle_dead_code(import_agent) -> None:
    issue = Issue(
        id="test - 2",
        type=IssueType.DEAD_CODE,
        severity=Priority.LOW,
        message="Unused import detected",
        file_path="test.py",
    )

    can_handle = await import_agent.can_handle(issue)
    assert can_handle > 0.0


@pytest.mark.asyncio
async def test_can_handle_by_message_content(import_agent) -> None:
    issue = Issue(
        id="test - 3",
        type=IssueType.FORMATTING,
        severity=Priority.LOW,
        message="redundant import statement found",
        file_path="test.py",
    )

    can_handle = await import_agent.can_handle(issue)
    assert can_handle > 0.0


@pytest.mark.asyncio
async def test_cannot_handle_unrelated_issue(import_agent) -> None:
    issue = Issue(
        id="test - 4",
        type=IssueType.SECURITY,
        severity=Priority.HIGH,
        message="SQL injection vulnerability",
        file_path="test.py",
    )

    can_handle = await import_agent.can_handle(issue)
    assert can_handle == 0.0


@pytest.mark.asyncio
async def test_analyze_file_with_mixed_imports(import_agent) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""import typing
from typing import Any, Dict
import json
from json import loads
""")
        temp_path = Path(f.name)

    try:
        analysis = await import_agent.analyze_file(temp_path)

        assert "typing" in analysis.mixed_imports
        assert "json" in analysis.mixed_imports
        assert len(analysis.mixed_imports) == 2

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_analyze_file_with_consistent_imports(import_agent) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""from typing import Any, Dict
from json import loads, dumps
from pathlib import Path
""")
        temp_path = Path(f.name)

    try:
        analysis = await import_agent.analyze_file(temp_path)

        assert len(analysis.mixed_imports) == 0

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_fix_issue_no_optimization_needed(import_agent) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""from typing import Any
from pathlib import Path
""")
        temp_path = Path(f.name)

    try:
        issue = Issue(
            id="test - 5",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.LOW,
            message="Check imports",
            file_path=str(temp_path),
        )

        result = await import_agent.fix_issue(issue)

        assert result.success is True
        assert result.confidence == 1.0
        assert "No import optimizations needed" in result.fixes_applied

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_fix_issue_with_mixed_typing_imports(import_agent) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""import typing
from typing import Any, Dict

def test_function(data: Any) -> Dict:
    return {}
""")
        temp_path = Path(f.name)

    try:
        issue = Issue(
            id="test - 6",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Mixed import styles detected",
            file_path=str(temp_path),
        )

        result = await import_agent.fix_issue(issue)

        assert result.success is True
        assert result.confidence == 0.9
        assert len(result.fixes_applied) > 0
        assert str(temp_path) in result.files_modified

        with temp_path.open() as f:
            content = f.read()

            assert "from typing import" in content
            assert "import typing" not in content

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_get_diagnostics(import_agent) -> None:
    import_agent.context.project_path = Path(__file__).parent.parent / "crackerjack"

    diagnostics = await import_agent.get_diagnostics()

    assert "files_analyzed" in diagnostics
    assert "mixed_import_files" in diagnostics
    assert "total_mixed_modules" in diagnostics
    assert diagnostics["files_analyzed"] >= 0
