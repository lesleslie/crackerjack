"""Integration tests for skills tracking with session-buddy.

These tests verify that crackerjack's skills tracking integration
works correctly with session-buddy.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType
from crackerjack.integration.skills_tracking import (
    NoOpSkillsTracker,
    SessionBuddyDirectTracker,
    SessionBuddyMCPTracker,
    SkillExecutionContext,
    create_skills_tracker,
)


# ============================================================================
# NoOpSkillsTracker Tests
# ============================================================================


class TestNoOpSkillsTracker:
    """Test no-op tracker when skills tracking is disabled."""

    def test_track_invocation_returns_none(self) -> None:
        """Test that tracking returns None (no-op)."""
        tracker = NoOpSkillsTracker()

        completer = tracker.track_invocation(
            skill_name="TestAgent",
            user_query="test query",
        )

        assert completer is None
        assert tracker.is_enabled() is False
        assert tracker.get_backend() == "none"

    def test_get_recommendations_returns_empty(self) -> None:
        """Test that recommendations return empty list."""
        tracker = NoOpSkillsTracker()

        recommendations = tracker.get_recommendations(
            user_query="test query",
            limit=5,
        )

        assert recommendations == []


# ============================================================================
# SessionBuddyDirectTracker Tests
# ============================================================================


class TestSessionBuddyDirectTracker:
    """Test direct integration with session-buddy."""

    def test_tracker_initialization(self) -> None:
        """Test tracker initialization with session ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "skills.db"

            tracker = SessionBuddyDirectTracker(
                session_id="test-session",
                db_path=db_path,
            )

            assert tracker.session_id == "test-session"
            assert tracker.db_path == db_path

    @patch("crackerjack.integration.skills_tracking.get_session_tracker")
    def test_track_invocation_with_mock(self, mock_get_tracker) -> None:
        """Test tracking with mocked session-buddy."""
        # Mock the skills tracker
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.track_invocation.return_value = lambda **kwargs: None
        mock_get_tracker.return_value = mock_tracker_instance

        tracker = SessionBuddyDirectTracker(session_id="test-session")

        completer = tracker.track_invocation(
            skill_name="RefactoringAgent",
            user_query="fix complexity",
            workflow_phase="comprehensive_hooks",
        )

        # Should return completer function
        assert completer is not None

        # Verify session-buddy was called
        mock_tracker_instance.track_invocation.assert_called_once()
        call_kwargs = mock_tracker_instance.track_invocation.call_args[1]
        assert call_kwargs["skill_name"] == "RefactoringAgent"
        assert call_kwargs["workflow_path"] == "comprehensive_hooks"

    @patch("crackerjack.integration.skills_tracking.get_session_tracker")
    def test_get_recommendations_with_mock(self, mock_get_tracker) -> None:
        """Test recommendations with mocked session-buddy."""
        # Mock the skills tracker
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.recommend_skills.return_value = [
            {
                "skill_name": "TestAgent",
                "similarity_score": 0.85,
                "completed": True,
            }
        ]
        mock_get_tracker.return_value = mock_tracker_instance

        tracker = SessionBuddyDirectTracker(session_id="test-session")

        recommendations = tracker.get_recommendations(
            user_query="fix type errors",
            limit=5,
        )

        assert len(recommendations) == 1
        assert recommendations[0]["skill_name"] == "TestAgent"
        assert recommendations[0]["similarity_score"] == 0.85


# ============================================================================
# SessionBuddyMCPTracker Tests
# ============================================================================


