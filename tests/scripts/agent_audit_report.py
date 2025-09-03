#!/usr/bin/env python3

import ast
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))

from crackerjack.agents.base import (
    AgentContext,
    Issue,
    IssueType,
    Priority,
    SubAgent,
    agent_registry,
)


@dataclass
class AgentAuditResult:
    agent_name: str
    class_name: str
    file_path: str

    has_can_handle: bool = False
    has_analyze_and_fix: bool = False
    has_get_supported_types: bool = False
    confidence_range_valid: bool = False

    estimated_complexity: int = 0
    method_count: int = 0
    lines_of_code: int = 0
    has_async_methods: bool = False

    supported_issue_types: set[IssueType] = field(default_factory=set)
    confidence_scores: dict[IssueType, float] = field(default_factory=dict)
    integration_issues: list[str] = field(default_factory=list)

    recommendations: list[str] = field(default_factory=list)
    critical_issues: list[str] = field(default_factory=list)
    performance_score: float = 0.0

    instantiation_success: bool = False
    mock_issue_handling: dict[str, Any] = field(default_factory=dict)


class AgentAuditor:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.agent_results: list[AgentAuditResult] = []

    async def audit_all_agents(self) -> list[AgentAuditResult]:
        self.console.print("🔍 [bold]Starting Comprehensive Agent Audit[/ bold]")

        agent_files = list(Path("crackerjack / agents").glob("*.py"))
        agent_files = [
            f for f in agent_files if f.name not in ["__init__.py", "base.py"]
        ]

        self.console.print(f"📁 Found {len(agent_files)} agent files to audit")

        for agent_file in agent_files:
            try:
                result = await self._audit_single_agent_file(agent_file)
                if result:
                    self.agent_results.append(result)
            except Exception as e:
                self.console.print(f"❌ Failed to audit {agent_file}: {e}")

        await self._audit_registered_agents()

        self._generate_audit_recommendations()

        return self.agent_results

    async def _audit_single_agent_file(
        self, agent_file: Path
    ) -> AgentAuditResult | None:
        self.console.print(f"🔍 Auditing {agent_file.name}")

        try:
            source = agent_file.read_text()
            tree = ast.parse(source)
        except Exception as e:
            self.console.print(f"❌ Failed to parse {agent_file}: {e}")
            return None

        agent_classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                is_agent = "Agent" in node.name or any(
                    isinstance(base, ast.Name) and base.id == "SubAgent"
                    for base in node.bases
                )
                if is_agent and not node.name.startswith("Test"):
                    agent_classes.append(node)

        if not agent_classes:
            return None

        agent_class = agent_classes[0]
        result = AgentAuditResult(
            agent_name=agent_class.name,
            class_name=agent_class.name,
            file_path=str(agent_file),
        )

        await self._analyze_agent_implementation(agent_class, source, result)

        return result

    async def _analyze_agent_implementation(
        self, class_node: ast.ClassDef, source: str, result: AgentAuditResult
    ):
        self._analyze_methods(class_node, result)

        self._analyze_complexity(class_node, source, result)

        self._calculate_quality_score(result)

        self._generate_quality_recommendations(result)

    def _analyze_methods(self, class_node: ast.ClassDef, result: AgentAuditResult):
        method_names = []
        async_methods = 0

        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                method_names.append(node.name)
                if any(
                    isinstance(dec, ast.Name) and dec.id == "asyncio"
                    for dec in node.decorator_list
                ):
                    async_methods += 1
            elif isinstance(node, ast.AsyncFunctionDef):
                method_names.append(node.name)
                async_methods += 1

        result.method_count = len(method_names)
        result.has_async_methods = async_methods > 0

        result.has_can_handle = "can_handle" in method_names
        result.has_analyze_and_fix = "analyze_and_fix" in method_names
        result.has_get_supported_types = "get_supported_types" in method_names

    def _analyze_complexity(
        self, class_node: ast.ClassDef, source: str, result: AgentAuditResult
    ):
        result.lines_of_code = len(
            [line for line in source.split("\n") if line.strip()]
        )
        result.estimated_complexity = self._estimate_complexity(class_node)

        if not result.has_can_handle:
            result.critical_issues.append("Missing required can_handle method")
        if not result.has_analyze_and_fix:
            result.critical_issues.append("Missing required analyze_and_fix method")

    def _calculate_quality_score(self, result: AgentAuditResult):
        score = 100
        if not result.has_can_handle:
            score -= 30
        if not result.has_analyze_and_fix:
            score -= 30
        if not result.has_get_supported_types:
            score -= 10
        if result.estimated_complexity > 15:
            score -= 20
        if result.lines_of_code > 500:
            score -= 10

        result.performance_score = max(0, score)

    def _generate_quality_recommendations(self, result: AgentAuditResult):
        if result.estimated_complexity > 15:
            result.recommendations.append("Consider breaking down complex methods")
        if result.lines_of_code > 300:
            result.recommendations.append(
                "Consider splitting large agent into smaller focused agents"
            )
        if not result.has_async_methods and result.method_count > 3:
            result.recommendations.append(
                "Consider using async methods for better performance"
            )

    def _estimate_complexity(self, class_node: ast.ClassDef) -> int:
        complexity = 1

        for node in ast.walk(class_node):
            if isinstance(node, ast.If | ast.While | ast.For | ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

        return complexity

    async def _audit_registered_agents(self):
        self.console.print("🧪 Testing registered agents...")

        context = AgentContext(project_path=Path.cwd())

        for agent_name, agent_class in agent_registry._agents.items():
            existing_result = None
            for result in self.agent_results:
                if result.agent_name == agent_name:
                    existing_result = result
                    break

            if not existing_result:
                existing_result = AgentAuditResult(
                    agent_name=agent_name, class_name=agent_name, file_path="Unknown"
                )
                self.agent_results.append(existing_result)

            try:
                agent = agent_class(context)
                existing_result.instantiation_success = True

                if hasattr(agent, "get_supported_types"):
                    existing_result.supported_issue_types = agent.get_supported_types()

                await self._test_agent_confidence(agent, existing_result)

            except Exception as e:
                existing_result.critical_issues.append(f"Instantiation failed: {e}")
                existing_result.instantiation_success = False

    async def _test_agent_confidence(self, agent: SubAgent, result: AgentAuditResult):
        test_issues = {
            IssueType.COMPLEXITY: Issue(
                id="test1",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Complex function",
                file_path="test.py",
            ),
            IssueType.FORMATTING: Issue(
                id="test2",
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="Format issue",
                file_path="test.py",
            ),
            IssueType.SECURITY: Issue(
                id="test3",
                type=IssueType.SECURITY,
                severity=Priority.CRITICAL,
                message="Security issue",
                file_path="test.py",
            ),
            IssueType.TEST_FAILURE: Issue(
                id="test4",
                type=IssueType.TEST_FAILURE,
                severity=Priority.HIGH,
                message="Test failed",
                file_path="test.py",
            ),
            IssueType.IMPORT_ERROR: Issue(
                id="test5",
                type=IssueType.IMPORT_ERROR,
                severity=Priority.MEDIUM,
                message="Import error",
                file_path="test.py",
            ),
        }

        valid_confidences = 0
        total_tests = 0

        for issue_type, issue in test_issues.items():
            try:
                confidence = await agent.can_handle(issue)
                result.confidence_scores[issue_type] = confidence

                if 0.0 <= confidence <= 1.0:
                    valid_confidences += 1
                else:
                    result.integration_issues.append(
                        f"Invalid confidence {confidence} for {issue_type}"
                    )

                total_tests += 1

            except Exception as e:
                result.integration_issues.append(
                    f"can_handle failed for {issue_type}: {e}"
                )

        result.confidence_range_valid = valid_confidences == total_tests

        if not result.confidence_range_valid:
            result.critical_issues.append("Invalid confidence scores returned")

    def _generate_audit_recommendations(self):
        self.console.print("📊 Generating audit recommendations...")

        total_agents = len(self.agent_results)
        working_agents = sum(1 for r in self.agent_results if r.instantiation_success)
        critical_issues_count = sum(len(r.critical_issues) for r in self.agent_results)

        self.console.print(
            f"📈 Agent Status: {working_agents}/{total_agents} agents functional"
        )
        self.console.print(f"🚨 Critical Issues: {critical_issues_count} total")

        problematic_agents = [
            r for r in self.agent_results if len(r.critical_issues) > 0
        ]
        if problematic_agents:
            self.console.print(
                f"⚠️ Problematic Agents: {[r.agent_name for r in problematic_agents]}"
            )

        avg_performance = sum(r.performance_score for r in self.agent_results) / len(
            self.agent_results
        )
        self.console.print(f"📊 Average Performance Score: {avg_performance: .1f}/ 100")

        top_performers = sorted(
            self.agent_results, key=lambda r: r.performance_score, reverse=True
        )[:3]
        self.console.print(
            f"🏆 Top Performers: {[(r.agent_name, f'{r.performance_score: .1f}') for r in top_performers]}"
        )

    def create_audit_table(self) -> Table:
        table = Table(
            title="AI Agent Audit Results",
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("Agent", style="cyan", width=20)
        table.add_column("Performance Score", justify="center", width=15)
        table.add_column("Methods", justify="center", width=10)
        table.add_column("LOC", justify="center", width=8)
        table.add_column("Complexity", justify="center", width=10)
        table.add_column("Status", justify="center", width=15)
        table.add_column("Critical Issues", width=25)

        for result in sorted(
            self.agent_results, key=lambda r: r.performance_score, reverse=True
        ):
            status_text = "✅ GOOD"
            status_color = "green"

            if len(result.critical_issues) > 0:
                status_text = "🚨 CRITICAL"
                status_color = "red"
            elif result.performance_score < 70:
                status_text = "⚠️ NEEDS WORK"
                status_color = "yellow"
            elif not result.instantiation_success:
                status_text = "❌ BROKEN"
                status_color = "red"

            critical_summary = "; ".join(result.critical_issues[:2])
            if len(result.critical_issues) > 2:
                critical_summary += f" (+{len(result.critical_issues) - 2} more)"

            table.add_row(
                result.agent_name,
                f"{result.performance_score: .1f}",
                str(result.method_count),
                str(result.lines_of_code),
                str(result.estimated_complexity),
                f"[{status_color}]{status_text}[/{status_color}]",
                critical_summary or "None",
            )

        return table

    def save_detailed_report(self):
        import json
        from datetime import datetime

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_agents": len(self.agent_results),
                "functional_agents": sum(
                    1 for r in self.agent_results if r.instantiation_success
                ),
                "critical_issues": sum(
                    len(r.critical_issues) for r in self.agent_results
                ),
                "average_performance": sum(
                    r.performance_score for r in self.agent_results
                )
                / len(self.agent_results)
                if self.agent_results
                else 0,
            },
            "agents": [
                {
                    "name": r.agent_name,
                    "class_name": r.class_name,
                    "file_path": r.file_path,
                    "performance_score": r.performance_score,
                    "method_count": r.method_count,
                    "lines_of_code": r.lines_of_code,
                    "estimated_complexity": r.estimated_complexity,
                    "has_required_methods": {
                        "can_handle": r.has_can_handle,
                        "analyze_and_fix": r.has_analyze_and_fix,
                        "get_supported_types": r.has_get_supported_types,
                    },
                    "supported_issue_types": [t.value for t in r.supported_issue_types],
                    "confidence_scores": {
                        k.value: v for k, v in r.confidence_scores.items()
                    },
                    "instantiation_success": r.instantiation_success,
                    "critical_issues": r.critical_issues,
                    "recommendations": r.recommendations,
                    "integration_issues": r.integration_issues,
                }
                for r in self.agent_results
            ],
        }

        report_file = Path(".crackerjack") / "agent_audit_report.json"
        report_file.parent.mkdir(exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        self.console.print(f"📄 Detailed audit report saved: {report_file}")


async def main():
    console = Console()
    auditor = AgentAuditor(console)

    results = await auditor.audit_all_agents()

    console.print("\n")
    console.print(auditor.create_audit_table())

    critical_agents = [r for r in results if len(r.critical_issues) > 0]
    if critical_agents:
        console.print(
            f"\n🚨 [bold red]CRITICAL: {len(critical_agents)} agents have critical issues[/ bold red]"
        )
        for agent in critical_agents:
            console.print(f" • {agent.agent_name}: {'; '.join(agent.critical_issues)}")

    auditor.save_detailed_report()

    console.print(f"\n✅ Audit complete: {len(results)} agents analyzed")

    return results


if __name__ == "__main__":
    asyncio.run(main())
