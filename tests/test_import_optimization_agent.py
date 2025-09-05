import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.import_optimization_agent import ImportOptimizationAgent


@pytest.fixture
def agent_context():
    return AgentContext(
        project_path=Path("/ tmp / test"),
        temp_dir=Path("/ tmp / test"),
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
        # Check new fields exist
        assert isinstance(analysis.unused_imports, list)
        assert isinstance(analysis.import_violations, list)

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
        # Check new fields exist
        assert isinstance(analysis.unused_imports, list)
        assert isinstance(analysis.import_violations, list)

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

def test_function(data: Any) ->  Dict:
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
        assert result.confidence == 0.85
        assert len(result.fixes_applied) > 0
        assert str(temp_path) in result.files_modified

        with temp_path.open() as f:
            content = f.read()

            assert "from typing import" in content
            assert "import typing" not in content

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_enhanced_can_handle_error_codes(import_agent) -> None:
    """Test that the agent can handle ruff/pyflakes error codes."""
    issue = Issue(
        id="test-f401",
        type=IssueType.FORMATTING,
        severity=Priority.LOW,
        message="F401: 'typing.Dict' imported but unused",
        file_path="test.py",
    )

    can_handle = await import_agent.can_handle(issue)
    assert can_handle == 0.8


@pytest.mark.asyncio
async def test_unused_import_detection(import_agent) -> None:
    """Test unused import detection with mock vulture output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""import json
import unused_module
from typing import Dict

def test_function():
    return json.loads('{}')
""")
        temp_path = Path(f.name)

    try:
        # Mock the vulture detection
        original_method = import_agent._detect_unused_imports

        async def mock_detect_unused(*args):
            return ["unused_module", "Dict"]

        import_agent._detect_unused_imports = mock_detect_unused

        analysis = await import_agent.analyze_file(temp_path)

        assert "unused_module" in analysis.unused_imports
        assert "Dict" in analysis.unused_imports

        # Restore original method
        import_agent._detect_unused_imports = original_method

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_pep8_import_violations(import_agent) -> None:
    """Test PEP 8 import organization violation detection."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""import third_party_pkg
import os  # Should come before third-party
from local_module import *  # Star import
""")
        temp_path = Path(f.name)

    try:
        analysis = await import_agent.analyze_file(temp_path)

        assert len(analysis.import_violations) > 0
        # Should detect star import violation
        star_violation = any(
            "star import" in v.lower() for v in analysis.import_violations
        )
        assert star_violation

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_comprehensive_optimization(import_agent) -> None:
    """Test comprehensive import optimization with mixed styles and unused imports."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""import typing
from typing import Dict, List
import json
from json import loads
import unused_module

def process_data(data: Dict) -> List:
    return loads(data)
""")
        temp_path = Path(f.name)

    try:
        # Mock vulture to detect unused_module
        original_method = import_agent._detect_unused_imports

        async def mock_detect_unused(*args):
            return ["unused_module"]

        import_agent._detect_unused_imports = mock_detect_unused

        issue = Issue(
            id="test-comprehensive",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="Multiple import issues detected",
            file_path=str(temp_path),
        )

        result = await import_agent.fix_issue(issue)

        assert result.success is True
        assert result.confidence == 0.85
        assert len(result.fixes_applied) > 0

        # Check that mixed import consolidation was applied
        mixed_fix = any("mixed import" in fix.lower() for fix in result.fixes_applied)
        unused_fix = any("unused import" in fix.lower() for fix in result.fixes_applied)
        assert mixed_fix or unused_fix

        # Check the modified file
        with temp_path.open() as f:
            content = f.read()
            # Should consolidate to from-imports
            assert content.count("from typing import") >= 1
            assert "import typing" not in content or content.count("import typing") == 0
            # Should remove unused import
            assert "unused_module" not in content

        # Restore original method
        import_agent._detect_unused_imports = original_method

    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_get_enhanced_diagnostics(import_agent) -> None:
    import_agent.context.project_path = Path(__file__).parent.parent / "crackerjack"

    diagnostics = await import_agent.get_diagnostics()

    # Check all new diagnostic fields
    required_fields = [
        "files_analyzed",
        "mixed_import_files",
        "total_mixed_modules",
        "unused_import_files",
        "total_unused_imports",
        "pep8_violations",
        "capabilities",
    ]

    for field in required_fields:
        assert field in diagnostics

    assert diagnostics["files_analyzed"] >= 0
    assert isinstance(diagnostics["capabilities"], list)
    assert len(diagnostics["capabilities"]) >= 4  # Should have multiple capabilities
