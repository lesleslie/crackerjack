#!/usr/bin/env python3
"""Unit tests for SessionLifecycleManager class."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from session_mgmt_mcp.core.session_manager import SessionLifecycleManager


class TestSessionLifecycleManagerInitialization:
    """Test SessionLifecycleManager initialization."""

    def test_init(self):
        """Test SessionLifecycleManager initialization."""
        with patch(
            "session_mgmt_mcp.core.session_manager.get_session_logger"
        ) as mock_logger:
            mock_logger.return_value = Mock()
            manager = SessionLifecycleManager()

            assert manager.current_project is None
            assert manager.logger is not None


class TestSessionLifecycleManagerProjectContext:
    """Test SessionLifecycleManager project context analysis."""

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_analyze_project_context_basic_files(self, mock_is_git_repo):
        """Test analyze_project_context with basic project files."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            # Create some project files
            (project_dir / "pyproject.toml").touch()
            (project_dir / "README.md").touch()
            (project_dir / "tests").mkdir()
            (project_dir / ".venv").mkdir()

            result = await manager.analyze_project_context(project_dir)

            assert result["has_pyproject_toml"] is True
            assert result["has_readme"] is True
            assert result["has_git_repo"] is True
            assert result["has_tests"] is True
            assert result["has_venv"] is True

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_analyze_project_context_no_files(self, mock_is_git_repo):
        """Test analyze_project_context with no project files."""
        mock_is_git_repo.return_value = False

        manager = SessionLifecycleManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            result = await manager.analyze_project_context(project_dir)

            # Should all be False except has_python_files which depends on glob
            assert result["has_git_repo"] is False
            assert result["has_pyproject_toml"] is False
            assert result["has_setup_py"] is False
            assert result["has_requirements_txt"] is False

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_analyze_project_context_python_files(self, mock_is_git_repo):
        """Test analyze_project_context detection of Python frameworks."""
        mock_is_git_repo.return_value = False

        manager = SessionLifecycleManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            # Create a Python file with framework imports
            python_file = project_dir / "app.py"
            with open(python_file, "w") as f:
                f.write("""
import fastapi
from django.http import HttpResponse
import flask
""")

            result = await manager.analyze_project_context(project_dir)

            # Should detect Python files
            assert result["has_python_files"] is True

            # Should detect frameworks (first 10 files are checked)
            assert result["uses_fastapi"] is True
            assert result["uses_django"] is True
            assert result["uses_flask"] is True

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_analyze_project_context_file_analysis_error(self, mock_is_git_repo):
        """Test analyze_project_context handles file analysis errors."""
        mock_is_git_repo.return_value = False

        manager = SessionLifecycleManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            # Create a file that will cause permission error when read
            python_file = project_dir / "app.py"
            python_file.touch()

            # Mock glob to return the file, but make reading it fail
            with patch.object(project_dir, "glob", return_value=[python_file]):
                with patch(
                    "builtins.open", side_effect=PermissionError("Permission denied")
                ):
                    result = await manager.analyze_project_context(project_dir)

                    # Should still work, just with warnings logged
                    assert isinstance(result, dict)
                    # Logger should have been called with warning
                    # We can't easily test this without more complex mocking


