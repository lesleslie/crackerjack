"""Tests for skills recommendation functionality.

These tests verify that skill recommendations work correctly
through the skills tracking integration.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crackerjack.agents.base import AgentContext
from crackerjack.integration.skills_tracking import (
    SessionBuddyDirectTracker,
    SessionBuddyMCPTracker,
    SkillExecutionContext,
)


# ============================================================================
# Recommendation Tests
# ============================================================================


class TestSkillRecommendations:
    """Test skill recommendation functionality."""

    @patch("crackerjack.integration.session_buddy_skills_compat.get_session_tracker")
    def test_direct_tracker_gets_recommendations(self, mock_get_tracker) -> None:
        """Test getting recommendations from direct tracker."""
        # Mock the skills tracker
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.recommend_skills.return_value = [
            {
                "skill_name": "RefactoringAgent",
                "similarity_score": 0.85,
                "completed": True,
                "duration_seconds": 42.5,
            }
        ]
        mock_get_tracker.return_value = mock_tracker_instance

        tracker = SessionBuddyDirectTracker(session_id="test-session")

        recommendations = tracker.get_recommendations(
            user_query="How do I fix complexity issues?",
            limit=5,
        )

        assert len(recommendations) == 1
        assert recommendations[0]["skill_name"] == "RefactoringAgent"
        assert recommendations[0]["similarity_score"] == 0.85

        # Verify session-buddy was called correctly (with session_id and workflow_phase)
        mock_tracker_instance.recommend_skills.assert_called_once()
        call_args = mock_tracker_instance.recommend_skills.call_args
        assert call_args[1]["user_query"] == "How do I fix complexity issues?"
        assert call_args[1]["limit"] == 5

    @patch("crackerjack.integration.session_buddy_skills_compat.get_session_tracker")
    def test_recommendations_with_workflow_phase(self, mock_get_tracker) -> None:
        """Test workflow-phase-aware recommendations."""
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.recommend_skills.return_value = [
            {
                "skill_name": "TestAgent",
                "similarity_score": 0.92,
                "completed": True,
                "workflow_phase": "fast_hooks",
            }
        ]
        mock_get_tracker.return_value = mock_tracker_instance

        tracker = SessionBuddyDirectTracker(session_id="test-session")

        recommendations = tracker.get_recommendations(
            user_query="Quick quality check",
            limit=5,
            workflow_phase="fast_hooks",
        )

        assert len(recommendations) == 1
        assert recommendations[0]["workflow_phase"] == "fast_hooks"

        # Verify phase was passed
        mock_tracker_instance.recommend_skills.assert_called_once()
        call_args = mock_tracker_instance.recommend_skills.call_args
        assert call_args[1]["workflow_phase"] == "fast_hooks"

    def test_recommendations_empty_if_tracker_unavailable(self) -> None:
        """Test that empty list returned if tracker unavailable."""
        with patch(
            "crackerjack.integration.session_buddy_skills_compat.get_session_tracker",
            side_effect=ImportError("session-buddy not available"),
        ):
            tracker = SessionBuddyDirectTracker(session_id="test-session")

            recommendations = tracker.get_recommendations(
                user_query="test query",
                limit=5,
            )

            assert recommendations == []


# ============================================================================
# Context Helper Tests
# ============================================================================


class TestAgentContextRecommendations:
    """Test recommendations through AgentContext."""

    def test_get_recommendations_through_context(self) -> None:
        """Test getting recommendations via AgentContext helper."""
        mock_tracker = MagicMock()
        mock_tracker.get_recommendations.return_value = [
            {
                "skill_name": "RecommendedAgent",
                "similarity_score": 0.88,
                "completed": True,
            }
        ]

        context = AgentContext(
            project_path="/tmp/test",
            skills_tracker=mock_tracker,
        )

        recommendations = context.get_skill_recommendations(
            user_query="Need help with type errors",
            limit=3,
        )

        assert len(recommendations) == 1
        assert recommendations[0]["skill_name"] == "RecommendedAgent"

        # Verify tracker was called (may include additional kwargs like workflow_phase)
        mock_tracker.get_recommendations.assert_called_once()
        call_args = mock_tracker.get_recommendations.call_args
        assert call_args[1]["user_query"] == "Need help with type errors"
        assert call_args[1]["limit"] == 3

    def test_recommendations_passes_workflow_phase(self) -> None:
        """Test that workflow phase is passed through."""
        mock_tracker = MagicMock()
        mock_tracker.get_recommendations.return_value = []

        context = AgentContext(
            project_path="/tmp/test",
            skills_tracker=mock_tracker,
        )

        context.get_skill_recommendations(
            user_query="test query",
            workflow_phase="comprehensive_hooks",
        )

        # Verify phase was passed
        mock_tracker.get_recommendations.assert_called_once()
        call_args = mock_tracker.get_recommendations.call_args
        assert call_args[1]["workflow_phase"] == "comprehensive_hooks"

    def test_recommendations_handles_error(self) -> None:
        """Test that errors are handled gracefully."""
        mock_tracker = MagicMock()
        mock_tracker.get_recommendations.side_effect = Exception("Recommendation failed!")

        context = AgentContext(
            project_path="/tmp/test",
            skills_tracker=mock_tracker,
        )

        recommendations = context.get_skill_recommendations(user_query="test")

        # Should return empty list on error
        assert recommendations == []

    def test_recommendations_returns_empty_if_no_tracker(self) -> None:
        """Test that empty list returned if no tracker configured."""
        context = AgentContext(
            project_path="/tmp/test",
            skills_tracker=None,
        )

        recommendations = context.get_skill_recommendations(user_query="test")

        assert recommendations == []


# ============================================================================
# SkillExecutionContext Tests
# ============================================================================


class TestRecommendationContext:
    """Test context creation for recommendations."""

    def test_context_from_issue(self) -> None:
        """Test creating context from issue for recommendations."""
        from crackerjack.agents.base import Issue, IssueType

        issue = Issue(
            type=IssueType.COMPLEXITY,
            severity="high",
            message="Function has cognitive complexity 15",
        )

        context = SkillExecutionContext.from_agent_execution(
            agent_name="RefactoringAgent",
            issue=issue,
            workflow_phase="comprehensive_hooks",
            candidates=None,
        )

        assert context.skill_name == "RefactoringAgent"
        assert context.user_query == "Function has cognitive complexity 15"
        assert context.workflow_phase == "comprehensive_hooks"

    def test_context_extracts_alternatives(self) -> None:
        """Test that alternatives are extracted from candidates."""
        candidates = []

        for name in ["AgentA", "AgentB", "RefactoringAgent"]:
            mock_agent = MagicMock()
            mock_agent.name = name
            candidates.append(mock_agent)

        context = SkillExecutionContext.from_agent_execution(
            agent_name="RefactoringAgent",
            issue=None,
            workflow_phase="execution",
            candidates=candidates,
        )

        # Alternatives should include other candidates but not selected agent
        assert "AgentA" in context.alternatives_considered
        assert "AgentB" in context.alternatives_considered
        assert "RefactoringAgent" not in context.alternatives_considered


# ============================================================================
# Ranking Tests
# ============================================================================


class TestRecommendationRanking:
    """Test recommendation ranking and selection."""

    @patch("crackerjack.integration.session_buddy_skills_compat.get_session_tracker")
    def test_selection_rank_tracked(self, mock_get_tracker) -> None:
        """Test that selection rank is tracked."""
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.track_invocation.return_value = lambda **kwargs: None
        mock_get_tracker.return_value = mock_tracker_instance

        tracker = SessionBuddyDirectTracker(session_id="test-session")

        # Track with selection rank
        completer = tracker.track_invocation(
            skill_name="RefactoringAgent",
            selection_rank=1,  # First choice
            alternatives_considered=["AgentA", "AgentB"],
        )

        assert completer is not None

        # Verify rank was passed
        mock_tracker_instance.track_invocation.assert_called_once()
        call_args = mock_tracker_instance.track_invocation.call_args[1]
        assert call_args["selection_rank"] == 1

    @patch("crackerjack.integration.session_buddy_skills_compat.get_session_tracker")
    def test_alternatives_considered_tracked(self, mock_get_tracker) -> None:
        """Test that alternatives are tracked."""
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.track_invocation.return_value = lambda **kwargs: None
        mock_get_tracker.return_value = mock_tracker_instance

        tracker = SessionBuddyDirectTracker(session_id="test-session")

        # Track with alternatives
        completer = tracker.track_invocation(
            skill_name="RefactoringAgent",
            alternatives_considered=["AgentA", "AgentB", "AgentC"],
        )

        assert completer is not None

        # Verify alternatives were passed
        mock_tracker_instance.track_invocation.assert_called_once()
        call_args = mock_tracker_instance.track_invocation.call_args[1]
        assert call_args["alternatives_considered"] == ["AgentA", "AgentB", "AgentC"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