class TestSessionBuddyMCPTracker:
    """Test MCP bridge with session-buddy."""

    def test_tracker_initialization(self) -> None:
        """Test MCP tracker initialization."""
        tracker = SessionBuddyMCPTracker(
            session_id="test-session",
            mcp_server_url="http://localhost:9999",
        )

        assert tracker.session_id == "test-session"
        assert tracker.mcp_server_url == "http://localhost:9999"

    def test_tracker_uses_fallback_on_mcp_unavailable(self) -> None:
        """Test that tracker falls back to direct tracking when MCP unavailable."""
        tracker = SessionBuddyMCPTracker(session_id="test-session")

        # With mock MCP unavailable, should have fallback
        assert tracker._fallback_tracker is not None
        assert tracker.is_enabled() is True
        assert "fallback" in tracker.get_backend()


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestCreateSkillsTracker:
    """Test the factory function for creating trackers."""

    def test_create_disabled_tracker(self) -> None:
        """Test creating disabled tracker."""
        tracker = create_skills_tracker(
            session_id="test-session",
            enabled=False,
        )

        assert isinstance(tracker, NoOpSkillsTracker)
        assert tracker.is_enabled() is False

    @patch("crackerjack.integration.skills_tracking.SessionBuddyDirectTracker")
    def test_create_direct_tracker(self, mock_direct_class) -> None:
        """Test creating direct tracker."""
        tracker = create_skills_tracker(
            session_id="test-session",
            enabled=True,
            backend="direct",
        )

        # Should create direct tracker
        mock_direct_class.assert_called_once()
        # Note: Can't assert type because we mocked it

    @patch("crackerjack.integration.skills_tracking.SessionBuddyMCPTracker")
    def test_create_mcp_tracker(self, mock_mcp_class) -> None:
        """Test creating MCP tracker."""
        tracker = create_skills_tracker(
            session_id="test-session",
            enabled=True,
            backend="mcp",
        )

        # Should create MCP tracker
        mock_mcp_class.assert_called_once()

    @patch("crackerjack.integration.skills_tracking.SessionBuddyMCPTracker")
    def test_create_auto_tracker_with_mcp_available(self, mock_mcp_class) -> None:
        """Test auto backend tries MCP first."""
        # Mock MCP tracker as available and connected
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.is_enabled.return_value = True
        mock_mcp_class.return_value = mock_mcp_instance

        tracker = create_skills_tracker(
            session_id="test-session",
            enabled=True,
            backend="auto",
        )

        # Should try MCP first
        mock_mcp_class.assert_called_once()

    @patch("crackerjack.integration.skills_tracking.SessionBuddyMCPTracker")
    @patch("crackerjack.integration.skills_tracking.SessionBuddyDirectTracker")
    def test_create_auto_tracker_falls_back_to_direct(
        self, mock_direct_class, mock_mcp_class
    ) -> None:
        """Test auto backend falls back to direct when MCP unavailable."""
        # Mock MCP tracker as unavailable
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.is_enabled.return_value = False
        mock_mcp_class.return_value = mock_mcp_instance

        tracker = create_skills_tracker(
            session_id="test-session",
            enabled=True,
            backend="auto",
        )

        # Should fallback to direct
        mock_direct_class.assert_called_once()


# ============================================================================
# AgentContext Integration Tests
# ============================================================================


class TestAgentContextIntegration:
    """Test AgentContext skills tracking integration."""

    def test_context_without_skills_tracker(self) -> None:
        """Test context without skills tracker (disabled)."""
        context = AgentContext(
            project_path=Path("/tmp/test"),
        )

        # Tracking should return None
        completer = context.track_skill_invocation(
            skill_name="TestAgent",
        )

        assert completer is None

    def test_context_with_skills_tracker(self) -> None:
        """Test context with skills tracker enabled."""
        mock_tracker = MagicMock()
        mock_tracker.track_invocation.return_value = lambda **kwargs: None

        context = AgentContext(
            project_path=Path("/tmp/test"),
            skills_tracker=mock_tracker,
        )

        # Call tracking
        completer = context.track_skill_invocation(
            skill_name="TestAgent",
            user_query="test query",
        )

        # Verify tracker was called
        mock_tracker.track_invocation.assert_called_once()

    def test_get_skill_recommendations(self) -> None:
        """Test getting recommendations through context."""
        mock_tracker = MagicMock()
        mock_tracker.get_recommendations.return_value = [
            {"skill_name": "TestAgent", "similarity_score": 0.9}
        ]

        context = AgentContext(
            project_path=Path("/tmp/test"),
            skills_tracker=mock_tracker,
        )

        recommendations = context.get_skill_recommendations(
            user_query="fix bugs",
            limit=5,
        )

        assert len(recommendations) == 1
        mock_tracker.get_recommendations.assert_called_once()


# ============================================================================
# SkillExecutionContext Tests
# ============================================================================