class TestSessionLifecycleManagerQualityScore:
    """Test SessionLifecycleManager quality score calculation."""

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    @patch("shutil.which")
    async def test_calculate_quality_score_all_factors(
        self, mock_which, mock_is_git_repo
    ):
        """Test calculate_quality_score with all positive factors."""
        mock_is_git_repo.return_value = True
        mock_which.return_value = "/usr/local/bin/uv"  # UV available

        manager = SessionLifecycleManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / "pyproject.toml").touch()
            (project_dir / "README.md").touch()
            (project_dir / "tests").mkdir()

            # Mock analyze_project_context to return positive results
            with patch.object(manager, "analyze_project_context") as mock_analyze:
                mock_analyze.return_value = {
                    "has_pyproject_toml": True,
                    "has_readme": True,
                    "has_git_repo": True,
                    "has_tests": True,
                    "has_venv": True,
                }

                # Mock permissions manager
                with patch(
                    "session_mgmt_mcp.core.session_manager.permissions_manager"
                ) as mock_perms:
                    mock_perms.trusted_operations = {"op1", "op2", "op3", "op4", "op5"}

                    result = await manager.calculate_quality_score()

                    assert "total_score" in result
                    assert "breakdown" in result
                    assert "recommendations" in result
                    assert isinstance(result["total_score"], int)
                    assert 0 <= result["total_score"] <= 100

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    @patch("shutil.which")
    async def test_calculate_quality_score_low_quality(
        self, mock_which, mock_is_git_repo
    ):
        """Test calculate_quality_score with low quality factors."""
        mock_is_git_repo.return_value = False
        mock_which.return_value = None  # UV not available

        manager = SessionLifecycleManager()
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir)

            # Mock analyze_project_context to return negative results
            with patch.object(manager, "analyze_project_context") as mock_analyze:
                mock_analyze.return_value = {
                    "has_pyproject_toml": False,
                    "has_readme": False,
                    "has_git_repo": False,
                    "has_tests": False,
                    "has_venv": False,
                }

                # Mock permissions manager with no trusted operations
                with patch(
                    "session_mgmt_mcp.core.session_manager.permissions_manager"
                ) as mock_perms:
                    mock_perms.trusted_operations = set()

                    result = await manager.calculate_quality_score()

                    assert result["total_score"] < 50  # Should be low quality
                    assert any(
                        "attention" in rec.lower() for rec in result["recommendations"]
                    )

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_generate_quality_recommendations(self, mock_is_git_repo):
        """Test _generate_quality_recommendations method."""
        mock_is_git_repo.return_value = False
        manager = SessionLifecycleManager()

        # Test low score recommendations
        recommendations = manager._generate_quality_recommendations(
            score=30,
            project_context={
                "has_pyproject_toml": False,
                "has_git_repo": False,
                "has_tests": False,
            },
            uv_available=False,
        )

        assert any("attention" in rec.lower() for rec in recommendations)
        assert any("pyproject.toml" in rec for rec in recommendations)
        assert any("git repository" in rec for rec in recommendations)
        assert any("uv package manager" in rec for rec in recommendations)
        assert any("test suite" in rec for rec in recommendations)

        # Test high score recommendations
        recommendations = manager._generate_quality_recommendations(
            score=90,
            project_context={
                "has_pyproject_toml": True,
                "has_git_repo": True,
                "has_tests": True,
            },
            uv_available=True,
        )

        assert any("excellent" in rec.lower() for rec in recommendations)

        # Test medium score recommendations
        recommendations = manager._generate_quality_recommendations(
            score=70,
            project_context={
                "has_pyproject_toml": True,
                "has_git_repo": True,
                "has_tests": True,
            },
            uv_available=True,
        )

        assert any("good session quality" in rec.lower() for rec in recommendations)


