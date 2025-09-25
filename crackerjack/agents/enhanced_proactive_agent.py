"""
Enhanced proactive agent that integrates Claude Code external agent consultation.

This module extends the base ProactiveAgent to consult with Claude Code's external
agents (like crackerjack-architect, python-pro, security-auditor) when handling
complex issues that require specialized expertise.
"""

import typing as t
from abc import abstractmethod

from .base import AgentContext, FixResult, Issue
from .claude_code_bridge import ClaudeCodeBridge
from .proactive_agent import ProactiveAgent


class EnhancedProactiveAgent(ProactiveAgent):
    """
    Proactive agent enhanced with Claude Code external agent consultation.

    This agent follows the standard crackerjack agent pattern but adds intelligent
    consultation with external Claude Code agents for complex scenarios that
    require specialized expertise.
    """

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.claude_bridge = ClaudeCodeBridge(context)
        self._external_consultation_enabled = True

    def enable_external_consultation(self, enabled: bool = True) -> None:
        """Enable or disable external Claude Code agent consultation."""
        self._external_consultation_enabled = enabled

    async def _execute_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        """
        Execute fix with plan, consulting external agents when appropriate.

        This method enhances the base implementation by:
        1. First attempting the internal fix
        2. Evaluating if external consultation would improve the result
        3. Consulting with relevant Claude Code agents
        4. Combining internal and external guidance for better results
        """
        # First, get the internal fix result
        internal_result = await self._execute_internal_fix(issue, plan)

        # Determine if we should consult external agents
        if not self._should_consult_external_agents(issue, internal_result, plan):
            return internal_result

        # Consult with relevant external agents
        external_consultations = await self._consult_external_agents(issue, plan)

        # Enhance the result with external guidance
        enhanced_result = self._combine_internal_and_external_results(
            internal_result, external_consultations
        )

        return enhanced_result

    async def _execute_internal_fix(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        """Execute the internal fix using the built-in agent logic."""
        # This calls the concrete agent's analyze_and_fix implementation
        return await self.analyze_and_fix(issue)

    def _should_consult_external_agents(
        self, issue: Issue, internal_result: FixResult, plan: dict[str, t.Any]
    ) -> bool:
        """Determine if external consultation would be beneficial."""
        if not self._external_consultation_enabled:
            return False

        # Consult external agents if:
        # 1. Internal result has low confidence
        # 2. Issue is complex and requires specialized expertise
        # 3. Plan strategy indicates external specialist guidance
        return (
            self.claude_bridge.should_consult_external_agent(
                issue, internal_result.confidence
            )
            or plan.get("strategy") == "external_specialist_guided"
            or not internal_result.success
        )

    async def _consult_external_agents(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> list[dict[str, t.Any]]:
        """Consult with relevant external Claude Code agents."""
        recommended_agents = self.claude_bridge.get_recommended_external_agents(issue)
        consultations = []

        # Limit to top 2 agents to avoid overwhelming the system
        for agent_name in recommended_agents[:2]:
            if self.claude_bridge.verify_agent_availability(agent_name):
                consultation = await self.claude_bridge.consult_external_agent(
                    issue, agent_name, {"plan": plan}
                )
                if consultation.get("status") == "success":
                    consultations.append(consultation)

        return consultations

    def _combine_internal_and_external_results(
        self, internal_result: FixResult, external_consultations: list[dict[str, t.Any]]
    ) -> FixResult:
        """Combine internal fix result with external agent consultations."""
        if not external_consultations:
            return internal_result

        # Use the bridge to create an enhanced result
        enhanced_result = self.claude_bridge.create_enhanced_fix_result(
            internal_result, external_consultations
        )

        # Add metadata about external consultation
        enhanced_result.recommendations.insert(
            0,
            f"Enhanced with consultation from {len(external_consultations)} Claude Code agents",
        )

        return enhanced_result

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        """
        Create a plan that considers both internal and external capabilities.

        This method should be implemented by concrete agents to define their
        specific planning logic while having access to external consultation.
        """
        # Default implementation - concrete agents should override this
        if self.claude_bridge.should_consult_external_agent(issue, 0.0):
            return {
                "strategy": "external_specialist_guided",
                "approach": "consult_claude_code_experts",
                "patterns": ["external_guidance"],
                "validation": ["verify_with_external_agents"],
            }

        return {
            "strategy": "internal_pattern_based",
            "approach": "apply_internal_logic",
            "patterns": ["standard_patterns"],
            "validation": ["run_internal_checks"],
        }

    @abstractmethod
    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """
        Concrete agents must implement their specific fix logic.

        This method contains the core agent-specific logic for analyzing
        and fixing issues. The enhanced execution framework will automatically
        handle external consultation when appropriate.
        """
        pass


# Convenience function to enhance existing agents
def enhance_agent_with_claude_code_bridge(
    agent_class: type[ProactiveAgent],
) -> type[EnhancedProactiveAgent]:
    """
    Enhance an existing ProactiveAgent class with Claude Code external consultation.

    This function creates a new class that inherits from both the original agent
    and EnhancedProactiveAgent, providing external consultation capabilities
    while preserving the original agent's logic.
    """

    class EnhancedAgent(EnhancedProactiveAgent, agent_class):  # type: ignore[misc,valid-type]
        def __init__(self, context: AgentContext) -> None:
            # Initialize both parent classes
            EnhancedProactiveAgent.__init__(self, context)
            agent_class.__init__(self, context)

    # Preserve the original class name and metadata
    EnhancedAgent.__name__ = f"Enhanced{agent_class.__name__}"
    EnhancedAgent.__qualname__ = f"Enhanced{agent_class.__qualname__}"

    return EnhancedAgent
