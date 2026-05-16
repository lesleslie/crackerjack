"""Integration tests for AI-fix workflow with FallbackChainCodeFixer.

Tests end-to-end AI-fix functionality including:
- FallbackChainCodeFixer initialization and delegation
- Agent selection for different issue types
- Metrics tracking during fixes
- Complete workflow execution
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.adapters.ai.registry import ProviderID
from crackerjack.adapters.ai.unified import FallbackChainCodeFixer
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.dependency_agent import DependencyAgent
from crackerjack.agents.enhanced_coordinator import EnhancedAgentCoordinator
from crackerjack.agents.refactoring_agent import RefactoringAgent
from crackerjack.config import load_settings, CrackerjackSettings
from crackerjack.memory.git_metrics_collector import BranchMetrics
from crackerjack.models.session_metrics import SessionMetrics
from crackerjack.services.metrics import MetricsCollector, _metrics_collector


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = Path(f.name)
    yield db_path


@pytest.fixture
def mock_context():
    """Mock AgentContext for testing."""
    context = MagicMock(spec=AgentContext)
    context.get_file_content = MagicMock(return_value=None)
    context.write_file_content = MagicMock(return_value=True)
    context.project_path = Path("/tmp/test_project")
    return context


@pytest.fixture
def test_repo(tmp_path):
    """Create a test repository with various issue types."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    (repo_dir / "complexity.py").write_text("""
def very_complex_function(arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10):
    if arg1:
        if arg2:
            if arg3:
                if arg4:
                    if arg5:
                        return arg1 + arg2
    return None
""")

    (repo_dir / "missing_types.py").write_text("""
def foo():
    pass

def bar():
    x = 1
    return x
""")

    (repo_dir / "pyproject.toml").write_text("""
