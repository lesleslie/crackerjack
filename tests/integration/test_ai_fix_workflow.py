"""Integration tests for AI-fix workflow with ProviderChain.

Tests end-to-end AI-fix functionality including:
- ProviderChain fallback behavior
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

from crackerjack.adapters.ai.registry import ProviderChain, ProviderID
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.dependency_agent import DependencyAgent
from crackerjack.agents.enhanced_coordinator import EnhancedAgentCoordinator
from crackerjack.agents.refactoring_agent import RefactoringAgent
from crackerjack.config import load_settings, CrackerjackSettings
from crackerjack.config.settings import AISettings
from crackerjack.memory.git_metrics_collector import BranchMetrics
from crackerjack.models.session_metrics import SessionMetrics
from crackerjack.services.metrics import MetricsCollector, _metrics_collector


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup is handled by the OS temp file cleanup


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

    # Create Python files with different issues
    (repo_dir / "complexity.py").write_text("""
def very_complex_function(arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10):
    # This function has high complexity
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


class TestProviderChainIntegration:
    """Integration tests for ProviderChain fallback behavior."""

    @pytest.mark.asyncio
    async def test_provider_chain_fallback_on_unavailable(self):
        """Test that ProviderChain falls back to next provider when first fails."""
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN])

        # Mock Claude as unavailable, Qwen as available
        async def mock_availability(provider):
            from crackerjack.adapters.ai.claude import ClaudeCodeFixer
            from crackerjack.adapters.ai.qwen import QwenCodeFixer

            if isinstance(provider, ClaudeCodeFixer):
                return False
            if isinstance(provider, QwenCodeFixer):
                return True
            return False

        with patch.object(chain, "_check_provider_availability", side_effect=mock_availability):
            provider, provider_id = await chain.get_available_provider()

        assert provider_id == ProviderID.QWEN
        assert provider is not None

    @pytest.mark.asyncio
    async def test_provider_chain_metrics_tracking(self, temp_db_path):
        """Test that provider selections are tracked in metrics."""
        # Create custom metrics collector with temp DB
        from crackerjack.services.metrics import _metrics_collector

        original_collector = _metrics_collector
        _metrics_collector = MetricsCollector(db_path=temp_db_path)

        try:
            chain = ProviderChain([ProviderID.CLAUDE])

            # Track a successful provider selection
            chain._metrics = _metrics_collector
            chain._track_provider_selection(
                ProviderID.CLAUDE, success=True, latency_ms=50
            )

            # Verify metrics were recorded
            with sqlite3.connect(temp_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # First check if any records exist
                cursor.execute("SELECT COUNT(*) FROM provider_performance")
                count = cursor.fetchone()[0]
                assert count > 0, "No records found in provider_performance table"

                # Now query for the specific record
                cursor.execute(
                    """SELECT * FROM provider_performance
                       WHERE provider_id=? ORDER BY id DESC LIMIT 1""",
                    ("claude",),
                )
                result = cursor.fetchone()

            assert result is not None, f"No record found for provider 'claude'. Total records: {count}"
            assert result["provider_id"] == "claude"
            assert result["success"] == 1
            assert result["latency_ms"] == 50.0

        finally:
            _metrics_collector = original_collector


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

        # Check agent can handle it
        confidence = await agent.can_handle(issue)
        assert confidence > 0.0

        # Verify get_supported_types includes TYPE_ERROR
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

        # Verify write was called with modified content
        mock_context.write_file_content.assert_called_once()
        written_content = mock_context.write_file_content.call_args[0][1]
        assert "pytest-snob" not in written_content
        assert "pytest>=7.0.0" in written_content  # Other deps preserved

    @pytest.mark.asyncio
    async def test_type_error_routes_to_refactoring_agent(self, mock_context, temp_db_path):
        """Test that TYPE_ERROR issues route to RefactoringAgent with high confidence.

        This test verifies the fix for the TYPE_ERROR routing bug where ArchitectAgent
        was being selected instead of RefactoringAgent. The test ensures:

        1. TYPE_ERROR issues are assigned to RefactoringAgent (not ArchitectAgent)
        2. RefactoringAgent reports confidence >= 0.7 (above AI-fix threshfrom crackerjack.memory import BranchMetrics)
        3. ArchitectAgent reports low confidence (0.1) for TYPE_ERROR (fallback only)
        4. The coordinator's agent selection prefers RefactoringAgent
        """
        import crackerjack.services.metrics as metrics_module
        from crackerjack.agents.architect_agent import ArchitectAgent

        original_collector = metrics_module._metrics_collector
        metrics_module._metrics_collector = MetricsCollector(db_path=temp_db_path)

        try:
            # Setup: Create test code with missing return type
            test_code = """def process_data(data):
    result = []
    for item in data:
        result.append(item.upper())
    return result
"""
            mock_context.get_file_content.return_value = test_code
            mock_context.write_file_content.return_value = True

            # Create TYPE_ERROR issue (missing return type annotation)
            issue = Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="Function 'process_data' has missing return type annotation",
                file_path="test_file.py",
                line_number=1,
            )

            # Step 1: Verify RefactoringAgent can handle TYPE_ERROR with high confidence
            refactor_agent = RefactoringAgent(mock_context)
            refactor_confidence = await refactor_agent.can_handle(issue)

            assert refactor_confidence >= 0.7, (
                f"RefactoringAgent should have high confidence (>=0.7) for TYPE_ERROR, "
                f"got {refactor_confidence}. This indicates the TYPE_ERROR routing is broken."
            )

            # Step 2: Verify ArchitectAgent has LOW confidence (fallback only)
            architect_agent = ArchitectAgent(mock_context)
            architect_confidence = await architect_agent.can_handle(issue)

            assert architect_confidence == 0.1, (
                f"ArchitectAgent should have low confidence (0.1) for TYPE_ERROR to act as "
                f"fallback, got {architect_confidence}. ArchitectAgent should delegate to "
                f"RefactoringAgent for TYPE_ERROR issues."
            )

            # Step 3: Verify RefactoringAgent wins over ArchitectAgent
            assert refactor_confidence > architect_confidence, (
                f"RefactoringAgent ({refactor_confidence}) should have higher confidence than "
                f"ArchitectAgent ({arch_confidence}) for TYPE_ERROR issues. This ensures "
                f"RefactoringAgent is selected first in the coordinator's agent selection."
            )

            # Step 4: Verify the fix is actually applied
            result = await refactor_agent.analyze_and_fix(issue)

            assert result.success is True, (
                f"RefactoringAgent should successfully fix TYPE_ERROR issues. "
                f"Failed with: {result.remaining_issues}"
            )

            assert result.confidence >= 0.7, (
                f"Fix result should have high confidence (>=0.7), got {result.confidence}"
            )

            assert "type annotation" in " ".join(result.fixes_applied).lower() or len(result.fixes_applied) > 0, (
                f"Fix should apply type annotation changes. Fixes applied: {result.fixes_applied}"
            )

        finally:
            metrics_module._metrics_collector = original_collector