class TestSessionLifecycleManagerQualityAssessment:
    """Test SessionLifecycleManager quality assessment methods."""

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_perform_quality_assessment(self, mock_is_git_repo):
        """Test perform_quality_assessment method."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()

        # Mock calculate_quality_score to return known values
        mock_quality_result = {
            "total_score": 85,
            "breakdown": {
                "project_health": 30.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 20.0,
            },
            "recommendations": ["Good setup!"],
        }

        with patch.object(
            manager, "calculate_quality_score", return_value=mock_quality_result
        ):
            quality_score, quality_data = await manager.perform_quality_assessment()

            assert quality_score == 85
            assert quality_data == mock_quality_result

    def test_format_quality_results_high_score(self):
        """Test format_quality_results with high quality score."""
        manager = SessionLifecycleManager()

        quality_score = 85
        quality_data = {
            "breakdown": {
                "project_health": 30.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 20.0,
            },
            "recommendations": ["Excellent setup!"],
        }

        result = manager.format_quality_results(quality_score, quality_data)

        assert any("excellent" in line.lower() for line in result)
        assert any("85/100" in line for line in result)
        assert any("project health" in line.lower() for line in result)
        assert any("recommendations" in line.lower() for line in result)

    def test_format_quality_results_medium_score(self):
        """Test format_quality_results with medium quality score."""
        manager = SessionLifecycleManager()

        quality_score = 65
        quality_data = {
            "breakdown": {
                "project_health": 25.0,
                "permissions": 10.0,
                "session_management": 20.0,
                "tools": 10.0,
            },
            "recommendations": ["Good setup with room for improvement"],
        }

        result = manager.format_quality_results(quality_score, quality_data)

        assert any("good" in line.lower() for line in result)
        assert any("65/100" in line for line in result)

    def test_format_quality_results_low_score(self):
        """Test format_quality_results with low quality score."""
        manager = SessionLifecycleManager()

        quality_score = 45
        quality_data = {
            "breakdown": {
                "project_health": 15.0,
                "permissions": 5.0,
                "session_management": 20.0,
                "tools": 5.0,
            },
            "recommendations": ["Needs attention"],
        }

        result = manager.format_quality_results(quality_score, quality_data)

        assert any("attention" in line.lower() for line in result)
        assert any("45/100" in line for line in result)

    def test_format_quality_results_with_checkpoint_result(self):
        """Test format_quality_results with checkpoint result data."""
        manager = SessionLifecycleManager()

        quality_score = 80
        quality_data = {
            "breakdown": {
                "project_health": 30.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 15.0,
            },
            "recommendations": ["Great work!"],
        }

        checkpoint_result = {
            "strengths": ["Good progress", "Consistent coding"],
            "session_stats": {
                "duration_minutes": 45,
                "total_checkpoints": 3,
                "success_rate": 95.5,
            },
        }

        result = manager.format_quality_results(
            quality_score, quality_data, checkpoint_result
        )

        assert any("strengths" in line.lower() for line in result)
        assert any("session progress" in line.lower() for line in result)
        assert any("45 minutes" in line for line in result)
        assert any("3 checkpoints" in line for line in result)
        assert any("95.5%" in line for line in result)


class TestSessionLifecycleManagerGitCheckpoint:
    """Test SessionLifecycleManager git checkpoint methods."""

    @patch("session_mgmt_mcp.core.session_manager.create_checkpoint_commit")
    async def test_perform_git_checkpoint_success(self, mock_create_checkpoint):
        """Test perform_git_checkpoint with successful operation."""
        mock_create_checkpoint.return_value = (
            True,
            "abc123",
            ["✅ Checkpoint created"],
        )

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            result = await manager.perform_git_checkpoint(project_dir, 85)

            assert "📦 Git Checkpoint Commit" in result
            assert "✅ Checkpoint created" in result
            mock_create_checkpoint.assert_called_once_with(
                project_dir, "test-project", 85
            )

    @patch("session_mgmt_mcp.core.session_manager.create_checkpoint_commit")
    async def test_perform_git_checkpoint_exception(self, mock_create_checkpoint):
        """Test perform_git_checkpoint with exception."""
        mock_create_checkpoint.side_effect = Exception("Git error")

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            result = await manager.perform_git_checkpoint(project_dir, 85)

            assert any("git operations error" in line.lower() for line in result)
            assert any("git error" in line.lower() for line in result)


class TestSessionLifecycleManagerSessionInitialization:
    """Test SessionLifecycleManager session initialization."""

    @patch("os.chdir")
    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_initialize_session_success(self, mock_is_git_repo, mock_chdir):
        """Test initialize_session with successful operation."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()

        # Mock the methods that are called
        mock_project_context = {
            "has_pyproject_toml": True,
            "has_git_repo": True,
        }

        mock_quality_data = {
            "total_score": 80,
            "breakdown": {
                "project_health": 30.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 15.0,
            },
            "recommendations": ["Good setup"],
        }

        with patch.object(
            manager, "analyze_project_context", return_value=mock_project_context
        ):
            with patch.object(
                manager,
                "perform_quality_assessment",
                return_value=(80, mock_quality_data),
            ):
                with patch.object(
                    manager, "_find_latest_handoff_file", return_value=None
                ):
                    with tempfile.TemporaryDirectory() as temp_dir:
                        result = await manager.initialize_session(temp_dir)

                        assert result["success"] is True
                        assert result["project"] is not None
                        assert result["quality_score"] == 80
                        assert "claude_directory" in result

    @patch("os.chdir")
    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_initialize_session_exception(self, mock_is_git_repo, mock_chdir):
        """Test initialize_session with exception."""
        mock_is_git_repo.return_value = True
        mock_chdir.side_effect = Exception("Chdir failed")

        manager = SessionLifecycleManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            result = await manager.initialize_session(temp_dir)

            assert result["success"] is False
            assert "chdir failed" in result["error"].lower()


