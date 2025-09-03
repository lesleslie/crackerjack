#!/usr/bin/env python3
"""Session lifecycle management for session-mgmt-mcp.

This module handles session initialization, quality assessment, checkpoints,
and cleanup operations.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from session_mgmt_mcp.utils.git_operations import (
    create_checkpoint_commit,
    is_git_repository,
)
from session_mgmt_mcp.utils.logging import get_session_logger


class SessionLifecycleManager:
    """Manages session lifecycle operations."""

    def __init__(self) -> None:
        self.logger = get_session_logger()
        self.current_project: str | None = None

    async def calculate_quality_score(self) -> dict[str, Any]:
        """Calculate session quality score based on multiple factors."""
        current_dir = Path(os.environ.get("PWD", Path.cwd()))

        # Project health indicators (40% of score)
        project_context = await self.analyze_project_context(current_dir)
        project_score = (
            sum(1 for detected in project_context.values() if detected)
            / len(project_context)
        ) * 40

        # Permissions health (20% of score) - placeholder for now
        permissions_score = 10  # Basic score until permissions system is integrated

        # Session management availability (20% of score)
        session_score = 20  # Always available in this refactored version

        # Tool availability (20% of score)
        uv_available = shutil.which("uv") is not None
        tool_score = 20 if uv_available else 10

        total_score = int(
            project_score + permissions_score + session_score + tool_score,
        )

        return {
            "total_score": total_score,
            "breakdown": {
                "project_health": project_score,
                "permissions": permissions_score,
                "session_management": session_score,
                "tools": tool_score,
            },
            "recommendations": self._generate_quality_recommendations(
                total_score,
                project_context,
                uv_available,
            ),
        }

    def _generate_quality_recommendations(
        self,
        score: int,
        project_context: dict,
        uv_available: bool,
    ) -> list[str]:
        """Generate quality improvement recommendations based on score factors."""
        recommendations = []

        if score < 50:
            recommendations.append(
                "Session needs attention - multiple areas for improvement",
            )

        if not project_context.get("has_pyproject_toml", False):
            recommendations.append(
                "Consider adding pyproject.toml for modern Python project structure",
            )

        if not project_context.get("has_git_repo", False):
            recommendations.append("Initialize git repository for version control")

        if not uv_available:
            recommendations.append(
                "Install UV package manager for improved dependency management",
            )

        if not project_context.get("has_tests", False):
            recommendations.append("Add test suite to improve code quality")

        if score >= 80:
            recommendations.append("Excellent session setup! Keep up the good work.")
        elif score >= 60:
            recommendations.append("Good session quality with room for optimization.")

        return recommendations[:5]  # Limit to top 5 recommendations

    async def analyze_project_context(self, project_dir: Path) -> dict[str, bool]:
        """Analyze project directory for common indicators and patterns."""
        indicators = {
            "has_pyproject_toml": (project_dir / "pyproject.toml").exists(),
            "has_setup_py": (project_dir / "setup.py").exists(),
            "has_requirements_txt": (project_dir / "requirements.txt").exists(),
            "has_readme": any(
                (project_dir / name).exists()
                for name in ["README.md", "README.rst", "README.txt", "readme.md"]
            ),
            "has_git_repo": is_git_repository(project_dir),
            "has_venv": any(
                (project_dir / name).exists()
                for name in [".venv", "venv", ".env", "env"]
            ),
            "has_tests": any(
                (project_dir / name).exists() for name in ["tests", "test", "testing"]
            ),
            "has_src_structure": (project_dir / "src").exists(),
            "has_docs": any(
                (project_dir / name).exists() for name in ["docs", "documentation"]
            ),
            "has_ci_cd": any(
                (project_dir / name).exists()
                for name in [".github", ".gitlab-ci.yml", ".travis.yml", "Jenkinsfile"]
            ),
        }

        # Additional context from file patterns
        try:
            python_files = list(project_dir.glob("**/*.py"))
            indicators["has_python_files"] = len(python_files) > 0

            # Check for common Python frameworks
            for py_file in python_files[:10]:  # Sample first 10 files
                try:
                    with open(py_file, encoding="utf-8") as f:
                        content = f.read(1000)  # Read first 1000 chars
                        if "import fastapi" in content or "from fastapi" in content:
                            indicators["uses_fastapi"] = True
                        if "import django" in content or "from django" in content:
                            indicators["uses_django"] = True
                        if "import flask" in content or "from flask" in content:
                            indicators["uses_flask"] = True
                except (UnicodeDecodeError, PermissionError):
                    continue

        except Exception as e:
            self.logger.warning(f"Error analyzing Python files: {e}")

        return indicators

    async def perform_quality_assessment(self) -> tuple[int, dict]:
        """Perform quality assessment and return score and data."""
        quality_data = await self.calculate_quality_score()
        quality_score = quality_data["total_score"]
        return quality_score, quality_data

    def format_quality_results(
        self,
        quality_score: int,
        quality_data: dict,
        checkpoint_result: dict | None = None,
    ) -> list[str]:
        """Format quality assessment results for display."""
        output = []

        # Quality status
        if quality_score >= 80:
            output.append(f"✅ Session quality: EXCELLENT (Score: {quality_score}/100)")
        elif quality_score >= 60:
            output.append(f"✅ Session quality: GOOD (Score: {quality_score}/100)")
        else:
            output.append(
                f"⚠️ Session quality: NEEDS ATTENTION (Score: {quality_score}/100)",
            )

        # Quality breakdown
        output.append("\n📈 Quality breakdown:")
        breakdown = quality_data["breakdown"]
        output.append(f"   • Project health: {breakdown['project_health']:.1f}/40")
        output.append(f"   • Permissions: {breakdown['permissions']:.1f}/20")
        output.append(f"   • Session tools: {breakdown['session_management']:.1f}/20")
        output.append(f"   • Tool availability: {breakdown['tools']:.1f}/20")

        # Recommendations
        recommendations = quality_data["recommendations"]
        if recommendations:
            output.append("\n💡 Recommendations:")
            for rec in recommendations[:3]:
                output.append(f"   • {rec}")

        # Session management specific results
        if checkpoint_result:
            strengths = checkpoint_result.get("strengths", [])
            if strengths:
                output.append("\n🌟 Session strengths:")
                for strength in strengths[:3]:
                    output.append(f"   • {strength}")

            session_stats = checkpoint_result.get("session_stats", {})
            if session_stats:
                output.append("\n⏱️ Session progress:")
                output.append(
                    f"   • Duration: {session_stats.get('duration_minutes', 0)} minutes",
                )
                output.append(
                    f"   • Checkpoints: {session_stats.get('total_checkpoints', 0)}",
                )
                output.append(
                    f"   • Success rate: {session_stats.get('success_rate', 0):.1f}%",
                )

        return output

    async def perform_git_checkpoint(
        self,
        current_dir: Path,
        quality_score: int,
    ) -> list[str]:
        """Handle git operations for checkpoint commit using the new git utilities."""
        output = []
        output.append("\n" + "=" * 50)
        output.append("📦 Git Checkpoint Commit")
        output.append("=" * 50)

        try:
            # Use the new git utilities
            success, result, git_output = create_checkpoint_commit(
                current_dir,
                self.current_project or "Unknown",
                quality_score,
            )

            output.extend(git_output)

            if success and result != "clean":
                self.logger.info(
                    "Checkpoint commit created",
                    project=self.current_project,
                    commit_hash=result,
                    quality_score=quality_score,
                )

        except Exception as e:
            output.append(f"\n⚠️ Git operations error: {e}")
            self.logger.exception(
                "Git checkpoint error occurred",
                error=str(e),
                project=self.current_project,
            )

        return output

    async def initialize_session(
        self,
        working_directory: str | None = None,
    ) -> dict[str, Any]:
        """Initialize a new session with comprehensive setup."""
        try:
            # Set working directory
            if working_directory:
                os.chdir(working_directory)

            current_dir = Path.cwd()
            self.current_project = current_dir.name

            # Create .claude directory structure
            claude_dir = Path.home() / ".claude"
            claude_dir.mkdir(exist_ok=True)
            (claude_dir / "data").mkdir(exist_ok=True)
            (claude_dir / "logs").mkdir(exist_ok=True)

            # Analyze project context
            project_context = await self.analyze_project_context(current_dir)
            quality_score, quality_data = await self.perform_quality_assessment()

            self.logger.info(
                "Session initialized",
                project=self.current_project,
                quality_score=quality_score,
                working_directory=str(current_dir),
            )

            return {
                "success": True,
                "project": self.current_project,
                "working_directory": str(current_dir),
                "quality_score": quality_score,
                "quality_data": quality_data,
                "project_context": project_context,
                "claude_directory": str(claude_dir),
            }

        except Exception as e:
            self.logger.exception("Session initialization failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def checkpoint_session(self) -> dict[str, Any]:
        """Perform a comprehensive session checkpoint."""
        try:
            current_dir = Path.cwd()
            self.current_project = current_dir.name

            # Quality assessment
            quality_score, quality_data = await self.perform_quality_assessment()

            # Git checkpoint
            git_output = await self.perform_git_checkpoint(current_dir, quality_score)

            # Format results
            quality_output = self.format_quality_results(quality_score, quality_data)

            self.logger.info(
                "Session checkpoint completed",
                project=self.current_project,
                quality_score=quality_score,
            )

            return {
                "success": True,
                "quality_score": quality_score,
                "quality_output": quality_output,
                "git_output": git_output,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.exception("Session checkpoint failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def end_session(self) -> dict[str, Any]:
        """End the current session with cleanup and summary."""
        try:
            current_dir = Path.cwd()
            self.current_project = current_dir.name

            # Final quality assessment
            quality_score, quality_data = await self.perform_quality_assessment()

            # Create session summary
            summary = {
                "project": self.current_project,
                "final_quality_score": quality_score,
                "session_end_time": datetime.now().isoformat(),
                "working_directory": str(current_dir),
                "recommendations": quality_data.get("recommendations", []),
            }

            self.logger.info(
                "Session ended",
                project=self.current_project,
                final_quality_score=quality_score,
            )

            return {"success": True, "summary": summary}

        except Exception as e:
            self.logger.exception("Session end failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def get_session_status(
        self,
        working_directory: str | None = None,
    ) -> dict[str, Any]:
        """Get current session status and health information."""
        try:
            current_dir = Path(working_directory) if working_directory else Path.cwd()

            self.current_project = current_dir.name

            # Get comprehensive status
            project_context = await self.analyze_project_context(current_dir)
            quality_score, quality_data = await self.perform_quality_assessment()

            # Check system health
            uv_available = shutil.which("uv") is not None
            git_available = is_git_repository(current_dir)
            claude_dir = Path.home() / ".claude"
            claude_dir_exists = claude_dir.exists()

            return {
                "success": True,
                "project": self.current_project,
                "working_directory": str(current_dir),
                "quality_score": quality_score,
                "quality_breakdown": quality_data["breakdown"],
                "recommendations": quality_data["recommendations"],
                "project_context": project_context,
                "system_health": {
                    "uv_available": uv_available,
                    "git_repository": git_available,
                    "claude_directory": claude_dir_exists,
                },
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.exception("Failed to get session status", error=str(e))
            return {"success": False, "error": str(e)}