[project]
name = "test-repo"
version = "0.1.0"
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
]
""")

    return repo_dir


class TestFallbackChainCodeFixerIntegration:
    """Integration tests for FallbackChainCodeFixer behavior."""

    def test_fixer_initializes_with_provider_ids(self):
        """FallbackChainCodeFixer knows about the three-tier providers."""
        from crackerjack.adapters.ai.unified import _build_llm_settings

        settings = _build_llm_settings()
        assert ProviderID.MINIMAX in [ProviderID(k) for k in settings.providers]
        assert ProviderID.LLAMA_SERVER in [ProviderID(k) for k in settings.providers]
        assert ProviderID.OLLAMA in [ProviderID(k) for k in settings.providers]

    @pytest.mark.asyncio
    async def test_fixer_delegates_to_fallback_chain(self):
        """FallbackChainCodeFixer delegates LLM calls to mcp_common FallbackChain."""
        from mcp_common.llm import FallbackChain

        fixer = FallbackChainCodeFixer()

        mock_chain = AsyncMock(spec=FallbackChain)
        mock_chain.execute.return_value = {
            "content": '{"fixed_code": "def foo() -> None:\\n    pass\\n", '
                       '"explanation": "Added return type", "confidence": 0.9}',
            "provider": "minimax",
            "model": "MiniMax-M2.7",
        }

        with patch.object(fixer, "_initialize_client", return_value=mock_chain):
            result = await fixer.fix_code_issue(
                file_path="test.py",
                issue_description="Missing return type",
                code_context="def foo():\n    pass\n",
                fix_type="type_annotation",
            )

        assert mock_chain.execute.called
        task = mock_chain.execute.call_args[0][0]
        assert task["task_type"] == "code_generation"
        assert "Missing return type" in task["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_fixer_respects_task_type_routing(self):
        """task_type=code_generation is sent to FallbackChain for per-provider routing."""
        from mcp_common.llm import FallbackChain

        fixer = FallbackChainCodeFixer()
        mock_chain = AsyncMock(spec=FallbackChain)
        mock_chain.execute.return_value = {
            "content": '{"fixed_code": "x = 1", "explanation": "fixed", "confidence": 0.8}',
            "provider": "ollama",
            "model": "qwen2.5-coder:7b",
        }

        with patch.object(fixer, "_initialize_client", return_value=mock_chain):
            await fixer.fix_code_issue("f.py", "issue", "code", "lint")

        task = mock_chain.execute.call_args[0][0]
        assert task["task_type"] == "code_generation"

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_error_result(self):
        """When FallbackChain raises AllProvidersExhaustedError, fixer returns failure dict."""
        from mcp_common.llm.exceptions import AllProvidersExhaustedError
        from mcp_common.llm import FallbackChain

        fixer = FallbackChainCodeFixer()
        mock_chain = AsyncMock(spec=FallbackChain)
        mock_chain.execute.side_effect = AllProvidersExhaustedError("all failed")

        with patch.object(fixer, "_initialize_client", return_value=mock_chain):
            result = await fixer.fix_code_issue("f.py", "issue", "code", "lint")

        assert result["success"] is False
        assert result["confidence"] == 0.0


class TestAgentSelectionIntegration:
    """Integration tests for agent selection with different issue types."""

    @pytest.mark.asyncio
    async def test_refactoring_agent_handles_type_error(self, mock_context):
        """Test that RefactoringAgent handles TYPE_ERROR issues."""
        agent = RefactoringAgent(mock_context)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path="missing_types.py",
            line_number=2,
        )

        confidence = await agent.can_handle(issue)
        assert confidence > 0.0

        supported = agent.get_supported_types()
        assert IssueType.TYPE_ERROR in supported

    @pytest.mark.asyncio
    async def test_dependency_agent_removes_unused_dependency(self, mock_context):
        """Test that DependencyAgent removes unused dependencies."""
        agent = DependencyAgent(mock_context)

        pyproject_content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
]
"""
        mock_context.get_file_content.return_value = pyproject_content
        mock_context.write_file_content.return_value = True

        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=4,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.confidence == 0.9
        assert "Removed unused dependency: pytest-snob" in result.fixes_applied

        mock_context.write_file_content.assert_called_once()
        written_content = mock_context.write_file_content.call_args[0][1]
        assert "pytest-snob" not in written_content
        assert "pytest>=7.0.0" in written_content

    @pytest.mark.asyncio
    async def test_type_error_routes_to_refactoring_agent(self, mock_context, temp_db_path):
        """Test that TYPE_ERROR issues route to RefactoringAgent with high confidence."""
        import crackerjack.services.metrics as metrics_module
        from crackerjack.agents.architect_agent import ArchitectAgent

        original_collector = metrics_module._metrics_collector
        metrics_module._metrics_collector = MetricsCollector(db_path=temp_db_path)

        try:
            test_code = """def process_data(data):
    result = []
    for item in data:
        result.append(item.upper())
    return result
"""
            mock_context.get_file_content.return_value = test_code
            mock_context.write_file_content.return_value = True

            issue = Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="Function 'process_data' has missing return type annotation",
                file_path="test_file.py",
                line_number=1,
            )

            refactor_agent = RefactoringAgent(mock_context)
            refactor_confidence = await refactor_agent.can_handle(issue)

            assert refactor_confidence >= 0.7

            architect_agent = ArchitectAgent(mock_context)
            architect_confidence = await architect_agent.can_handle(issue)

            assert architect_confidence == 0.5
            assert refactor_confidence > architect_confidence

            result = await refactor_agent.analyze_and_fix(issue)
            assert result.success is True
            assert result.confidence >= 0.7

        finally:
            metrics_module._metrics_collector = original_collector


class TestEnhancedCoordinatorIntegration:
    """Integration tests for EnhancedAgentCoordinator with FallbackChainCodeFixer."""

    @pytest.mark.asyncio
    async def test_coordinator_initializes_code_fixer(self, mock_context):
        """Test that EnhancedAgentCoordinator initializes FallbackChainCodeFixer."""
        tracker = MagicMock()
        debugger = MagicMock()

        coordinator = EnhancedAgentCoordinator(
            context=mock_context,
            tracker=tracker,
            debugger=debugger,
        )

        assert coordinator.code_fixer is not None
        assert isinstance(coordinator.code_fixer, FallbackChainCodeFixer)

    @pytest.mark.asyncio
    async def test_coordinator_tracks_agent_executions(self, mock_context, temp_db_path):
        """Test that coordinator tracks agent executions in metrics."""
        import crackerjack.services.metrics as metrics_module

        original_collector = metrics_module._metrics_collector
        metrics_module._metrics_collector = MetricsCollector(db_path=temp_db_path)

        try:
            tracker = MagicMock()
            debugger = MagicMock()

            coordinator = EnhancedAgentCoordinator(
                context=mock_context,
                tracker=tracker,
                debugger=debugger,
            )

            issue = Issue(
                type=IssueType.COMPLEXITY,
                severity=Priority.MEDIUM,
                message="Function too complex",
                file_path="complexity.py",
                line_number=2,
            )

            result = FixResult(
                success=True,
                confidence=0.85,
                fixes_applied=["Simplified function"],
                files_modified=["complexity.py"],
            )

            job_id = "test-job-1"
            await coordinator._track_agent_execution(
                job_id=job_id,
                agent_name="RefactoringAgent",
                issue_type="COMPLEXITY",
                result=result,
            )

            with sqlite3.connect(temp_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM agent_executions"
                )
                count = cursor.fetchone()[0]
                assert count > 0

                cursor.execute(
                    "SELECT * FROM agent_executions WHERE job_id=? AND agent_name=?",
                    (job_id, "RefactoringAgent"),
                )
                execution = cursor.fetchone()

            assert execution is not None
            assert execution["agent_name"] == "RefactoringAgent"
            assert execution["issue_type"] == "COMPLEXITY"
            assert execution["success"] == 1
            assert execution["confidence"] == 0.85

        finally:
            metrics_module._metrics_collector = original_collector