class TestSessionLifecycleManagerCheckpoint:
    """Test SessionLifecycleManager session checkpoint."""

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_checkpoint_session_success(self, mock_is_git_repo):
        """Test checkpoint_session with successful operation."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        # Mock the methods that are called
        mock_quality_data = {
            "total_score": 85,
            "breakdown": {
                "project_health": 30.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 20.0,
            },
            "recommendations": ["Excellent setup"],
        }

        mock_git_output = ["✅ Git checkpoint successful"]

        with patch.object(
            manager, "perform_quality_assessment", return_value=(85, mock_quality_data)
        ):
            with patch.object(
                manager, "perform_git_checkpoint", return_value=mock_git_output
            ):
                with patch.object(
                    manager,
                    "format_quality_results",
                    return_value=["✅ Quality: 85/100"],
                ):
                    result = await manager.checkpoint_session()

                    assert result["success"] is True
                    assert result["quality_score"] == 85
                    assert "quality_output" in result
                    assert "git_output" in result
                    assert "timestamp" in result

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_checkpoint_session_exception(self, mock_is_git_repo):
        """Test checkpoint_session with exception."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        with patch.object(
            manager,
            "perform_quality_assessment",
            side_effect=Exception("Checkpoint failed"),
        ):
            result = await manager.checkpoint_session()

            assert result["success"] is False
            assert "checkpoint failed" in result["error"].lower()


class TestSessionLifecycleManagerSessionEnd:
    """Test SessionLifecycleManager session end."""

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_end_session_success(self, mock_is_git_repo):
        """Test end_session with successful operation."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        # Mock the methods that are called
        mock_quality_data = {
            "total_score": 90,
            "breakdown": {
                "project_health": 35.0,
                "permissions": 20.0,
                "session_management": 20.0,
                "tools": 15.0,
            },
            "recommendations": ["Excellent work"],
        }

        with patch.object(
            manager, "perform_quality_assessment", return_value=(90, mock_quality_data)
        ):
            with patch.object(
                manager,
                "_generate_handoff_documentation",
                return_value="# Handoff Report",
            ):
                with patch.object(
                    manager,
                    "_save_handoff_documentation",
                    return_value=Path("/tmp/handoff.md"),
                ):
                    result = await manager.end_session()

                    assert result["success"] is True
                    assert "summary" in result
                    assert result["summary"]["final_quality_score"] == 90
                    assert "handoff_documentation" in result["summary"]

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_end_session_exception(self, mock_is_git_repo):
        """Test end_session with exception."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        with patch.object(
            manager, "perform_quality_assessment", side_effect=Exception("End failed")
        ):
            result = await manager.end_session()

            assert result["success"] is False
            assert "end failed" in result["error"].lower()


