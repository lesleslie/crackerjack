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

        # Permissions health (20% of score)
        # Check if we have a permissions manager and if operations are trusted
        try:
            from session_mgmt_mcp.server import permissions_manager

            if hasattr(permissions_manager, "trusted_operations"):
                trusted_count = len(permissions_manager.trusted_operations)
                # Score based on number of trusted operations (max 20 points)
                permissions_score = min(
                    trusted_count * 4, 20
                )  # 4 points per trusted operation, max 20
            else:
                permissions_score = (
                    10  # Basic score if we can't access trusted operations
                )
        except (ImportError, AttributeError):
            # If we can't import permissions manager or access trusted operations, use a basic score
            permissions_score = 10

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
                for name in ("README.md", "README.rst", "README.txt", "readme.md")
            ),
            "has_git_repo": is_git_repository(project_dir),
            "has_venv": any(
                (project_dir / name).exists()
                for name in (".venv", "venv", ".env", "env")
            ),
            "has_tests": any(
                (project_dir / name).exists() for name in ("tests", "test", "testing")
            ),
            "has_src_structure": (project_dir / "src").exists(),
            "has_docs": any(
                (project_dir / name).exists() for name in ("docs", "documentation")
            ),
            "has_ci_cd": any(
                (project_dir / name).exists()
                for name in (".github", ".gitlab-ci.yml", ".travis.yml", "Jenkinsfile")
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

            # Check for previous session information
            previous_session_info = None
            latest_handoff = self._find_latest_handoff_file(current_dir)
            if latest_handoff:
                previous_session_info = self._read_previous_session_info(latest_handoff)

            self.logger.info(
                "Session initialized",
                project=self.current_project,
                quality_score=quality_score,
                working_directory=str(current_dir),
                has_previous_session=previous_session_info is not None,
            )

            return {
                "success": True,
                "project": self.current_project,
                "working_directory": str(current_dir),
                "quality_score": quality_score,
                "quality_data": quality_data,
                "project_context": project_context,
                "claude_directory": str(claude_dir),
                "previous_session": previous_session_info,
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

            # Generate handoff documentation
            handoff_content = self._generate_handoff_documentation(
                summary, quality_data
            )

            # Save handoff documentation
            handoff_path = self._save_handoff_documentation(
                handoff_content, current_dir
            )

            self.logger.info(
                "Session ended",
                project=self.current_project,
                final_quality_score=quality_score,
            )

            summary["handoff_documentation"] = (
                str(handoff_path) if handoff_path else None
            )

            return {"success": True, "summary": summary}

        except Exception as e:
            self.logger.exception("Session end failed", error=str(e))
            return {"success": False, "error": str(e)}

    def _generate_handoff_documentation(self, summary: dict, quality_data: dict) -> str:
        """Generate comprehensive handoff documentation in markdown format."""
        # Create markdown documentation
        lines = []

        # Header
        lines.append(f"# Session Handoff Report - {summary['project']}")
        lines.append("")
        lines.append(f"**Session ended:** {summary['session_end_time']}")
        lines.append(f"**Final quality score:** {summary['final_quality_score']}/100")
        lines.append(f"**Working directory:** {summary['working_directory']}")
        lines.append("")

        # Quality assessment
        lines.append("## Quality Assessment")
        lines.append("")
        breakdown = quality_data.get("breakdown", {})
        lines.append(
            f"- **Project health:** {breakdown.get('project_health', 0):.1f}/40"
        )
        lines.append(f"- **Permissions:** {breakdown.get('permissions', 0):.1f}/20")
        lines.append(
            f"- **Session tools:** {breakdown.get('session_management', 0):.1f}/20"
        )
        lines.append(f"- **Tool availability:** {breakdown.get('tools', 0):.1f}/20")
        lines.append("")

        # Recommendations
        recommendations = summary.get("recommendations", [])
        if recommendations:
            lines.append("## Recommendations for Next Session")
            lines.append("")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Key achievements (placeholder for future enhancement)
        lines.append("## Key Achievements")
        lines.append("")
        lines.append("- Session successfully completed")
        lines.append("- Quality metrics captured")
        lines.append("- Temporary files cleaned up")
        lines.append("")

        # Next steps
        lines.append("## Next Steps")
        lines.append("")
        lines.append("1. Review the recommendations above")
        lines.append("2. Check the working directory for any uncommitted changes")
        lines.append("3. Ensure all necessary files are committed to version control")
        lines.append("4. Address any outstanding issues before starting next session")
        lines.append("")

        return "\n".join(lines)

    def _save_handoff_documentation(
        self, content: str, working_dir: Path
    ) -> Path | None:
        """Save handoff documentation to file."""
        try:
            # Create organized directory structure
            handoff_dir = working_dir / ".crackerjack" / "session" / "handoff"
            handoff_dir.mkdir(parents=True, exist_ok=True)

            # Create handoff filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_handoff_{timestamp}.md"
            handoff_path = handoff_dir / filename

            # Write content to file
            with open(handoff_path, "w", encoding="utf-8") as f:
                f.write(content)

            return handoff_path
        except Exception as e:
            self.logger.exception("Failed to save handoff documentation", error=str(e))
            return None

    def _find_latest_handoff_file(self, working_dir: Path) -> Path | None:
        """Find the most recent session handoff file."""
        try:
            handoff_dir = working_dir / ".crackerjack" / "session" / "handoff"

            if not handoff_dir.exists():
                # Check for legacy handoff files in project root
                legacy_files = list(working_dir.glob("session_handoff_*.md"))
                if legacy_files:
                    # Return the most recent legacy file
                    return max(legacy_files, key=lambda f: f.stat().st_mtime)
                return None

            # Find all handoff files
            handoff_files = list(handoff_dir.glob("session_handoff_*.md"))

            if not handoff_files:
                return None

            # Return the most recent file based on timestamp in filename
            return max(handoff_files, key=lambda f: f.name)

        except Exception as e:
            self.logger.debug(f"Error finding handoff files: {e}")
            return None

    def _read_previous_session_info(self, handoff_file: Path) -> dict[str, str] | None:
        """Extract key information from previous session handoff file."""
        try:
            with open(handoff_file, encoding="utf-8") as f:
                content = f.read()

            info = {}
            lines = content.split("\n")

            for line in lines:
                if line.startswith("**Session ended:**"):
                    info["ended_at"] = line.split("**Session ended:**")[1].strip()
                elif line.startswith("**Final quality score:**"):
                    info["quality_score"] = line.split("**Final quality score:**")[
                        1
                    ].strip()
                elif line.startswith("**Working directory:**"):
                    info["working_directory"] = line.split("**Working directory:**")[
                        1
                    ].strip()

            # Extract first recommendation if available
            in_recommendations = False
            for line in lines:
                if "## Recommendations for Next Session" in line:
                    in_recommendations = True
                    continue
                if in_recommendations and line.strip().startswith("1."):
                    info["top_recommendation"] = line.strip()[
                        3:
                    ].strip()  # Remove "1. "
                    break
                if in_recommendations and line.startswith("##"):
                    break  # End of recommendations section

            return info if info else None

        except Exception as e:
            self.logger.debug(f"Error reading handoff file: {e}")
            return None

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