class TestEndToEndWorkflow:
    """End-to-end tests for complete AI-fix workflow."""

    @pytest.mark.asyncio
    async def test_complete_fix_workflow_type_error(self, mock_context, temp_db_path):
        """Test complete workflow: issue -> agent -> fix -> metrics."""
        import crackerjack.services.metrics as metrics_module

        original_collector = metrics_module._metrics_collector
        metrics_module._metrics_collector = MetricsCollector(db_path=temp_db_path)

        try:
            tracker = MagicMock()
            debugger = MagicMock()
            coordinator = EnhancedAgentCoordinator(
                context=mock_context,
                tracker=tracker,
                debugger=debugger,
            )

            test_code = "def foo():\n    pass\n"
            mock_context.get_file_content.return_value = test_code
            mock_context.write_file_content.return_value = True

            issue = Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="Missing return type",
                file_path="test.py",
                line_number=1,
            )

            agent = RefactoringAgent(mock_context)
            result = await agent.analyze_and_fix(issue)

            assert result.success is True
            assert result.confidence > 0.0

            job_id = "e2e-test-1"
            await coordinator._track_agent_execution(
                job_id=job_id,
                agent_name="RefactoringAgent",
                issue_type="TYPE_ERROR",
                result=result,
            )

            with sqlite3.connect(temp_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM agent_executions WHERE job_id=?", (job_id,))
                execution = cursor.fetchone()

            assert execution is not None
            assert execution["success"] == 1
            assert execution["issue_type"] == "TYPE_ERROR"

            success_rate = metrics_module._metrics_collector.get_agent_success_rate("RefactoringAgent")
            assert success_rate == 1.0

            distribution = metrics_module._metrics_collector.get_agent_confidence_distribution("RefactoringAgent")
            assert "high" in distribution or "medium" in distribution

        finally:
            metrics_module._metrics_collector = original_collector

    @pytest.mark.asyncio
    async def test_multiple_agents_different_issues(self, mock_context, temp_db_path):
        """Test workflow with multiple agents handling different issue types."""
        import crackerjack.services.metrics as metrics_module

        original_collector = metrics_module._metrics_collector
        metrics_module._metrics_collector = MetricsCollector(db_path=temp_db_path)

        try:
            tracker = MagicMock()
            debugger = MagicMock()
            coordinator = EnhancedAgentCoordinator(
                context=mock_context,
                tracker=tracker,
                debugger=debugger,
            )

            job_id = "multi-agent-test"

            mock_context.get_file_content.return_value = "def foo():\n    pass\n"
            issue1 = Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="Missing return type",
                file_path="test1.py",
                line_number=1,
            )

            agent = RefactoringAgent(mock_context)
            result1 = await agent.analyze_and_fix(issue1)
            await coordinator._track_agent_execution(
                job_id=job_id,
                agent_name="RefactoringAgent",
                issue_type="TYPE_ERROR",
                result=result1,
            )

            pyproject_content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
            mock_context.get_file_content.return_value = pyproject_content

            issue2 = Issue(
                type=IssueType.DEPENDENCY,
                severity=Priority.MEDIUM,
                message="Unused dependency: pytest-snob",
                file_path="pyproject.toml",
                line_number=3,
            )

            dep_agent = DependencyAgent(mock_context)
            result2 = await dep_agent.analyze_and_fix(issue2)
            await coordinator._track_agent_execution(
                job_id=job_id,
                agent_name="DependencyAgent",
                issue_type="DEPENDENCY",
                result=result2,
            )

            with sqlite3.connect(temp_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT agent_name, issue_type, success FROM agent_executions WHERE job_id=? ORDER BY id",
                    (job_id,),
                )
                executions = cursor.fetchall()

            assert len(executions) == 2
            assert executions[0]["agent_name"] == "RefactoringAgent"
            assert executions[0]["issue_type"] == "TYPE_ERROR"
            assert executions[1]["agent_name"] == "DependencyAgent"
            assert executions[1]["issue_type"] == "DEPENDENCY"

            refactor_rate = metrics_module._metrics_collector.get_agent_success_rate("RefactoringAgent")
            dep_rate = metrics_module._metrics_collector.get_agent_success_rate("DependencyAgent")

            assert refactor_rate == 1.0
            assert dep_rate == 1.0

        finally:
            metrics_module._metrics_collector = original_collector


