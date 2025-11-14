"""
Bridge between crackerjack's built-in agents and Claude Code's external agents.

This module provides integration between the internal agent system and Claude Code's
specialized agents located in ~/.claude/agents. It enables crackerjack's built-in
agents to consult with expert external agents for complex scenarios.
"""

import logging
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.services.file_modifier import SafeFileModifier

from .base import AgentContext, FixResult, Issue, IssueType

# Conditional import - ClaudeCodeFixer may not be available
_claude_ai_available = False
ClaudeCodeFixer: type[t.Any] | None = None

with suppress(ImportError):
    from crackerjack.adapters.ai.claude import ClaudeCodeFixer  # type: ignore[no-redef]

    _claude_ai_available = True

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
    """Bridge for consulting Claude Code external agents with real AI integration."""

    def __init__(self, context: AgentContext) -> None:
        self.context = context
        self.logger = logging.getLogger(__name__)
        self._agent_path = Path.home() / ".claude" / "agents"
        self._consultation_cache: dict[str, dict[str, t.Any]] = {}

        # Real AI integration components (if available)
        self.ai_fixer: t.Any | None = None  # ClaudeCodeFixer instance or None
        self.file_modifier = SafeFileModifier()
        self._ai_available = _claude_ai_available

        if not self._ai_available:
            self.logger.warning(
                "Claude AI adapter not available - AI-powered fixes disabled"
            )

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

    async def _ensure_ai_fixer(self) -> t.Any:
        """Lazy initialization of AI fixer adapter.

        Returns:
            Initialized ClaudeCodeFixer instance

        Raises:
            RuntimeError: If Claude AI is not available or initialization fails
        """
        if not self._ai_available:
            raise RuntimeError(
                "Claude AI adapter not available - install ACB with 'uv add acb[ai]'"
            )

        if self.ai_fixer is None:
            if ClaudeCodeFixer is None:
                raise RuntimeError("ClaudeCodeFixer import failed")

            self.ai_fixer = ClaudeCodeFixer()
            await self.ai_fixer.init()
            self.logger.debug("Claude AI fixer initialized")

        return self.ai_fixer

    def _extract_ai_response_fields(
        self, ai_result: dict[str, t.Any]
    ) -> tuple[str, str, float, list[str], list[str]]:
        """Extract fields from AI result."""
        fixed_code = str(ai_result.get("fixed_code", ""))
        explanation = str(ai_result.get("explanation", "No explanation"))
        confidence = float(ai_result.get("confidence", 0.0))
        changes_made = ai_result.get("changes_made", [])
        potential_side_effects = ai_result.get("potential_side_effects", [])

        return fixed_code, explanation, confidence, changes_made, potential_side_effects

    async def _apply_fix_to_file(
        self, file_path: str, fixed_code: str, dry_run: bool
    ) -> dict[str, t.Any]:
        """Apply the fix to the file using SafeFileModifier."""
        modify_result = await self.file_modifier.apply_fix(
            file_path=file_path,
            fixed_content=fixed_code,
            dry_run=dry_run,
            create_backup=True,
        )
        return modify_result

    def _handle_successful_ai_fix(
        self,
        issue: Issue,
        file_path: str,
        confidence: float,
        changes_made: list[str],
        potential_side_effects: list[str],
        fix_type: str,
    ) -> FixResult:
        """Handle the case when the AI successfully fixes the issue."""
        self.logger.info(
            f"Successfully applied AI fix to {file_path} (confidence: {confidence:.2f})"
        )

        return FixResult(
            success=True,
            confidence=confidence,
            fixes_applied=[f"Fixed {fix_type} in {file_path}"],
            remaining_issues=[],
            recommendations=[
                issue.message,
                *[f"Change: {change}" for change in changes_made],
                *[
                    f"Potential side effect: {effect}"
                    for effect in potential_side_effects
                ],
            ],
            files_modified=[file_path],
        )

    def _handle_dry_run_response(
        self, confidence: float, changes_made: list[str], issue: Issue
    ) -> FixResult:
        """Handle the case for dry-run mode."""
        return FixResult(
            success=True,
            confidence=confidence,
            fixes_applied=[],
            remaining_issues=[issue.id],
            recommendations=[
                f"AI suggests (dry-run): {issue.message}",
                *[f"Change: {change}" for change in changes_made],
            ],
            files_modified=[],
        )

    def _handle_error_response(self, error_msg: str, issue: Issue) -> FixResult:
        """Handle the case when there's an error in AI fix."""
        self.logger.error(f"AI fix failed: {error_msg}")

        return FixResult(
            success=False,
            confidence=0.0,
            fixes_applied=[],
            remaining_issues=[issue.id],
            recommendations=[f"AI fix failed: {error_msg}"],
            files_modified=[],
        )

    def _handle_low_confidence_response(
        self, confidence: float, explanation: str, issue: Issue
    ) -> FixResult:
        """Handle the case when confidence is too low."""
        min_confidence = 0.7  # Match AI fixer's default
        self.logger.warning(
            f"AI confidence {confidence:.2f} below threshold {min_confidence}"
        )

        return FixResult(
            success=False,
            confidence=confidence,
            fixes_applied=[],
            remaining_issues=[issue.id],
            recommendations=[
                f"AI fix confidence {confidence:.2f} too low (threshold: {min_confidence})",
                explanation,
            ],
            files_modified=[],
        )

    async def _validate_ai_result(
        self, ai_result: dict[str, t.Any], issue: Issue
    ) -> tuple[str, str, float, list[str], list[str]] | None:
        """Validate AI result and extract fields.

        Returns:
            Tuple of (fixed_code, explanation, confidence, changes_made, side_effects)
            or None if validation failed (already returned FixResult)
        """
        # Check if AI fix was successful
        if not ai_result.get("success"):
            ai_result.get("error", "Unknown AI error")
            return None

        # Extract AI response fields
        (
            fixed_code,
            explanation,
            confidence,
            changes_made,
            potential_side_effects,
        ) = self._extract_ai_response_fields(ai_result)

        # Validate confidence threshold
        min_confidence = 0.7  # Match AI fixer's default
        if confidence < min_confidence:
            return None

        return (
            fixed_code,
            explanation,
            confidence,
            changes_made,
            potential_side_effects,
        )

    async def _apply_ai_fix(
        self,
        file_path: str,
        fixed_code: str,
        confidence: float,
        changes_made: list[str],
        potential_side_effects: list[str],
        fix_type: str,
        issue: Issue,
        dry_run: bool,
    ) -> FixResult:
        """Apply AI fix to file using SafeFileModifier."""
        modify_result = await self._apply_fix_to_file(file_path, fixed_code, dry_run)

        if not modify_result.get("success"):
            error_msg = modify_result.get("error", "Unknown modification error")
            self.logger.error(f"File modification failed: {error_msg}")

            return FixResult(
                success=False,
                confidence=confidence,
                fixes_applied=[],
                remaining_issues=[issue.id],
                recommendations=[
                    f"File modification failed: {error_msg}",
                    "",
                ],
                files_modified=[],
            )

        # Success - fix applied
        return self._handle_successful_ai_fix(
            issue,
            file_path,
            confidence,
            changes_made,
            potential_side_effects,
            fix_type,
        )

    async def consult_on_issue(
        self,
        issue: Issue,
        dry_run: bool = False,
    ) -> FixResult:
        """Consult with Claude AI to fix an issue using real AI integration.

        This method replaces the simulation-based approach with real AI-powered
        code fixing. It:
        1. Calls the ClaudeCodeFixer adapter to generate a fix
        2. Validates the AI response (confidence, success)
        3. Uses SafeFileModifier to safely apply changes
        4. Handles errors gracefully
        5. Returns a proper FixResult

        Args:
            issue: Issue to fix
            dry_run: If True, only generate fix without applying

        Returns:
            FixResult with fix details and success status
        """
        try:
            # Initialize AI fixer if needed
            fixer = await self._ensure_ai_fixer()

            # Extract issue details for AI context
            file_path = str(issue.file_path) if issue.file_path else "unknown"
            issue_description = issue.message  # Issue uses 'message' not 'description'
            code_snippet = "\n".join(issue.details) if issue.details else ""
            fix_type = issue.type.value

            self.logger.info(
                f"Consulting Claude AI for {fix_type} issue in {file_path}"
            )

            # Call AI fixer to generate code fix
            ai_result = await fixer.fix_code_issue(
                file_path=file_path,
                issue_description=issue_description,
                code_context=code_snippet,
                fix_type=fix_type,
            )

            # Validate AI result
            validation_result = await self._validate_ai_result(ai_result, issue)
            if validation_result is None:
                # Validation failed - extract error from ai_result
                if not ai_result.get("success"):
                    error_msg = ai_result.get("error", "Unknown AI error")
                    return self._handle_error_response(error_msg, issue)
                else:
                    # Low confidence
                    _, explanation, confidence, *_ = self._extract_ai_response_fields(
                        ai_result
                    )
                    return self._handle_low_confidence_response(
                        confidence, explanation, issue
                    )

            (
                fixed_code,
                explanation,
                confidence,
                changes_made,
                potential_side_effects,
            ) = validation_result

            # Apply fix using SafeFileModifier
            if not dry_run and fixed_code:
                return await self._apply_ai_fix(
                    file_path,
                    fixed_code,
                    confidence,
                    changes_made,
                    potential_side_effects,
                    fix_type,
                    issue,
                    dry_run,
                )
            else:
                # Dry-run mode or no code - just report recommendation
                return self._handle_dry_run_response(confidence, changes_made, issue)

        except Exception as e:
            self.logger.exception(f"Unexpected error in consult_on_issue: {e}")

            return FixResult(
                success=False,
                confidence=0.0,
                fixes_applied=[],
                remaining_issues=[issue.id],
                recommendations=[f"Unexpected error: {e}"],
                files_modified=[],
            )

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