class TestSkillExecutionContext:
    """Test skill execution context data normalizer."""

    def test_from_agent_execution_basic(self) -> None:
        """Test creating context from basic agent execution."""
        # Mock agent
        mock_agent = MagicMock()
        mock_agent.name = "RefactoringAgent"

        context = SkillExecutionContext.from_agent_execution(
            agent_name=mock_agent.name,
            issue=None,
            workflow_phase="comprehensive_hooks",
            candidates=None,
        )

        assert context.skill_name == "RefactoringAgent"
        assert context.workflow_phase == "comprehensive_hooks"

    def test_from_agent_execution_with_issue(self) -> None:
        """Test creating context with issue."""
        # Mock agent and issue
        mock_agent = MagicMock()
        mock_agent.name = "RefactoringAgent"

        mock_issue = MagicMock()
        mock_issue.message = "Fix complexity issues"

        context = SkillExecutionContext.from_agent_execution(
            agent_name=mock_agent.name,
            issue=mock_issue,
            workflow_phase="fast_hooks",
            candidates=None,
        )

        assert context.user_query == "Fix complexity issues"
        assert context.workflow_phase == "fast_hooks"

    def test_from_agent_execution_with_candidates(self) -> None:
        """Test creating context with candidate agents."""
        # Mock agents
        agents = []
        for name in ["AgentA", "AgentB", "AgentC"]:
            mock_agent = MagicMock()
            mock_agent.name = name
            agents.append(mock_agent)

        context = SkillExecutionContext.from_agent_execution(
            agent_name="AgentB",  # Selected agent
            issue=None,
            workflow_phase="execution",
            candidates=agents,
        )

        # Alternatives should exclude selected agent
        assert "AgentA" in context.alternatives_considered
        assert "AgentC" in context.alternatives_considered
        assert "AgentB" not in context.alternatives_considered

        assert context.selection_rank == 1  # First choice


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestSkillsTrackingErrorHandling:
    """Test error handling in skills tracking."""

    def test_tracker_gracefully_handles_import_error(self) -> None:
        """Test that import errors are handled gracefully."""
        # Patch to simulate import error
        with patch(
            "crackerjack.integration.skills_tracking.get_session_tracker",
            side_effect=ImportError("session-buddy not available"),
        ):
            tracker = SessionBuddyDirectTracker(session_id="test-session")

            # Should not raise exception, just log warning
            assert tracker._skills_tracker is None
            assert tracker.is_enabled() is False

    def test_tracker_gracefully_handles_tracking_error(self) -> None:
        """Test that tracking errors are handled gracefully."""
        mock_tracker = MagicMock()
        mock_tracker.track_invocation.side_effect = Exception("Tracking failed!")

        context = AgentContext(
            project_path=Path("/tmp/test"),
            skills_tracker=mock_tracker,
        )

        # Should not raise, just log warning
        completer = context.track_skill_invocation(skill_name="TestAgent")

        # Should return None on error
        assert completer is None

    def test_recommendations_error_returns_empty_list(self) -> None:
        """Test that recommendation errors return empty list."""
        mock_tracker = MagicMock()
        mock_tracker.get_recommendations.side_effect = Exception("Recommendation failed!")

        context = AgentContext(
            project_path=Path("/tmp/test"),
            skills_tracker=mock_tracker,
        )

        recommendations = context.get_skill_recommendations(user_query="test")

        assert recommendations == []


# ============================================================================
# Configuration Tests
# ============================================================================


class TestSkillsConfiguration:
    """Test skills tracking configuration."""

    def test_settings_has_skills_config(self) -> None:
        """Test that CrackerjackSettings includes skills configuration."""
        from crackerjack.config.settings import CrackerjackSettings, SkillsSettings

        settings = CrackerjackSettings()

        # Should have skills config
        assert isinstance(settings.skills, SkillsSettings)
        assert hasattr(settings.skills, "enabled")
        assert hasattr(settings.skills, "backend")

    def test_default_configuration(self) -> None:
        """Test default configuration values."""
        from crackerjack.config.settings import SkillsSettings

        settings = SkillsSettings()

        assert settings.enabled is True  # Default enabled
        assert settings.backend == "auto"  # Auto-detect backend
        assert settings.db_path is None  # Use default path
        assert settings.mcp_server_url == "http://localhost:8678"
        assert settings.min_similarity == 0.3
        assert settings.max_recommendations == 5

    def test_backend_choice_direct(self) -> None:
        """Test direct backend configuration."""
        settings = SkillsSettings(backend="direct")

        assert settings.backend == "direct"

    def test_backend_choice_mcp(self) -> None:
        """Test MCP backend configuration."""
        settings = SkillsSettings(backend="mcp")

        assert settings.backend == "mcp"

    def test_backend_choice_auto(self) -> None:
        """Test auto backend configuration."""
        settings = SkillsSettings(backend="auto")

        assert settings.backend == "auto"

    def test_disabled_configuration(self) -> None:
        """Test disabled configuration."""
        settings = SkillsSettings(enabled=False)

        assert settings.enabled is False