class TestSessionLifecycleManagerHandoffDocumentation:
    """Test SessionLifecycleManager handoff documentation methods."""

    def test_generate_handoff_documentation(self):
        """Test _generate_handoff_documentation method."""
        manager = SessionLifecycleManager()

        summary = {
            "project": "test-project",
            "final_quality_score": 85,
            "session_end_time": "2024-01-01T12:00:00Z",
            "working_directory": "/path/to/project",
            "recommendations": ["Great work!", "Consider adding tests"],
        }

        quality_data = {
            "breakdown": {
                "project_health": 30.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 20.0,
            }
        }

        result = manager._generate_handoff_documentation(summary, quality_data)

        assert "# Session Handoff Report - test-project" in result
        assert "85/100" in result
        assert "Great work!" in result
        assert "Consider adding tests" in result
        assert "Quality Assessment" in result

    def test_save_handoff_documentation(self):
        """Test _save_handoff_documentation method."""
        manager = SessionLifecycleManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)
            content = "# Test Handoff"

            result = manager._save_handoff_documentation(content, working_dir)

            assert result is not None
            assert result.exists()
            assert result.name.startswith("session_handoff_")
            assert result.suffix == ".md"

            # Verify content was written
            with open(result) as f:
                saved_content = f.read()
                assert saved_content == content

    def test_save_handoff_documentation_exception(self):
        """Test _save_handoff_documentation with exception."""
        manager = SessionLifecycleManager()

        with patch("pathlib.Path.mkdir", side_effect=Exception("Permission denied")):
            with tempfile.TemporaryDirectory() as temp_dir:
                working_dir = Path(temp_dir)
                content = "# Test Handoff"

                result = manager._save_handoff_documentation(content, working_dir)

                assert result is None  # Should return None on failure

    def test_find_latest_handoff_file(self):
        """Test _find_latest_handoff_file method."""
        manager = SessionLifecycleManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)

            # Create handoff directory and files
            handoff_dir = working_dir / ".crackerjack" / "session" / "handoff"
            handoff_dir.mkdir(parents=True)

            # Create handoff files with timestamps
            old_file = handoff_dir / "session_handoff_20240101_100000.md"
            old_file.touch()

            new_file = handoff_dir / "session_handoff_20240101_120000.md"
            new_file.touch()

            result = manager._find_latest_handoff_file(working_dir)

            assert result == new_file  # Should return the newer file

    def test_find_latest_handoff_file_legacy(self):
        """Test _find_latest_handoff_file with legacy files."""
        manager = SessionLifecycleManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)

            # Create legacy handoff file in project root
            legacy_file = working_dir / "session_handoff_20240101_100000.md"
            legacy_file.touch()

            result = manager._find_latest_handoff_file(working_dir)

            assert result == legacy_file

    def test_read_previous_session_info(self):
        """Test _read_previous_session_info method."""
        manager = SessionLifecycleManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            handoff_file = Path(temp_dir) / "handoff.md"

            # Create handoff content
            content = """
# Session Handoff Report - test-project

**Session ended:** 2024-01-01T12:00:00Z
**Final quality score:** 85/100
**Working directory:** /path/to/project

## Recommendations for Next Session

1. Add more tests to improve coverage
2. Review documentation

## Key Achievements

- Session successfully completed
"""

            with open(handoff_file, "w") as f:
                f.write(content)

            result = manager._read_previous_session_info(handoff_file)

            assert result is not None
            assert result["ended_at"] == "2024-01-01T12:00:00Z"
            assert result["quality_score"] == "85/100"
            assert result["working_directory"] == "/path/to/project"
            assert result["top_recommendation"] == "Add more tests to improve coverage"


class TestSessionLifecycleManagerSessionStatus:
    """Test SessionLifecycleManager session status."""

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    @patch("shutil.which")
    async def test_get_session_status_success(self, mock_which, mock_is_git_repo):
        """Test get_session_status with successful operation."""
        mock_is_git_repo.return_value = True
        mock_which.return_value = "/usr/local/bin/uv"

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        # Mock the methods that are called
        mock_project_context = {
            "has_pyproject_toml": True,
            "has_git_repo": True,
            "has_tests": True,
        }

        mock_quality_data = {
            "total_score": 85,
            "breakdown": {
                "project_health": 30.0,
                "permissions": 15.0,
                "session_management": 20.0,
                "tools": 20.0,
            },
            "recommendations": ["Excellent setup"],
        }

        with patch.object(
            manager, "analyze_project_context", return_value=mock_project_context
        ):
            with patch.object(
                manager,
                "perform_quality_assessment",
                return_value=(85, mock_quality_data),
            ):
                with tempfile.TemporaryDirectory() as temp_dir:
                    result = await manager.get_session_status(temp_dir)

                    assert result["success"] is True
                    assert result["project"] == "test-project"
                    assert result["quality_score"] == 85
                    assert "quality_breakdown" in result
                    assert "recommendations" in result
                    assert "project_context" in result
                    assert "system_health" in result
                    assert result["system_health"]["uv_available"] is True
                    assert result["system_health"]["git_repository"] is True

    @patch("session_mgmt_mcp.core.session_manager.is_git_repository")
    async def test_get_session_status_exception(self, mock_is_git_repo):
        """Test get_session_status with exception."""
        mock_is_git_repo.return_value = True

        manager = SessionLifecycleManager()
        manager.current_project = "test-project"

        with patch.object(
            manager,
            "analyze_project_context",
            side_effect=Exception("Status check failed"),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                result = await manager.get_session_status(temp_dir)

                assert result["success"] is False
                assert "status check failed" in result["error"].lower()


if __name__ == "__main__":
    pytest.main([__file__])
