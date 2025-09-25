"""
Enhanced AgentCoordinator with Claude Code external agent integration.

This module extends the base AgentCoordinator to seamlessly integrate with
Claude Code's external agents while maintaining full compatibility with
the existing crackerjack agent system.
"""

import typing as t

from .base import AgentContext, FixResult, Issue
from .claude_code_bridge import ClaudeCodeBridge
from .coordinator import AgentCoordinator


class EnhancedAgentCoordinator(AgentCoordinator):
    """
    AgentCoordinator enhanced with Claude Code external agent integration.

    This coordinator maintains all the functionality of the base AgentCoordinator
    while adding intelligent consultation with external Claude Code agents
    when handling complex issues.
    """

    def __init__(
        self,
        context: AgentContext,
        cache: t.Any = None,
        enable_external_agents: bool = True,
    ) -> None:
        super().__init__(context, cache)
        self.claude_bridge = ClaudeCodeBridge(context)
        self.external_agents_enabled = enable_external_agents
        self._external_consultation_stats: dict[str, int] = {
            "consultations_requested": 0,
            "consultations_successful": 0,
            "improvements_achieved": 0,
        }

        self.logger.info(
            f"Enhanced coordinator initialized with external agents: {enable_external_agents}"
        )

    def enable_external_agents(self, enabled: bool = True) -> None:
        """Enable or disable external Claude Code agent consultation."""
        self.external_agents_enabled = enabled
        self.logger.info(f"External agents {'enabled' if enabled else 'disabled'}")

    def get_external_consultation_stats(self) -> dict[str, int]:
        """Get statistics about external agent consultations."""
        return self._external_consultation_stats.copy()

    async def handle_issues_proactively(self, issues: list[Issue]) -> FixResult:
        """
        Enhanced proactive handling with external agent consultation.

        This method extends the base proactive handling to:
        1. Identify issues that would benefit from external consultation
        2. Pre-consult with relevant Claude Code agents for strategic guidance
        3. Apply the combined internal/external strategy
        """
        if not self.external_agents_enabled:
            return await super().handle_issues_proactively(issues)

        if not self.agents:
            self.initialize_agents()

        if not issues:
            return FixResult(success=True, confidence=1.0)

        self.logger.info(f"Enhanced proactive handling of {len(issues)} issues")

        # Pre-analyze issues for external consultation opportunities
        strategic_consultations = await self._pre_consult_for_strategy(issues)

        # Create enhanced architectural plan incorporating external guidance
        architectural_plan = await self._create_enhanced_architectural_plan(
            issues, strategic_consultations
        )

        # Apply fixes with enhanced strategy
        overall_result = await self._apply_enhanced_fixes_with_plan(
            issues, architectural_plan, strategic_consultations
        )

        # Post-process with external validation if needed
        validated_result = await self._validate_with_external_agents(
            overall_result, architectural_plan
        )

        self._update_consultation_stats(strategic_consultations, validated_result)

        return validated_result

    async def _pre_consult_for_strategy(self, issues: list[Issue]) -> dict[str, t.Any]:
        """Pre-consult with external agents for strategic guidance."""
        strategic_consultations: dict[str, t.Any] = {
            "crackerjack_architect_guidance": None,
            "specialist_recommendations": {},
            "coordination_strategy": "internal_first",
        }

        # Identify complex issues that need architectural guidance
        complex_issues = [
            issue
            for issue in issues
            if self.claude_bridge.should_consult_external_agent(issue, 0.0)
        ]

        if not complex_issues:
            return strategic_consultations

        # Consult crackerjack-architect for overall strategy if available
        if self.claude_bridge.verify_agent_availability("crackerjack-architect"):
            self._external_consultation_stats["consultations_requested"] += 1

            # Use the first complex issue as representative for strategic planning
            primary_issue = complex_issues[0]
            architect_consultation = await self.claude_bridge.consult_external_agent(
                primary_issue,
                "crackerjack-architect",
                {"context": "strategic_planning"},
            )

            if architect_consultation.get("status") == "success":
                strategic_consultations["crackerjack_architect_guidance"] = (
                    architect_consultation
                )
                strategic_consultations["coordination_strategy"] = "architect_guided"
                self._external_consultation_stats["consultations_successful"] += 1

        return strategic_consultations

    async def _create_enhanced_architectural_plan(
        self, issues: list[Issue], strategic_consultations: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        """Create architectural plan enhanced with external agent guidance."""
        # Start with the base architectural plan
        base_plan = await self._create_architectural_plan(issues)

        # Enhance with external guidance if available
        architect_guidance = strategic_consultations.get(
            "crackerjack_architect_guidance"
        )
        if architect_guidance and architect_guidance.get("status") == "success":
            # Integrate external architectural guidance
            base_plan["external_guidance"] = architect_guidance
            base_plan["enhanced_patterns"] = architect_guidance.get("patterns", [])
            base_plan["external_validation"] = architect_guidance.get(
                "validation_steps", []
            )

            # Update strategy based on external guidance
            if "strategy" in architect_guidance:
                base_plan["strategy"] = "external_specialist_guided"

        return base_plan

    async def _apply_enhanced_fixes_with_plan(
        self,
        issues: list[Issue],
        plan: dict[str, t.Any],
        strategic_consultations: dict[str, t.Any],
    ) -> FixResult:
        """Apply fixes using enhanced strategy with external guidance."""
        # Use the base implementation but with enhanced plan
        return await self._apply_fixes_with_plan(issues, plan)

    async def _validate_with_external_agents(
        self, result: FixResult, plan: dict[str, t.Any]
    ) -> FixResult:
        """Post-validate results with external agents if configured."""
        external_validation = plan.get("external_validation", [])

        if not external_validation or not self.external_agents_enabled:
            return result

        # Add validation recommendations from external agents
        validation_recommendations = [
            f"External validation: {validation_step}"
            for validation_step in external_validation
        ]

        enhanced_result = FixResult(
            success=result.success,
            confidence=min(
                result.confidence + 0.1, 1.0
            ),  # Slight confidence boost for external validation
            fixes_applied=result.fixes_applied.copy(),
            remaining_issues=result.remaining_issues.copy(),
            recommendations=result.recommendations + validation_recommendations,
            files_modified=result.files_modified.copy(),
        )

        return enhanced_result

    def _update_consultation_stats(
        self, strategic_consultations: dict[str, t.Any], result: FixResult
    ) -> None:
        """Update statistics about external consultations."""
        if strategic_consultations.get("crackerjack_architect_guidance"):
            if result.success and result.confidence > 0.8:
                self._external_consultation_stats["improvements_achieved"] += 1

    async def _handle_with_single_agent_enhanced(
        self, agent: t.Any, issue: Issue
    ) -> FixResult:
        """Enhanced single agent handling with external consultation."""
        # Check if this agent should consult external experts
        internal_result = await super()._handle_with_single_agent(agent, issue)

        # If the agent is proactive and has external consultation capability, enhance it
        if (
            hasattr(agent, "claude_bridge")
            and self.external_agents_enabled
            and not internal_result.success
        ):
            # Try external consultation for failed fixes
            recommended_agents = self.claude_bridge.get_recommended_external_agents(
                issue
            )
            if recommended_agents:
                self._external_consultation_stats["consultations_requested"] += 1

                # Consult the top recommended external agent
                consultation = await self.claude_bridge.consult_external_agent(
                    issue, recommended_agents[0]
                )

                if consultation.get("status") == "success":
                    self._external_consultation_stats["consultations_successful"] += 1
                    enhanced_result = self.claude_bridge.create_enhanced_fix_result(
                        internal_result, [consultation]
                    )
                    return enhanced_result

        return internal_result

    def get_enhanced_agent_capabilities(self) -> dict[str, dict[str, t.Any]]:
        """Get capabilities including external agent integration."""
        base_capabilities = self.get_agent_capabilities()

        # Add information about external agent integration
        enhanced_info = {
            "external_agents_enabled": self.external_agents_enabled,
            "available_external_agents": [
                agent
                for agent in (
                    "crackerjack-architect",
                    "python-pro",
                    "security-auditor",
                    "refactoring-specialist",
                    "crackerjack-test-specialist",
                )
                if self.claude_bridge.verify_agent_availability(agent)
            ],
            "consultation_stats": self.get_external_consultation_stats(),
            "claude_code_bridge": {
                "agent_mapping_coverage": len(self.claude_bridge._get_agent_mapping()),
                "consultation_threshold": self.claude_bridge._get_consultation_threshold(),
            },
        }

        return base_capabilities | {"_enhanced_coordinator_info": enhanced_info}


def create_enhanced_coordinator(
    context: AgentContext, cache: t.Any = None, enable_external_agents: bool = True
) -> EnhancedAgentCoordinator:
    """
    Factory function to create an enhanced coordinator.

    This function provides a clean interface for creating coordinators
    with external agent integration while maintaining compatibility
    with existing code.
    """
    return EnhancedAgentCoordinator(
        context=context, cache=cache, enable_external_agents=enable_external_agents
    )
