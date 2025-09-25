"""
Bridge between crackerjack's built-in agents and Claude Code's external agents.

This module provides integration between the internal agent system and Claude Code's
specialized agents located in ~/.claude/agents. It enables crackerjack's built-in
agents to consult with expert external agents for complex scenarios.
"""

import logging
import typing as t
from pathlib import Path

from .base import AgentContext, FixResult, Issue, IssueType

# Mapping of internal issue types to Claude Code external agents
CLAUDE_CODE_AGENT_MAPPING = {
    IssueType.COMPLEXITY: ["refactoring-specialist", "crackerjack-architect"],
    IssueType.DRY_VIOLATION: ["refactoring-specialist", "crackerjack-architect"],
    IssueType.PERFORMANCE: ["performance-specialist", "python-pro"],
    IssueType.SECURITY: ["security-auditor", "python-pro"],
    IssueType.TYPE_ERROR: ["python-pro", "crackerjack-architect"],
    IssueType.TEST_FAILURE: ["crackerjack-test-specialist", "python-pro"],
    IssueType.TEST_ORGANIZATION: ["crackerjack-test-specialist", "testing-specialist"],
    IssueType.IMPORT_ERROR: ["python-pro", "refactoring-specialist"],
    IssueType.DOCUMENTATION: ["documentation-specialist", "crackerjack-architect"],
    IssueType.FORMATTING: ["python-pro"],
}

# Minimum confidence threshold for consulting external agents
EXTERNAL_CONSULTATION_THRESHOLD = 0.8


