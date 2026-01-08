import typing as t
from abc import abstractmethod

from .base import AgentContext, FixResult, Issue
from .claude_code_bridge import ClaudeCodeBridge
from .proactive_agent import ProactiveAgent


class EnhancedProactiveAgent(ProactiveAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.claude_bridge = ClaudeCodeBridge(context)
        self._external_consultation_enabled = True

    def enable_external_consultation(self, enabled: bool = True) -> None:
        self._external_consultation_enabled = enabled

    async def _execute_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        internal_result = await self._execute_internal_fix(issue, plan)

        if not self._should_consult_external_agents(issue, internal_result, plan):
            return internal_result

        external_consultations = await self._consult_external_agents(issue, plan)

        enhanced_result = self._combine_internal_and_external_results(
            internal_result, external_consultations
        )

        return enhanced_result

    async def _execute_internal_fix(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        return await self.analyze_and_fix(issue)

    def _should_consult_external_agents(
        self, issue: Issue, internal_result: FixResult, plan: dict[str, t.Any]
    ) -> bool:
        if not self._external_consultation_enabled:
            return False

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
        recommended_agents = self.claude_bridge.get_recommended_external_agents(issue)
        consultations = []

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
        if not external_consultations:
            return internal_result

        enhanced_result = self.claude_bridge.create_enhanced_fix_result(
            internal_result, external_consultations
        )

        enhanced_result.recommendations.insert(
            0,
            f"Enhanced with consultation from {len(external_consultations)} Claude Code agents",
        )

        return enhanced_result

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
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
        pass


def enhance_agent_with_claude_code_bridge(
    agent_class: type[ProactiveAgent],
) -> type[EnhancedProactiveAgent]:
    class EnhancedAgent(EnhancedProactiveAgent, agent_class):  # type: ignore[misc, valid-type]
        def __init__(self, context: AgentContext) -> None:
            EnhancedProactiveAgent.__init__(self, context)
            agent_class.__init__(self, context)

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return await agent_class.analyze_and_fix(self, issue)

    EnhancedAgent.__name__ = f"Enhanced{agent_class.__name__}"
    EnhancedAgent.__qualname__ = f"Enhanced{agent_class.__qualname__}"

    return EnhancedAgent