class TestEnhancedCoordinatorIntegration:
    """Integration tests for EnhancedAgentCoordinator with ProviderChain."""

    @pytest.mark.asyncio
    async def test_coordinator_initializes_provider_chain(self, mock_context):
        """Test that EnhancedAgentCoordinator initializes ProviderChain."""
        tracker = MagicMock()
        debugger = MagicMock()

        coordinator = EnhancedAgentCoordinator(
            context=mock_context,
            tracker=tracker,
            debugger=debugger,
        )

        assert coordinator.provider_chain is not None
        assert len(coordinator.provider_chain.provider_ids) > 0

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

            # Create a test issue
            issue = Issue(
                type=IssueType.COMPLEXITY,
                severity=Priority.MEDIUM,
                message="Function too complex",
                file_path="complexity.py",
                line_number=2,
            )

            # Mock agent execution
            result = FixResult(
                success=True,
                confidence=0.85,
                fixes_applied=["Simplified function"],
                files_modified=["complexity.py"],
            )

            # Track the execution
            job_id = "test-job-1"
            await coordinator._track_agent_execution(
                job_id=job_id,
                agent_name="RefactoringAgent",
                issue_type="COMPLEXITY",
                result=result,
            )

            # Verify metrics were recorded
            with sqlite3.connect(temp_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # First check if any records exist
                cursor.execute("SELECT COUNT(*) FROM agent_executions")
                count = cursor.fetchone()[0]
                assert count > 0, f"No agent_executions records found. Total: {count}"

                # Now query for the specific record
                cursor.execute(
                    """SELECT * FROM agent_executions
                       WHERE job_id=? AND agent_name=?""",
                    (job_id, "RefactoringAgent"),
                )
                execution = cursor.fetchone()

            assert execution is not None, f"No execution found for job_id={job_id}, agent=RefactoringAgent"
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
        """Test complete workflow: issue → agent → fix → metrics."""
        import crackerjack.services.metrics as metrics_module

        original_collector = metrics_module._metrics_collector
        metrics_module._metrics_collector = MetricsCollector(db_path=temp_db_path)

        try:
            # Setup: Create coordinator and issue
            tracker = MagicMock()
            debugger = MagicMock()
            coordinator = EnhancedAgentCoordinator(
                context=mock_context,
                tracker=tracker,
                debugger=debugger,
            )

            # Create a test TYPE_ERROR issue
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

            # Execute: Agent analyzes and fixes
            agent = RefactoringAgent(mock_context)
            result = await agent.analyze_and_fix(issue)

            # Verify fix was applied
            assert result.success is True
            assert result.confidence > 0.0

            # Track metrics
            job_id = "e2e-test-1"
            await coordinator._track_agent_execution(
                job_id=job_id,
                agent_name="RefactoringAgent",
                issue_type="TYPE_ERROR",
                result=result,
            )

            # Verify complete workflow
            with sqlite3.connect(temp_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Check agent execution was tracked
                cursor.execute(
                    """SELECT * FROM agent_executions WHERE job_id=?""",
                    (job_id,),
                )
                execution = cursor.fetchone()

            assert execution is not None
            assert execution["success"] == 1
            assert execution["issue_type"] == "TYPE_ERROR"

            # Verify query methods work
            success_rate = metrics_module._metrics_collector.get_agent_success_rate("RefactoringAgent")
            assert success_rate == 1.0  # Only one execution, successful

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

            # Issue 1: TYPE_ERROR handled by RefactoringAgent
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

            # Issue 2: DEPENDENCY handled by DependencyAgent
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

            # Verify both agents tracked correctly
            with sqlite3.connect(temp_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    """SELECT agent_name, issue_type, success FROM agent_executions
                       WHERE job_id=? ORDER BY id""",
                    (job_id,),
                )
                executions = cursor.fetchall()

            assert len(executions) == 2
            assert executions[0]["agent_name"] == "RefactoringAgent"
            assert executions[0]["issue_type"] == "TYPE_ERROR"
            assert executions[1]["agent_name"] == "DependencyAgent"
            assert executions[1]["issue_type"] == "DEPENDENCY"

            # Verify per-agent success rates
            refactor_rate = metrics_module._metrics_collector.get_agent_success_rate("RefactoringAgent")
            dep_rate = metrics_module._metrics_collector.get_agent_success_rate("DependencyAgent")

            assert refactor_rate == 1.0
            assert dep_rate == 1.0

        finally:
            metrics_module._metrics_collector = original_collector


class TestProviderChainFallbackScenarios:
    """Integration tests for realistic ProviderChain fallback scenarios."""

    @pytest.mark.asyncio
    async def test_claude_unavailable_falls_back_to_qwen(self):
        """Test fallback from Claude to Qwen when Claude unavailable."""
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN])

        async def mock_check(provider):
            # Claude unavailable
            from crackerjack.adapters.ai.claude import ClaudeCodeFixer
            if isinstance(provider, ClaudeCodeFixer):
                return False
            # Qwen available
            return True

        with patch.object(chain, "_check_provider_availability", side_effect=mock_check):
            provider, provider_id = await chain.get_available_provider()

        assert provider_id == ProviderID.QWEN
        assert provider is not None

    @pytest.mark.asyncio
    async def test_all_providers_unavailable_raises_error(self):
        """Test that RuntimeError is raised when all providers unavailable."""
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN])

        async def mock_check(provider):
            # All providers unavailable
            return False

        with patch.object(chain, "_check_provider_availability", side_effect=mock_check):
            with pytest.raises(RuntimeError, match="All AI providers unavailable"):
                await chain.get_available_provider()

    @pytest.mark.asyncio
    async def test_provider_priority_order_respected(self):
        """Test that provider priority order is respected."""
        # Qwen first, then Claude (reverse order)
        chain = ProviderChain([ProviderID.QWEN, ProviderID.CLAUDE])

        # Mock both as available
        async def mock_check(provider):
            return True

        with patch.object(chain, "_check_provider_availability", side_effect=mock_check):
            provider, provider_id = await chain.get_available_provider()

        # Should return Qwen (higher priority)
        assert provider_id == ProviderID.QWEN