class TestMetricsQueryIntegration:
    """Integration tests for metrics queries with real data."""

    def test_agent_success_rate_calculation(self, temp_db_path):
        """Test success rate calculation with realistic data."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            for i in range(8):
                conn.execute(
                    "INSERT INTO agent_executions (job_id, agent_name, issue_type, success, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (f"job-success-{i}", "RefactoringAgent", "COMPLEXITY", True, 0.85, datetime.now()),
                )
            for i in range(2):
                conn.execute(
                    "INSERT INTO agent_executions (job_id, agent_name, issue_type, success, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (f"job-fail-{i}", "RefactoringAgent", "COMPLEXITY", False, 0.5, datetime.now()),
                )
            for i in range(5):
                conn.execute(
                    "INSERT INTO agent_executions (job_id, agent_name, issue_type, success, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (f"dep-job-{i}", "DependencyAgent", "DEPENDENCY", True, 0.9, datetime.now()),
                )

        assert collector.get_agent_success_rate("RefactoringAgent") == 0.8
        assert collector.get_agent_success_rate("DependencyAgent") == 1.0

    def test_provider_availability_time_window(self, temp_db_path):
        """Test provider availability with different time windows."""
        collector = MetricsCollector(db_path=temp_db_path)

        now = datetime.now()
        with sqlite3.connect(temp_db_path) as conn:
            for i in range(8):
                timestamp = now - timedelta(minutes=5 * i)
                conn.execute(
                    "INSERT INTO provider_performance (provider_id, success, latency_ms, timestamp) VALUES (?, ?, ?, ?)",
                    ("minimax", True, 50.0, timestamp),
                )
            for i in range(2):
                timestamp = now - timedelta(days=2, hours=i)
                conn.execute(
                    "INSERT INTO provider_performance (provider_id, success, latency_ms, timestamp) VALUES (?, ?, ?, ?)",
                    ("minimax", True, 60.0, timestamp),
                )
            for i in range(3):
                timestamp = now - timedelta(minutes=10 * i)
                conn.execute(
                    "INSERT INTO provider_performance (provider_id, success, latency_ms, error_message, timestamp) VALUES (?, ?, ?, ?, ?)",
                    ("ollama", False, None, "connection refused", timestamp),
                )

        assert collector.get_provider_availability("minimax", hours=24) == 1.0
        assert collector.get_provider_availability("ollama", hours=24) == 0.0

    def test_confidence_distribution_aggregation(self, temp_db_path):
        """Test confidence distribution across multiple agents."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            confidences = [0.3, 0.4, 0.6, 0.7, 0.85, 0.95]
            for i, conf in enumerate(confidences):
                conn.execute(
                    "INSERT INTO agent_executions (job_id, agent_name, issue_type, success, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (f"job-{i}", "RefactoringAgent", "COMPLEXITY", True, conf, datetime.now()),
                )
            for i in range(4):
                conn.execute(
                    "INSERT INTO agent_executions (job_id, agent_name, issue_type, success, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (f"dep-job-{i}", "DependencyAgent", "DEPENDENCY", True, 0.9, datetime.now()),
                )

        refactor_dist = collector.get_agent_confidence_distribution("RefactoringAgent")
        assert refactor_dist["low"] == 2
        assert refactor_dist["medium"] == 2
        assert refactor_dist["high"] == 2

        dep_dist = collector.get_agent_confidence_distribution("DependencyAgent")
        assert dep_dist["high"] == 4
        assert dep_dist["low"] == 0
        assert dep_dist["medium"] == 0
