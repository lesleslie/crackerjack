import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

import pytest

from crackerjack.core.proactive_workflow import ProactiveWorkflowPipeline, ArchitecturalAssessment


@pytest.fixture
def temp_project_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.mark.asyncio
async def test_proactive_workflow_pipeline_initialization(temp_project_path):
    """Test initialization of ProactiveWorkflowPipeline."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    assert pipeline.project_path == temp_project_path
    assert pipeline.logger is not None
    assert pipeline._architect_agent_coordinator is None


@pytest.mark.asyncio
async def test_run_complete_workflow_with_planning_standard_path(temp_project_path):
    """Test running complete workflow with planning when standard workflow is chosen."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    # Mock the private methods to control the flow
    with patch.object(pipeline, '_assess_codebase_architecture') as mock_assess:
        # Create a mock assessment that doesn't need planning
        mock_assessment = Mock()
        mock_assessment.needs_planning = False
        mock_assess.return_value = mock_assessment

        # Mock the standard workflow execution
        with patch.object(pipeline, '_execute_standard_workflow', return_value=True) as mock_std_wf:
            options = Mock()
            result = await pipeline.run_complete_workflow_with_planning(options)

            assert result is True
            mock_assess.assert_called_once()
            mock_std_wf.assert_called_once_with(options)


@pytest.mark.asyncio
async def test_run_complete_workflow_with_planning_proactive_path(temp_project_path):
    """Test running complete workflow with planning when proactive path is chosen."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    # Mock the private methods to control the flow
    with patch.object(pipeline, '_assess_codebase_architecture') as mock_assess, \
         patch.object(pipeline, '_create_comprehensive_plan') as mock_create_plan, \
         patch.object(pipeline, '_execute_planned_workflow', return_value=True) as mock_exec_plan:

        # Create a mock assessment that needs planning
        mock_assessment = Mock()
        mock_assessment.needs_planning = True
        mock_assess.return_value = mock_assessment

        # Create a mock plan
        mock_plan = {"strategy": "proactive", "phases": ["test"]}
        mock_create_plan.return_value = mock_plan

        options = Mock()
        result = await pipeline.run_complete_workflow_with_planning(options)

        assert result is True
        mock_assess.assert_called_once()
        mock_create_plan.assert_called_once_with(mock_assessment)
        mock_exec_plan.assert_called_once_with(options, mock_plan)


@pytest.mark.asyncio
async def test_run_complete_workflow_with_planning_exception_handling(temp_project_path):
    """Test that exceptions in proactive workflow fall back to standard workflow."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    # Mock the assessment to raise an exception
    with patch.object(pipeline, '_assess_codebase_architecture', side_effect=Exception("Test error")), \
         patch.object(pipeline, '_execute_standard_workflow', return_value=True) as mock_std_wf:

        options = Mock()
        result = await pipeline.run_complete_workflow_with_planning(options)

        assert result is True
        mock_std_wf.assert_called_once_with(options)


@pytest.mark.asyncio
async def test_assess_codebase_architecture(temp_project_path):
    """Test the architecture assessment method."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    assessment = await pipeline._assess_codebase_architecture()

    assert isinstance(assessment, ArchitecturalAssessment)
    assert hasattr(assessment, 'needs_planning')
    assert hasattr(assessment, 'complexity_score')
    assert hasattr(assessment, 'potential_issues')
    assert hasattr(assessment, 'recommended_strategy')


@pytest.mark.asyncio
async def test_identify_potential_issues(temp_project_path):
    """Test identifying potential issues."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    issues = await pipeline._identify_potential_issues()

    assert isinstance(issues, list)
    # The method should return at least 2 issues based on the implementation
    assert len(issues) >= 2


def test_evaluate_planning_need(temp_project_path):
    """Test evaluating if planning is needed based on issues."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    # Mock issues that should trigger planning
    from crackerjack.agents.base import Issue, IssueType, Priority

    mock_issues = [
        Issue(
            id="test1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test issue 1",
            file_path=str(temp_project_path),
        ),
        Issue(
            id="test2",
            type=IssueType.DRY_VIOLATION,
            severity=Priority.MEDIUM,
            message="Test issue 2",
            file_path=str(temp_project_path),
        ),
    ]

    # Should need planning since there are 2 complex issues
    needs_planning = pipeline._evaluate_planning_need(mock_issues)
    assert needs_planning is True

    # Should not need planning with only 1 complex issue
    needs_planning_single = pipeline._evaluate_planning_need([mock_issues[0]])
    assert needs_planning_single is False


@pytest.mark.asyncio
async def test_execute_standard_workflow(temp_project_path):
    """Test executing standard workflow."""
    pipeline = ProactiveWorkflowPipeline(temp_project_path)

    options = Mock()
    result = await pipeline._execute_standard_workflow(options)

    assert result is True


@pytest.mark.asyncio
async def test_architectural_assessment_initialization():
    """Test initialization of ArchitecturalAssessment."""
    from crackerjack.agents.base import Issue, IssueType, Priority

    mock_issues = [
        Issue(
            id="test",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test issue",
            file_path="/fake/path",
        )
    ]

    assessment = ArchitecturalAssessment(
        needs_planning=True,
        complexity_score=5,
        potential_issues=mock_issues,
        recommended_strategy="proactive"
    )

    assert assessment.needs_planning is True
    assert assessment.complexity_score == 5
    assert assessment.potential_issues == mock_issues
    assert assessment.recommended_strategy == "proactive"