class TestMetricsQueryIntegration:
    """Integration tests for metrics queries with real data."""

    def test_agent_success_rate_calculation(self, temp_db_path):
        """Test success rate calculation with realistic data."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Insert realistic execution data
        with sqlite3.connect(temp_db_path) as conn:
            # RefactoringAgent: 8 successes, 2 failures = 80%
            for i in range(8):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"job-success-{i}", "RefactoringAgent", "COMPLEXITY", True, 0.85, datetime.now()),
                )
            for i in range(2):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"job-fail-{i}", "RefactoringAgent", "COMPLEXITY", False, 0.5, datetime.now()),
                )

            # DependencyAgent: 5 successes, 0 failures = 100%
            for i in range(5):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"dep-job-{i}", "DependencyAgent", "DEPENDENCY", True, 0.9, datetime.now()),
                )

        # Verify success rates
        refactor_rate = collector.get_agent_success_rate("RefactoringAgent")
        dep_rate = collector.get_agent_success_rate("DependencyAgent")

        assert refactor_rate == 0.8
        assert dep_rate == 1.0

    def test_provider_availability_time_window(self, temp_db_path):
        """Test provider availability with different time windows."""
        collector = MetricsCollector(db_path=temp_db_path)

        now = datetime.now()
        with sqlite3.connect(temp_db_path) as conn:
            # Recent: Last hour (within 24h)
            for i in range(8):
                timestamp = now - timedelta(minutes=5 * i)
                conn.execute(
                    """INSERT INTO provider_performance
                       (provider_id, success, latency_ms, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    ("claude", True, 50.0, timestamp),
                )

            # Older: 2 days ago (outside 24h window)
            for i in range(2):
                timestamp = now - timedelta(days=2, hours=i)
                conn.execute(
                    """INSERT INTO provider_performance
                       (provider_id, success, latency_ms, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    ("claude", True, 60.0, timestamp),
                )

            # Qwen: Recent failures
            for i in range(3):
                timestamp = now - timedelta(minutes=10 * i)
                conn.execute(
                    """INSERT INTO provider_performance
                       (provider_id, success, latency_ms, error_message, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("qwen", False, None, "API error", timestamp),
                )

        # Claude 24h availability: 100% (only recent counted)
        claude_24h = collector.get_provider_availability("claude", hours=24)
        assert claude_24h == 1.0

        # Qwen 24h availability: 0% (all failures)
        qwen_24h = collector.get_provider_availability("qwen", hours=24)
        assert qwen_24h == 0.0

    def test_confidence_distribution_aggregation(self, temp_db_path):
        """Test confidence distribution across multiple agents."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # RefactoringAgent: Mixed confidence levels
            confidences = [0.3, 0.4, 0.6, 0.7, 0.85, 0.95]  # 2 low, 2 medium, 2 high
            for i, conf in enumerate(confidences):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"job-{i}", "RefactoringAgent", "COMPLEXITY", True, conf, datetime.now()),
                )

            # DependencyAgent: All high confidence
            for i in range(4):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"dep-job-{i}", "DependencyAgent", "DEPENDENCY", True, 0.9, datetime.now()),
                )

        # Check RefactoringAgent distribution
        refactor_dist = collector.get_agent_confidence_distribution("RefactoringAgent")
        assert refactor_dist["low"] == 2
        assert refactor_dist["medium"] == 2
        assert refactor_dist["high"] == 2

        # Check DependencyAgent distribution
        dep_dist = collector.get_agent_confidence_distribution("DependencyAgent")
        assert dep_dist["high"] == 4
        assert "low" not in dep_dist
        assert "medium" not in dep_dist