class ClaudeCodeBridge:
    """Bridge for consulting Claude Code external agents."""

    def __init__(self, context: AgentContext) -> None:
        self.context = context
        self.logger = logging.getLogger(__name__)
        self._agent_path = Path.home() / ".claude" / "agents"
        self._consultation_cache: dict[str, dict[str, t.Any]] = {}

    def should_consult_external_agent(
        self, issue: Issue, internal_confidence: float
    ) -> bool:
        """Determine if we should consult an external Claude Code agent."""
        # Only consult for complex issues that meet threshold
        if internal_confidence >= EXTERNAL_CONSULTATION_THRESHOLD:
            return False

        # Check if we have relevant external agents for this issue type
        return issue.type in CLAUDE_CODE_AGENT_MAPPING

    def _get_agent_mapping(self) -> dict[t.Any, list[str]]:
        """Get the agent mapping for external access."""
        return CLAUDE_CODE_AGENT_MAPPING

    def _get_consultation_threshold(self) -> float:
        """Get the consultation threshold for external access."""
        return EXTERNAL_CONSULTATION_THRESHOLD

    def get_recommended_external_agents(self, issue: Issue) -> list[str]:
        """Get list of recommended external agents for an issue."""
        return CLAUDE_CODE_AGENT_MAPPING.get(issue.type, [])

    def verify_agent_availability(self, agent_name: str) -> bool:
        """Check if a Claude Code agent file exists."""
        agent_file = self._agent_path / f"{agent_name}.md"
        return agent_file.exists()

    async def consult_external_agent(
        self, issue: Issue, agent_name: str, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """
        Consult with a Claude Code external agent for expert guidance.

        This method would ideally use the Task tool to invoke external agents,
        but since we're within crackerjack's internal system, we'll simulate
        the consultation process and provide structured recommendations.
        """
        cache_key = (
            f"{agent_name}:{issue.type.value}:{issue.file_path}:{issue.line_number}"
        )

        if cache_key in self._consultation_cache:
            self.logger.debug(f"Using cached consultation for {agent_name}")
            return self._consultation_cache[cache_key]

        if not self.verify_agent_availability(agent_name):
            self.logger.warning(f"Agent {agent_name} not available in ~/.claude/agents")
            return {"status": "unavailable", "recommendations": []}

        # Generate consultation based on agent expertise and issue type
        consultation = await self._generate_agent_consultation(
            issue, agent_name, context
        )

        # Cache successful consultations
        if consultation.get("status") == "success":
            self._consultation_cache[cache_key] = consultation

        return consultation

    async def _generate_agent_consultation(
        self, issue: Issue, agent_name: str, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Generate structured consultation response from agent expertise."""
        consultation: dict[str, t.Any] = {
            "status": "success",
            "agent": agent_name,
            "issue_type": issue.type.value,
            "recommendations": [],
            "patterns": [],
            "validation_steps": [],
            "confidence": 0.9,
        }

        # Agent-specific consultation logic
        if agent_name == "crackerjack-architect":
            consultation.update(
                await self._consult_crackerjack_architect(issue, context)
            )
        elif agent_name == "python-pro":
            consultation.update(await self._consult_python_pro(issue, context))
        elif agent_name == "security-auditor":
            consultation.update(await self._consult_security_auditor(issue, context))
        elif agent_name == "refactoring-specialist":
            consultation.update(
                await self._consult_refactoring_specialist(issue, context)
            )
        elif agent_name == "crackerjack-test-specialist":
            consultation.update(await self._consult_test_specialist(issue, context))
        else:
            consultation.update(
                await self._consult_generic_agent(issue, agent_name, context)
            )

        return consultation

    async def _consult_crackerjack_architect(
        self, issue: Issue, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Consult with crackerjack-architect for architectural guidance."""
        return {
            "recommendations": [
                "Apply clean code principles (DRY, YAGNI, KISS)",
                "Follow crackerjack's modular architecture patterns",
                "Use protocol-based dependency injection",
                "Break complex functions into focused helper methods",
                "Maintain single responsibility principle",
            ],
            "patterns": [
                "extract_method",
                "dependency_injection",
                "protocol_interfaces",
                "helper_methods",
                "single_responsibility",
            ],
            "validation_steps": [
                "run_complexity_check",
                "verify_type_annotations",
                "check_architectural_consistency",
                "validate_against_crackerjack_patterns",
            ],
        }

    async def _consult_python_pro(
        self, issue: Issue, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Consult with python-pro for Python-specific best practices."""
        return {
            "recommendations": [
                "Use modern Python 3.13+ type hints with | unions",
                "Apply proper error handling patterns",
                "Follow PEP 8 style guidelines",
                "Use pathlib over os.path",
                "Implement proper context managers",
            ],
            "patterns": [
                "type_annotations",
                "context_managers",
                "exception_handling",
                "python_idioms",
                "modern_syntax",
            ],
            "validation_steps": [
                "run_type_checking",
                "verify_python_compatibility",
                "check_style_compliance",
                "validate_error_handling",
            ],
        }

    async def _consult_security_auditor(
        self, issue: Issue, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Consult with security-auditor for security best practices."""
        return {
            "recommendations": [
                "Never use hardcoded paths or credentials",
                "Use secure temp file creation",
                "Avoid shell=True in subprocess calls",
                "Implement proper input validation",
                "Use environment variables for sensitive data",
            ],
            "patterns": [
                "secure_temp_files",
                "input_validation",
                "safe_subprocess",
                "environment_variables",
                "sanitization",
            ],
            "validation_steps": [
                "run_security_scan",
                "check_for_hardcoded_secrets",
                "validate_subprocess_calls",
                "verify_temp_file_handling",
            ],
        }

    async def _consult_refactoring_specialist(
        self, issue: Issue, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Consult with refactoring-specialist for code improvement."""
        return {
            "recommendations": [
                "Break down complex functions (complexity ≤ 15)",
                "Extract common patterns into utilities",
                "Remove dead code and unused imports",
                "Apply DRY principle to eliminate duplication",
                "Use composition over inheritance",
            ],
            "patterns": [
                "extract_method",
                "eliminate_duplication",
                "dead_code_removal",
                "complexity_reduction",
                "composition_pattern",
            ],
            "validation_steps": [
                "measure_complexity_reduction",
                "verify_test_coverage_maintained",
                "check_for_dead_code",
                "validate_duplication_removal",
            ],
        }

    async def _consult_test_specialist(
        self, issue: Issue, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Consult with crackerjack-test-specialist for testing guidance."""
        return {
            "recommendations": [
                "Avoid complex async tests that can hang",
                "Use synchronous config tests for reliability",
                "Mock external dependencies properly",
                "Follow crackerjack's testing patterns",
                "Maintain test coverage ratchet",
            ],
            "patterns": [
                "synchronous_tests",
                "proper_mocking",
                "test_organization",
                "coverage_improvement",
                "fixture_patterns",
            ],
            "validation_steps": [
                "run_test_suite",
                "verify_coverage_increase",
                "check_test_reliability",
                "validate_mock_usage",
            ],
        }

    async def _consult_generic_agent(
        self, issue: Issue, agent_name: str, context: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Generic consultation for unspecified agents."""
        return {
            "recommendations": [
                f"Consult {agent_name} documentation for specific guidance",
                "Apply domain-specific best practices",
                "Follow established patterns and conventions",
            ],
            "patterns": ["domain_specific_patterns"],
            "validation_steps": ["validate_domain_requirements"],
        }

    def create_enhanced_fix_result(
        self, base_result: FixResult, consultations: list[dict[str, t.Any]]
    ) -> FixResult:
        """Enhance a FixResult with external agent consultations."""
        enhanced_result = FixResult(
            success=base_result.success,
            confidence=base_result.confidence,
            fixes_applied=base_result.fixes_applied.copy(),
            remaining_issues=base_result.remaining_issues.copy(),
            recommendations=base_result.recommendations.copy(),
            files_modified=base_result.files_modified.copy(),
        )

        # Aggregate recommendations from all consultations
        for consultation in consultations:
            if consultation.get("status") == "success":
                agent_name = consultation.get("agent", "unknown")
                enhanced_result.recommendations.extend(
                    [
                        f"[{agent_name}] {rec}"
                        for rec in consultation.get("recommendations", [])
                    ]
                )

                # Boost confidence if external agents provided guidance
                external_confidence = consultation.get("confidence", 0.0)
                enhanced_result.confidence = max(
                    enhanced_result.confidence,
                    (enhanced_result.confidence + external_confidence) / 2,
                )

        return enhanced_result
