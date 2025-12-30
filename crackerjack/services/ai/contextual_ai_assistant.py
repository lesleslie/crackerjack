import json
import subprocess
import time
import tomllib
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.models.protocols import FileSystemInterface


@dataclass
class AIRecommendation:
    category: str
    priority: str
    title: str
    description: str
    action_command: str | None = None
    reasoning: str = ""
    confidence: float = 0.0


@dataclass
class ProjectContext:
    has_tests: bool = False
    test_coverage: float = 0.0
    lint_errors_count: int = 0
    security_issues: list[str] = field(default_factory=list)
    outdated_dependencies: list[str] = field(default_factory=list)
    last_commit_days: int = 0
    project_size: str = "small"
    main_languages: list[str] = field(default_factory=list)
    has_ci_cd: bool = False
    has_documentation: bool = False
    project_type: str = "library"


class ContextualAIAssistant:
    def __init__(
        self,
        filesystem: FileSystemInterface,
    ) -> None:
        self.filesystem = filesystem
        self.console = console
        self.project_root = Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self.cache_file = self.project_root / ".crackerjack" / "ai_context.json"

    def get_contextual_recommendations(
        self,
        max_recommendations: int = 5,
    ) -> list[AIRecommendation]:
        context = self._analyze_project_context()
        recommendations = self._generate_recommendations(context)

        recommendations.sort(
            key=lambda r: (
                {"high": 3, "medium": 2, "low": 1}[r.priority],
                r.confidence,
            ),
            reverse=True,
        )

        return recommendations[:max_recommendations]

    def _analyze_project_context(self) -> ProjectContext:
        context = ProjectContext()

        context.has_tests = self._has_test_directory()
        context.test_coverage = self._get_current_coverage()
        context.lint_errors_count = self._count_current_lint_errors()
        context.project_size = self._determine_project_size()
        context.main_languages = self._detect_main_languages()
        context.has_ci_cd = self._has_ci_cd_config()
        context.has_documentation = self._has_documentation()
        context.project_type = self._determine_project_type()
        context.last_commit_days = self._days_since_last_commit()

        context.security_issues = self._detect_security_issues()
        context.outdated_dependencies = self._get_outdated_dependencies()

        return context

    def _generate_recommendations(
        self,
        context: ProjectContext,
    ) -> list[AIRecommendation]:
        recommendations: list[AIRecommendation] = []

        recommendations.extend(self._get_testing_recommendations(context))
        recommendations.extend(self._get_code_quality_recommendations(context))
        recommendations.extend(self._get_security_recommendations(context))
        recommendations.extend(self._get_maintenance_recommendations(context))
        recommendations.extend(self._get_workflow_recommendations(context))
        recommendations.extend(self._get_documentation_recommendations(context))

        return recommendations

    def _get_testing_recommendations(
        self,
        context: ProjectContext,
    ) -> list[AIRecommendation]:
        recommendations = []

        if not context.has_tests:
            recommendations.append(
                AIRecommendation(
                    category="testing",
                    priority="high",
                    title="Add Test Suite",
                    description="No test directory found. Adding tests improves code reliability and enables CI / CD.",
                    action_command="python -m crackerjack -t",
                    reasoning="Projects without tests have 40 % more bugs in production",
                    confidence=0.9,
                ),
            )
        elif context.test_coverage < 75:
            milestones = [15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]
            next_milestone = next(
                (m for m in milestones if m > context.test_coverage), 100
            )

            recommendations.append(
                AIRecommendation(
                    category="testing",
                    priority="medium",
                    title="Progress Toward 100 % Coverage",
                    description=f"Current coverage: {context.test_coverage:.1f}%. Next milestone: {next_milestone}% on the journey to 100%.",
                    action_command="python -m crackerjack -t",
                    reasoning="Coverage ratchet system prevents regression and targets 100 % coverage incrementally",
                    confidence=0.85,
                ),
            )

        return recommendations

    def _get_code_quality_recommendations(
        self,
        context: ProjectContext,
    ) -> list[AIRecommendation]:
        recommendations = []

        if context.lint_errors_count > 20:
            recommendations.append(
                AIRecommendation(
                    category="code_quality",
                    priority="high",
                    title="Fix Lint Errors",
                    description=f"Found {context.lint_errors_count} lint errors that should be addressed.",
                    action_command="python -m crackerjack --ai-fix",
                    reasoning="High lint error count indicates technical debt and potential bugs",
                    confidence=0.95,
                ),
            )
        elif context.lint_errors_count > 5:
            recommendations.append(
                AIRecommendation(
                    category="code_quality",
                    priority="medium",
                    title="Clean Up Code Style",
                    description=f"Found {context.lint_errors_count} minor lint issues to resolve.",
                    action_command="python -m crackerjack",
                    reasoning="Clean code is easier to maintain and has fewer bugs",
                    confidence=0.8,
                ),
            )

        return recommendations

    def _get_security_recommendations(
        self,
        context: ProjectContext,
    ) -> list[AIRecommendation]:
        recommendations = []

        if context.security_issues:
            recommendations.append(
                AIRecommendation(
                    category="security",
                    priority="high",
                    title="Address Security Vulnerabilities",
                    description=f"Found {len(context.security_issues)} security issues in dependencies.",
                    action_command="python -m crackerjack --check-dependencies",
                    reasoning="Security vulnerabilities can expose your application to attacks",
                    confidence=0.95,
                ),
            )

        return recommendations

    def _get_maintenance_recommendations(
        self,
        context: ProjectContext,
    ) -> list[AIRecommendation]:
        recommendations = []

        if len(context.outdated_dependencies) > 10:
            recommendations.append(
                AIRecommendation(
                    category="maintenance",
                    priority="medium",
                    title="Update Dependencies",
                    description=f"Found {len(context.outdated_dependencies)} outdated dependencies.",
                    action_command="python -m crackerjack --check-dependencies",
                    reasoning="Outdated dependencies may have security vulnerabilities or performance issues",
                    confidence=0.75,
                ),
            )

        return recommendations

    def _get_workflow_recommendations(
        self,
        context: ProjectContext,
    ) -> list[AIRecommendation]:
        recommendations = []

        if not context.has_ci_cd and context.project_size != "small":
            recommendations.append(
                AIRecommendation(
                    category="workflow",
                    priority="medium",
                    title="Set Up CI / CD Pipeline",
                    description="No CI / CD configuration found. Automated testing and deployment improve reliability.",
                    reasoning="CI / CD prevents 60 % of deployment issues and improves team productivity",
                    confidence=0.8,
                ),
            )

        return recommendations

    def _get_documentation_recommendations(
        self,
        context: ProjectContext,
    ) -> list[AIRecommendation]:
        recommendations = []

        if not context.has_documentation and context.project_type in ("library", "api"):
            recommendations.append(
                AIRecommendation(
                    category="documentation",
                    priority="medium",
                    title="Add Documentation",
                    description="No documentation found. Good documentation improves adoption and maintenance.",
                    reasoning="Well-documented projects get 3x more contributors and have better longevity",
                    confidence=0.7,
                ),
            )

        return recommendations

    def _has_test_directory(self) -> bool:
        test_dirs = ["tests", "test", "testing"]
        return any((self.project_root / dirname).exists() for dirname in test_dirs)

    def _get_current_coverage(self) -> float:
        from contextlib import suppress

        with suppress(Exception):
            coverage_file = self.project_root / ".coverage"
            if coverage_file.exists():
                result = subprocess.run(
                    ["uv", "run", "coverage", "report", "--format=json"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=self.project_root,
                )

                if result.returncode == 0 and result.stdout:
                    data = json.loads(result.stdout)
                    return float(data.get("totals", {}).get("percent_covered", 0))
        return 0.0

    def _count_current_lint_errors(self) -> int:
        from contextlib import suppress

        with suppress(Exception):
            result = subprocess.run(
                ["uv", "run", "ruff", "check", ".", "--output-format=json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root,
            )

            if result.returncode != 0 and result.stdout:
                with suppress(json.JSONDecodeError):
                    lint_data = json.loads(result.stdout)
                    return len(lint_data) if isinstance(lint_data, list) else 0
                return len(result.stdout.splitlines())
        return 0

    def _determine_project_size(self) -> str:
        try:
            python_files = list[t.Any](self.project_root.rglob("*.py"))
            if len(python_files) < 10:
                return "small"
            if len(python_files) < 50:
                return "medium"
            return "large"
        except Exception:
            return "small"

    def _detect_main_languages(self) -> list[str]:
        languages = []

        if (self.project_root / "pyproject.toml").exists():
            languages.append("python")

        if (self.project_root / "package.json").exists():
            languages.append("javascript")
        if any(self.project_root.glob("*.ts")):
            languages.append("typescript")

        if (self.project_root / "Cargo.toml").exists():
            languages.append("rust")

        if (self.project_root / "go.mod").exists():
            languages.append("go")

        return languages or ["python"]

    def _has_ci_cd_config(self) -> bool:
        ci_files = [
            ".github / workflows",
            ".gitlab-ci.yml",
            "azure-pipelines.yml",
            "Jenkinsfile",
            ".travis.yml",
        ]
        return any((self.project_root / path).exists() for path in ci_files)

    def _has_documentation(self) -> bool:
        doc_indicators = [
            "README.md",
            "README.rst",
            "docs",
            "documentation",
            "doc",
        ]
        return any((self.project_root / path).exists() for path in doc_indicators)

    def _determine_project_type(self) -> str:
        try:
            if self.pyproject_path.exists():
                with self.pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                project_data = data.get("project", {})
                scripts = project_data.get("scripts", {})

                if scripts or "console_scripts" in project_data.get("entry-points", {}):
                    return "cli"

                dependencies = project_data.get("dependencies", [])
                web_frameworks = ["fastapi", "flask", "django", "starlette"]
                if any(fw in str(dependencies).lower() for fw in web_frameworks):
                    return "api"

                if (self.project_root / "__main__.py").exists():
                    return "application"

            return "library"
        except Exception:
            return "library"

    def _days_since_last_commit(self) -> int:
        from contextlib import suppress

        with suppress(Exception):
            result = subprocess.run(
                ["git", "log", "- 1", "--format=% ct"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.project_root,
            )

            if result.returncode == 0 and result.stdout.strip():
                last_commit_timestamp = int(result.stdout.strip())
                current_timestamp = time.time()
                return int((current_timestamp - last_commit_timestamp) / 86400)
        return 0

    def _detect_security_issues(self) -> list[str]:
        issues = []
        from contextlib import suppress

        with suppress(Exception):
            result = subprocess.run(
                ["uv", "run", "bandit", "- r", ".", "- f", "json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root,
            )

            if result.returncode != 0 and result.stdout:
                with suppress(json.JSONDecodeError):
                    bandit_data = json.loads(result.stdout)
                    results = bandit_data.get("results", [])
                    for issue in results[:5]:
                        test_id = issue.get("test_id", "unknown")
                        issues.append(f"Security issue: {test_id}")

        return issues

    def _get_outdated_dependencies(self) -> list[str]:
        outdated = []

        from contextlib import suppress

        with suppress(Exception):
            if self.pyproject_path.exists():
                with self.pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                dependencies = data.get("project", {}).get("dependencies", [])

                old_patterns = [" == 1.", " == 0.", " >= 1.", "~ = 1."]
                for dep in dependencies:
                    if any(pattern in dep for pattern in old_patterns):
                        pkg_name = (
                            dep.split(" == ")[0]
                            .split(" >= ")[0]
                            .split("~ = ")[0]
                            .strip()
                        )
                        outdated.append(pkg_name)

        return outdated

    def display_recommendations(self, recommendations: list[AIRecommendation]) -> None:
        if not recommendations:
            self.console.print(
                "[green]✨ Great job ! No immediate recommendations.[/ green]",
            )
            return

        self.console.print("\n[bold cyan]🤖 AI Assistant Recommendations[/ bold cyan]")
        self.console.print("[dim]Based on your current project context[/ dim]\n")

        for i, rec in enumerate(recommendations, 1):
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(
                rec.priority,
                "white",
            )

            category_emoji = {
                "testing": "🧪",
                "code_quality": "🔧",
                "security": "🔒",
                "maintenance": "📦",
                "workflow": "⚙️",
                "documentation": "📚",
                "architecture": "🏗️",
                "performance": "⚡",
            }.get(rec.category, "💡")

            self.console.print(
                f"[bold]{i}. {category_emoji} {rec.title}[/ bold] [{priority_color}]({rec.priority})[/{priority_color}]",
            )
            self.console.print(f" {rec.description}")

            if rec.action_command:
                self.console.print(
                    f" [dim]Run: [/ dim] [cyan]{rec.action_command}[/ cyan]",
                )

            if rec.reasoning:
                self.console.print(f" [dim italic]💭 {rec.reasoning}[/ dim italic]")

            confidence_bar = "█" * int(rec.confidence * 10) + "▒" * (
                10 - int(rec.confidence * 10)
            )
            self.console.print(
                f" [dim]Confidence: [{confidence_bar}] {rec.confidence:.1%}[/ dim]",
            )

            if i < len(recommendations):
                self.console.print()

    def get_quick_help(self, query: str) -> str:
        """Get quick help for common queries using keyword matching."""
        query_lower = query.lower()

        # Define help responses with keywords
        help_mapping = self._get_help_keyword_mapping()

        # Find the first matching help response
        for keywords, response in help_mapping:
            if self._query_contains_keywords(query_lower, keywords):
                return response

        return "For full help, run: python -m crackerjack --help\nFor AI assistance: python -m crackerjack --ai-fix"

    def _get_help_keyword_mapping(self) -> list[tuple[list[str], str]]:
        """Get mapping of keywords to help responses."""
        return [
            (
                ["coverage"],
                "Check test coverage with: python -m crackerjack -t\nView HTML report: uv run coverage html",
            ),
            (
                ["security", "vulnerabilit"],
                "Check security with: python -m crackerjack --check-dependencies\nRun security audit: uv run bandit -r .",
            ),
            (
                ["lint", "format"],
                "Fix code style with: python -m crackerjack\nFor AI-powered fixes: python -m crackerjack --ai-fix",
            ),
            (
                ["test"],
                "Run tests with: python -m crackerjack -t\nFor AI-powered test fixes: python -m crackerjack --ai-fix -t",
            ),
            (
                ["publish", "release"],
                "Publish to PyPI: python -m crackerjack -p patch\nBump version only: python -m crackerjack -b patch",
            ),
            (
                ["clean"],
                "Clean code: python -m crackerjack -x\nNote: Resolve TODOs first before cleaning",
            ),
            (
                ["dashboard", "monitor"],
                # Phase 1: WebSocket server command removed from help text (WebSocket stack deleted)
                "Start monitoring dashboard: python -m crackerjack --dashboard",
            ),
        ]

    def _query_contains_keywords(self, query: str, keywords: list[str]) -> bool:
        """Check if query contains any of the specified keywords."""
        return any(keyword in query for keyword in keywords)
