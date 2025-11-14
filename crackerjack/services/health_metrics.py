import json
import subprocess
import time
import tomllib
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from rich.console import Console

from crackerjack.models.protocols import FileSystemInterface


@dataclass
class ProjectHealth:
    lint_error_trend: list[int] = field(default_factory=list)
    test_coverage_trend: list[float] = field(default_factory=list)
    dependency_age: dict[str, int] = field(default_factory=dict[str, t.Any])
    config_completeness: float = 0.0
    last_updated: float = field(default_factory=time.time)

    def needs_init(self) -> bool:
        if self._is_trending_up(self.lint_error_trend):
            return True

        if self._is_trending_down(self.test_coverage_trend):
            return True

        if any(age > 180 for age in self.dependency_age.values()):
            return True

        return self.config_completeness < 0.8

    def _is_trending_up(
        self, values: list[int] | list[float], min_points: int = 3
    ) -> bool:
        if len(values) < min_points:
            return False

        recent = values[-min_points:]

        return all(a <= b for a, b in zip(recent, recent[1:]))

    def _is_trending_down(
        self, values: list[int] | list[float], min_points: int = 3
    ) -> bool:
        if len(values) < min_points:
            return False

        recent = values[-min_points:]

        return all(a >= b for a, b in zip(recent, recent[1:]))

    def get_health_score(self) -> float:
        scores: list[float] = []

        if self.lint_error_trend:
            recent_errors = sum(self.lint_error_trend[-5:]) / min(
                len(self.lint_error_trend),
                5,
            )
            lint_score = max(0, 1.0 - (recent_errors / 100))
            scores.append(lint_score)

        if self.test_coverage_trend:
            recent_coverage = sum(self.test_coverage_trend[-5:]) / min(
                len(self.test_coverage_trend),
                5,
            )
            coverage_score = recent_coverage / 100.0
            scores.append(coverage_score)

        if self.dependency_age:
            avg_age = sum(self.dependency_age.values()) / len(self.dependency_age)

            dependency_score = max(0, 1.0 - (avg_age / 365))
            scores.append(dependency_score)

        scores.append(self.config_completeness)

        return sum(scores) / len(scores) if scores else 0.0

    def get_recommendations(self) -> list[str]:
        recommendations: list[str] = []

        if self._is_trending_up(self.lint_error_trend):
            recommendations.append(
                "🔧 Lint errors are increasing-consider running formatting tools",
            )

        if self._is_trending_down(self.test_coverage_trend):
            recommendations.append("🧪 Test coverage is declining-add more tests")

        if any(age > 365 for age in self.dependency_age.values()):
            old_deps: list[str] = [
                pkg for pkg, age in self.dependency_age.items() if age > 365
            ]
            recommendations.append(
                f"📦 Very old dependencies detected: {', '.join(old_deps[:3])}",
            )

        if self.config_completeness < 0.5:
            recommendations.append(
                "⚙️ Project configuration is incomplete-run crackerjack init",
            )
        elif self.config_completeness < 0.8:
            recommendations.append("⚙️ Project configuration could be improved")

        if len(self.lint_error_trend) > 10:
            recent_avg = sum(self.lint_error_trend[-5:]) / 5
            older_avg = sum(self.lint_error_trend[-10:-5]) / 5
            if recent_avg > older_avg * 1.5:
                recommendations.append(
                    "📈 Quality is degrading rapidly - immediate attention needed",
                )

        return recommendations


