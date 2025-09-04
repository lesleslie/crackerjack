"""Unit tests for SessionLifecycleManager.

Tests the session lifecycle operations including quality assessment,
checkpoints, and cleanup functionality.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from session_mgmt_mcp.core.session_manager import SessionLifecycleManager


class TestSessionLifecycleManager:
    """Test suite for SessionLifecycleManager."""

    @pytest.fixture
    def session_manager(self):
        """Create SessionLifecycleManager instance."""
        return SessionLifecycleManager()

    @pytest.mark.asyncio
    async def test_calculate_quality_score_with_uv(self, session_manager):
        """Test quality score calculation when UV is available."""
        with patch("shutil.which", return_value="/usr/bin/uv"):
            with patch.object(
                session_manager, "analyze_project_context", new_callable=AsyncMock
            ) as mock_analyze:
                mock_analyze.return_value = {
                    "has_pyproject_toml": True,
                    "has_git_repo": True,
                    "has_tests": True,
                    "has_docs": True,
                }

                result = await session_manager.calculate_quality_score()

                assert "total_score" in result
                assert "breakdown" in result
                assert "recommendations" in result
                assert result["total_score"] >= 80  # Should be high with UV

    @pytest.mark.asyncio
    async def test_calculate_quality_score_without_uv(self, session_manager):
        """Test quality score calculation when UV is not available."""
        with patch("shutil.which", return_value=None):
            with patch.object(
                session_manager, "analyze_project_context", new_callable=AsyncMock
            ) as mock_analyze:
                mock_analyze.return_value = {
                    "has_pyproject_toml": True,
                    "has_git_repo": True,
                    "has_tests": True,
                    "has_docs": True,
                }

                result = await session_manager.calculate_quality_score()

                assert "total_score" in result
                assert result["total_score"] < 90  # Should be lower without UV

    @pytest.mark.asyncio
    async def test_analyze_project_context(self, session_manager):
        """Test project context analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            # Create project files
            (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_dir / ".git").mkdir()
            (project_dir / "tests").mkdir()
            (project_dir / "README.md").write_text("# Test Project")
            (project_dir / "src").mkdir()
            (project_dir / "docs").mkdir()

            result = await session_manager.analyze_project_context(project_dir)

            assert isinstance(result, dict)
            assert result["has_pyproject_toml"] is True
            assert result["has_git_repo"] is True
            assert result["has_tests"] is True
            assert result["has_docs"] is True

    @pytest.mark.asyncio
    async def test_analyze_project_context_empty_directory(self, session_manager):
        """Test project context analysis with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            result = await session_manager.analyze_project_context(project_dir)

            assert isinstance(result, dict)
            # All should be False for empty directory
            assert all(value is False for value in result.values())

    @pytest.mark.asyncio
    async def test_perform_quality_assessment(self, session_manager):
        """Test quality assessment performance."""
        with patch.object(
            session_manager, "calculate_quality_score", new_callable=AsyncMock
        ) as mock_calculate:
            mock_calculate.return_value = {
                "total_score": 85,
                "breakdown": {
                    "project_health": 35.0,
                    "permissions": 15.0,
                    "session_management": 20.0,
                    "tools": 15.0,
                },
                "recommendations": ["Install UV for better dependency management"],
            }

            (
                quality_score,
                quality_data,
            ) = await session_manager.perform_quality_assessment()

            assert isinstance(quality_score, int)
            assert isinstance(quality_data, dict)
            assert quality_score == 85
            assert "breakdown" in quality_data

    @pytest.mark.asyncio
    async def test_format_quality_results(self, session_manager):
        """Test quality results formatting."""
        quality_score = 85
        quality_data = {
            "total_score": 85,
            "breakdown": {
                "project_health": 35.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 15.0,
            },
            "recommendations": ["Install UV for better dependency management"],
        }

        result = session_manager.format_quality_results(quality_score, quality_data)

        assert isinstance(result, list)
        assert len(result) > 0
        # Should contain quality status
        assert any("Session quality" in line for line in result)
        # Should contain breakdown
        assert any("Quality breakdown" in line for line in result)

    @pytest.mark.asyncio
    async def test_initialize_session(self, session_manager):
        """Test session initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)

            # Create a simple project structure
            (working_dir / "README.md").write_text("# Test Project")

            with patch.dict(os.environ, {"PWD": str(working_dir)}):
                result = await session_manager.initialize_session(str(working_dir))

                assert isinstance(result, dict)
                assert "success" in result
                assert result["success"] is True
                assert "project" in result
                assert "quality_score" in result

    @pytest.mark.asyncio
    async def test_checkpoint_session(self, session_manager):
        """Test session checkpoint creation."""
        # Mock the Path.cwd() to avoid FileNotFoundError
        with patch("pathlib.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/tmp/test")

            with patch.object(
                session_manager, "perform_quality_assessment", new_callable=AsyncMock
            ) as mock_assessment:
                mock_assessment.return_value = (
                    85,
                    {"total_score": 85, "breakdown": {}, "recommendations": []},
                )

                with patch.object(
                    session_manager, "perform_git_checkpoint", new_callable=AsyncMock
                ) as mock_git:
                    mock_git.return_value = ["Git checkpoint completed"]

                    with patch.object(
                        session_manager, "format_quality_results"
                    ) as mock_format:
                        mock_format.return_value = ["Quality: Excellent (85/100)"]

                        # Mock the logger to avoid AttributeError
                        with patch.object(session_manager, "logger"):
                            result = await session_manager.checkpoint_session()

                            assert isinstance(result, dict)
                            assert "success" in result
                            assert result["success"] is True
                            assert "quality_score" in result
                            assert result["quality_score"] == 85

    @pytest.mark.asyncio
    async def test_end_session(self, session_manager):
        """Test session ending."""
        # Mock the Path.cwd() to avoid FileNotFoundError
        with patch("pathlib.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/tmp/test")

            with patch.object(
                session_manager, "perform_quality_assessment", new_callable=AsyncMock
            ) as mock_assessment:
                mock_assessment.return_value = (
                    85,
                    {"total_score": 85, "breakdown": {}, "recommendations": []},
                )

                # Mock the logger to avoid AttributeError
                with patch.object(session_manager, "logger"):
                    result = await session_manager.end_session()

                    assert isinstance(result, dict)
                    assert "success" in result
                    assert result["success"] is True
                    assert "summary" in result
                    assert isinstance(result["summary"], dict)

    @pytest.mark.asyncio
    async def test_get_session_status(self, session_manager):
        """Test session status retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)
            (working_dir / "README.md").write_text("# Test Project")

            with patch.dict(os.environ, {"PWD": str(working_dir)}):
                # Mock the Path.cwd() to avoid FileNotFoundError
                with patch("pathlib.Path.cwd") as mock_cwd:
                    mock_cwd.return_value = working_dir

                    with patch.object(
                        session_manager,
                        "analyze_project_context",
                        new_callable=AsyncMock,
                    ) as mock_analyze:
                        mock_analyze.return_value = {
                            "has_pyproject_toml": False,
                            "has_git_repo": False,
                            "has_tests": False,
                            "has_docs": False,
                        }

                        with patch.object(
                            session_manager,
                            "perform_quality_assessment",
                            new_callable=AsyncMock,
                        ) as mock_assessment:
                            mock_assessment.return_value = (
                                50,
                                {
                                    "total_score": 50,
                                    "breakdown": {},
                                    "recommendations": [],
                                },
                            )

                            # Mock the logger and git operations
                            with patch.object(session_manager, "logger"):
                                with patch(
                                    "session_mgmt_mcp.core.session_manager.is_git_repository",
                                    return_value=False,
                                ):
                                    result = await session_manager.get_session_status(
                                        str(working_dir)
                                    )

                                    assert isinstance(result, dict)
                                    assert "success" in result
                                    assert result["success"] is True
                                    assert "project" in result
                                    assert "quality_score" in result