class HealthMetricsService:
    def __init__(
        self,
        filesystem: FileSystemInterface,
        console: Console | None = None,
    ) -> None:
        self.filesystem = filesystem
        self.console = console or Console()
        self.project_root = Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self.health_cache = self.project_root / ".crackerjack" / "health_metrics.json"
        self.max_trend_points = 20

    def collect_current_metrics(self) -> ProjectHealth:
        health = self._load_health_history()

        lint_errors = self._count_lint_errors()
        if lint_errors is not None:
            health.lint_error_trend.append(lint_errors)
            health.lint_error_trend = health.lint_error_trend[-self.max_trend_points :]

        coverage = self._get_test_coverage()
        if coverage is not None:
            health.test_coverage_trend.append(coverage)
            health.test_coverage_trend = health.test_coverage_trend[
                -self.max_trend_points :
            ]

        health.dependency_age = self._calculate_dependency_ages()

        health.config_completeness = self._assess_config_completeness()

        health.last_updated = time.time()

        return health

    def _load_health_history(self) -> ProjectHealth:
        with suppress(Exception):
            if self.health_cache.exists():
                with self.health_cache.open() as f:
                    data = json.load(f)
                return ProjectHealth(**data)

        return ProjectHealth()

    def _save_health_metrics(self, health: ProjectHealth) -> None:
        try:
            self.health_cache.parent.mkdir(exist_ok=True)
            with self.health_cache.open("w") as f:
                data = {
                    "lint_error_trend": health.lint_error_trend,
                    "test_coverage_trend": health.test_coverage_trend,
                    "dependency_age": health.dependency_age,
                    "config_completeness": health.config_completeness,
                    "last_updated": health.last_updated,
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            self.console.print(
                f"[yellow]Warning: Failed to save health metrics: {e}[/ yellow]",
            )

    def _count_lint_errors(self) -> int | None:
        with suppress(Exception):
            result = subprocess.run(
                ["uv", "run", "ruff", "check", ".", "- - output-format=json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root,
            )

            if result.returncode == 0:
                return 0

            if result.stdout:
                try:
                    lint_data = json.loads(result.stdout)
                    return len(lint_data) if isinstance(lint_data, list) else 0
                except json.JSONDecodeError:
                    return len(result.stdout.splitlines())

        return None

    def _get_test_coverage(self) -> float | None:
        with suppress(Exception):
            existing_coverage = self._check_existing_coverage_files()
            if existing_coverage is not None:
                return existing_coverage

            generated_coverage = self._generate_coverage_report()
            if generated_coverage is not None:
                return generated_coverage

            return self._get_coverage_from_command()

        return None

    def _check_existing_coverage_files(self) -> float | None:
        coverage_files = [
            self.project_root / ".coverage",
            self.project_root / "htmlcov" / "index.html",
            self.project_root / "coverage.xml",
        ]

        for coverage_file in coverage_files:
            if coverage_file.exists():
                return self._get_coverage_from_command()

        return None

    def _generate_coverage_report(self) -> float | None:
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "- m",
                "pytest",
                "--cov =.",
                "- - cov-report=json",
                "--tb=no",
                "- q",
                "--maxfail=1",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=self.project_root,
        )

        coverage_json = self.project_root / "coverage.json"
        if coverage_json.exists():
            with coverage_json.open() as f:
                data = json.load(f)
                return float(data.get("totals", {}).get("percent_covered", 0))

        return None

    def _get_coverage_from_command(self) -> float | None:
        result = subprocess.run(
            ["uv", "run", "coverage", "report", "--format=json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=self.project_root,
        )

        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            return float(data.get("totals", {}).get("percent_covered", 0))

        return None

    def _calculate_dependency_ages(self) -> dict[str, int]:
        dependency_ages: dict[str, int] = {}

        with suppress(Exception):
            if not self.pyproject_path.exists():
                return dependency_ages

            project_data = self._load_project_data()
            dependencies = self._extract_all_dependencies(project_data)
            dependency_ages = self._get_ages_for_dependencies(dependencies)

        return dependency_ages

    def _load_project_data(self) -> dict[str, t.Any]:
        with self.pyproject_path.open("rb") as f:
            return tomllib.load(f)

    def _extract_all_dependencies(self, project_data: dict[str, t.Any]) -> list[str]:
        dependencies: list[str] = []

        if "dependencies" in project_data.get("project", {}):
            dependencies.extend(project_data["project"]["dependencies"])

        if "optional-dependencies" in project_data.get("project", {}):
            for group_deps in project_data["project"]["optional-dependencies"].values():
                dependencies.extend(group_deps)

        return dependencies

    def _get_ages_for_dependencies(self, dependencies: list[str]) -> dict[str, int]:
        dependency_ages: dict[str, int] = {}

        for dep_spec in dependencies:
            package_name = self._extract_package_name(dep_spec)
            if package_name:
                age = self._get_package_age(package_name)
                if age is not None:
                    dependency_ages[package_name] = age

        return dependency_ages

    def _extract_package_name(self, dep_spec: str) -> str | None:
        if not dep_spec or dep_spec.startswith("-"):
            return None

        for operator in ("> =", "< =", "= =", "~=", "! =", ">", "<"):
            if operator in dep_spec:
                return dep_spec.split(operator)[0].strip()

        return dep_spec.strip()

    def _get_package_age(self, package_name: str) -> int | None:
        try:
            package_data = self._fetch_package_data(package_name)
            if not package_data:
                return None

            upload_time = self._extract_upload_time(package_data)
            if not upload_time:
                return None

            return self._calculate_days_since_upload(upload_time)
        except Exception:
            return None

    def _fetch_package_data(self, package_name: str) -> dict[str, t.Any] | None:
        try:
            from urllib.parse import urlparse

            url = f"https: //pypi.org/pypi/{package_name}/json"

            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.netloc != "pypi.org":
                msg = f"Invalid URL: only https: //pypi.org URLs are allowed, got {url}"
                raise ValueError(msg)

            if not parsed.path.startswith("/pypi/") or not parsed.path.endswith(
                "/json"
            ):
                msg = f"Invalid PyPI API path: {parsed.path}"
                raise ValueError(msg)

            response = requests.get(url, timeout=10, verify=True)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def _extract_upload_time(self, package_data: dict[str, t.Any]) -> str | None:
        info = package_data.get("info", {})
        releases = package_data.get("releases", {})

        latest_version = info.get("version", "")
        if not latest_version or latest_version not in releases:
            return None

        release_info = releases[latest_version]
        if not release_info:
            return None

        return release_info[0].get("upload_time", "")

    def _calculate_days_since_upload(self, upload_time: str) -> int | None:
        try:
            upload_date = datetime.fromisoformat(upload_time)
            return (datetime.now(upload_date.tzinfo) - upload_date).days
        except Exception:
            return None

    def _assess_config_completeness(self) -> float:
        score = 0.0
        total_checks = 0

        pyproject_score, pyproject_checks = self._assess_pyproject_config()
        score += pyproject_score
        total_checks += pyproject_checks

        precommit_score, precommit_checks = self._assess_precommit_config()
        score += precommit_score
        total_checks += precommit_checks

        ci_score, ci_checks = self._assess_ci_config()
        score += ci_score
        total_checks += ci_checks

        doc_score, doc_checks = self._assess_documentation_config()
        score += doc_score
        total_checks += doc_checks

        return min(1.0, score) if total_checks > 0 else 0.0

    def _assess_pyproject_config(self) -> tuple[float, int]:
        score = 0.0
        total_checks = 1

        if not self.pyproject_path.exists():
            return score, total_checks

        score += 0.2

        with suppress(Exception):
            with self.pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            project_score, project_checks = self._assess_project_metadata(data)
            score += project_score
            total_checks += project_checks

            tool_score, tool_checks = self._assess_tool_configs(data)
            score += tool_score
            total_checks += tool_checks

        return score, total_checks

    def _assess_project_metadata(self, data: dict[str, t.Any]) -> tuple[float, int]:
        score = 0.0
        total_checks = 0

        if "project" not in data:
            return score, total_checks

        project_data = data["project"]
        essential_fields = ["name", "version", "description", "dependencies"]

        for field_name in essential_fields:
            total_checks += 1
            if field_name in project_data:
                score += 0.1

        return score, total_checks

    def _assess_tool_configs(self, data: dict[str, t.Any]) -> tuple[float, int]:
        score = 0.0
        tool_configs = ["tool.ruff", "tool.pytest", "tool.coverage"]

        for tool in tool_configs:
            keys = tool.split(".")
            current = data
            with suppress(KeyError):
                for key in keys:
                    current = current[key]
                score += 0.05

        return score, len(tool_configs)

    def _assess_precommit_config(self) -> tuple[float, int]:
        precommit_files = [
            self.project_root / ".pre-commit-config.yaml",
            self.project_root / ".pre - commit-config.yml",
        ]
        score = 0.1 if any(f.exists() for f in precommit_files) else 0.0
        return score, 1

    def _assess_ci_config(self) -> tuple[float, int]:
        ci_files = [
            self.project_root / ".github" / "workflows",
            self.project_root / ".gitlab-ci.yml",
            self.project_root / "azure-pipelines.yml",
        ]
        score = 0.1 if any(f.exists() for f in ci_files) else 0.0
        return score, 1

    def _assess_documentation_config(self) -> tuple[float, int]:
        doc_files = [
            self.project_root / "README.md",
            self.project_root / "README.rst",
            self.project_root / "docs",
        ]
        score = 0.1 if any(f.exists() for f in doc_files) else 0.0
        return score, 1

    def analyze_project_health(self, save_metrics: bool = True) -> ProjectHealth:
        health = self.collect_current_metrics()

        if save_metrics:
            self._save_health_metrics(health)

        return health

    def report_health_status(self, health: ProjectHealth) -> None:
        health_score = health.get_health_score()

        self._print_health_summary(health_score)
        self._print_health_metrics(health)
        self._print_health_recommendations(health)

    def _print_health_summary(self, health_score: float) -> None:
        status_icon, status_text, status_color = self._get_health_status_display(
            health_score,
        )

        self.console.print("\n[bold]📊 Project Health Report[/ bold]")
        self.console.print(
            f"{status_icon} Overall Health: [{status_color}]{status_text} ({health_score: .1 %})[/{status_color}]",
        )

    def _get_health_status_display(self, health_score: float) -> tuple[str, str, str]:
        if health_score >= 0.8:
            return "🟢", "Excellent", "green"
        if health_score >= 0.6:
            return "🟡", "Good", "yellow"
        if health_score >= 0.4:
            return "🟠", "Fair", "orange"
        return "🔴", "Poor", "red"

    def _print_health_metrics(self, health: ProjectHealth) -> None:
        if health.lint_error_trend:
            recent_errors = health.lint_error_trend[-1]
            self.console.print(f"🔧 Lint Errors: {recent_errors}")

        if health.test_coverage_trend:
            recent_coverage = health.test_coverage_trend[-1]
            self.console.print(f"🧪 Test Coverage: {recent_coverage: .1f}%")

        if health.dependency_age:
            avg_age = sum(health.dependency_age.values()) / len(health.dependency_age)
            self.console.print(f"📦 Avg Dependency Age: {avg_age: .0f} days")

        self.console.print(f"⚙️ Config Completeness: {health.config_completeness: .1 %}")

    def _print_health_recommendations(self, health: ProjectHealth) -> None:
        recommendations = health.get_recommendations()
        if recommendations:
            self.console.print("\n[bold]💡 Recommendations: [/ bold]")
            for rec in recommendations:
                self.console.print(f" {rec}")

        if health.needs_init():
            self.console.print(
                "\n[bold yellow]⚠️ Consider running `crackerjack --init` to improve project health[/ bold yellow]",
            )

    def get_health_trend_summary(self, days: int = 30) -> dict[str, Any]:
        health = self._load_health_history()

        return {
            "health_score": health.get_health_score(),
            "needs_attention": health.needs_init(),
            "recommendations": health.get_recommendations(),
            "metrics": {
                "lint_errors": self._get_lint_errors_metrics(health),
                "test_coverage": self._get_test_coverage_metrics(health),
                "dependency_age": self._get_dependency_age_metrics(health),
                "config_completeness": health.config_completeness,
            },
        }

    def _get_lint_errors_metrics(
        self, health: ProjectHealth
    ) -> dict[str, str | int | None]:
        return {
            "current": health.lint_error_trend[-1] if health.lint_error_trend else None,
            "trend": self._get_trend_direction(health, health.lint_error_trend),
        }

    def _get_test_coverage_metrics(
        self, health: ProjectHealth
    ) -> dict[str, str | float | None]:
        return {
            "current": health.test_coverage_trend[-1]
            if health.test_coverage_trend
            else None,
            "trend": self._get_coverage_trend_direction(
                health, health.test_coverage_trend
            ),
        }

    def _get_dependency_age_metrics(
        self, health: ProjectHealth
    ) -> dict[str, float | int | None]:
        if not health.dependency_age:
            return {"average": None, "outdated_count": 0}

        return {
            "average": sum(health.dependency_age.values()) / len(health.dependency_age),
            "outdated_count": sum(
                1 for age in health.dependency_age.values() if age > 180
            ),
        }

    def _get_trend_direction(self, health: ProjectHealth, trend_data: list[int]) -> str:
        if health._is_trending_up([float(x) for x in trend_data]):
            return "up"
        elif health._is_trending_down([float(x) for x in trend_data]):
            return "down"
        return "stable"

    def _get_coverage_trend_direction(
        self, health: ProjectHealth, coverage_trend: list[float]
    ) -> str:
        if health._is_trending_up([int(x) for x in coverage_trend]):
            return "up"
        elif health._is_trending_down(coverage_trend):
            return "down"
        return "stable"
