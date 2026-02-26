import asyncio
import hashlib
import time
import typing as t
from dataclasses import dataclass, field

from crackerjack.models.protocols import (
    DelegationMetrics,
)
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.logging import get_logger

if t.TYPE_CHECKING:
    from crackerjack.agents.base import AgentContext, FixResult, Issue, SubAgent
    from crackerjack.agents.coordinator import AgentCoordinator


@dataclass
class DelegationStats:
    total_delegations: int = 0
    successful_delegations: int = 0
    failed_delegations: int = 0
    total_latency_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    agents_used: dict[str, int] = field(default_factory=dict[str, int])

    @property
    def average_latency_ms(self) -> float:
        if self.total_delegations == 0:
            return 0.0
        return self.total_latency_ms / self.total_delegations

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    def to_dict(self) -> DelegationMetrics:
        return {
            "total_delegations": self.total_delegations,
            "successful_delegations": self.successful_delegations,
            "failed_delegations": self.failed_delegations,
            "average_latency_ms": self.average_latency_ms,
            "cache_hit_rate": self.cache_hit_rate,
            "agents_used": dict(self.agents_used),
        }


class AgentDelegator:
    def __init__(
        self,
        coordinator: "AgentCoordinator",
        cache: CrackerjackCache | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.cache = cache or CrackerjackCache()
        self.logger = get_logger(__name__)
        self._stats = DelegationStats()
        self._delegation_cache: dict[str, FixResult] = {}

    async def delegate_to_type_specialist(
        self,
        issue: "Issue",
        context: "AgentContext",
    ) -> "FixResult":
        from crackerjack.agents.base import IssueType

        if issue.type != IssueType.TYPE_ERROR:
            self.logger.warning(
                f"Expected TYPE_ERROR issue, got {issue.type.value}: {issue.message[:60]}"
            )

        return await self._delegate_to_agent(
            agent_name="TypeErrorSpecialistAgent",
            issue=issue,
            context=context,
        )

    async def delegate_to_dead_code_remover(
        self,
        issue: "Issue",
        context: "AgentContext",
        confidence: float = 0.8,
    ) -> "FixResult":
        from crackerjack.agents.base import IssueType

        if issue.type != IssueType.DEAD_CODE:
            self.logger.warning(
                f"Expected DEAD_CODE issue, got {issue.type.value}: {issue.message[:60]}"
            )

        return await self._delegate_to_agent(
            agent_name="DeadCodeRemovalAgent",
            issue=issue,
            context=context,
            extra_params={"confidence": confidence},
        )

    async def delegate_to_refurb_transformer(
        self,
        issue: "Issue",
        context: "AgentContext",
        refurb_code: str | None = None,
    ) -> "FixResult":
        from crackerjack.agents.base import IssueType

        if issue.type != IssueType.REFURB:
            self.logger.warning(
                f"Expected REFURB issue, got {issue.type.value}: {issue.message[:60]}"
            )

        extra_params: dict[str, t.Any] = {}
        if refurb_code:
            extra_params["refurb_code"] = refurb_code

        return await self._delegate_to_agent(
            agent_name="RefurbCodeTransformerAgent",
            issue=issue,
            context=context,
            extra_params=extra_params,
        )

    async def delegate_to_performance_optimizer(
        self,
        issue: "Issue",
        context: "AgentContext",
    ) -> "FixResult":
        from crackerjack.agents.base import IssueType

        if issue.type != IssueType.PERFORMANCE:
            self.logger.warning(
                f"Expected PERFORMANCE issue, got {issue.type.value}: {issue.message[:60]}"
            )

        return await self._delegate_to_agent(
            agent_name="PerformanceAgent",
            issue=issue,
            context=context,
        )

    async def delegate_batch(
        self,
        issues: list["Issue"],
        context: "AgentContext",
    ) -> list["FixResult"]:
        if not issues:
            return []

        from crackerjack.agents.base import FixResult

        self.logger.info(f"Starting batch delegation for {len(issues)} issues")

        tasks = [self._delegate_auto(issue, context) for issue in issues]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results: list[FixResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    f"Batch delegation failed for issue {issues[i].id}: {result}"
                )
                processed_results.append(
                    FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[f"Delegation failed: {result}"],
                    )
                )
            else:
                processed_results.append(result)  # type: ignore[arg-type]

        successful = sum(1 for r in processed_results if r.success)
        self.logger.info(
            f"Batch delegation complete: {successful}/{len(issues)} successful"
        )

        return processed_results

    def get_delegation_metrics(self) -> DelegationMetrics:
        return self._stats.to_dict()

    async def _delegate_auto(
        self,
        issue: "Issue",
        context: "AgentContext",
    ) -> "FixResult":
        from crackerjack.agents.base import IssueType

        delegation_map = {
            IssueType.TYPE_ERROR: self.delegate_to_type_specialist,
            IssueType.DEAD_CODE: self.delegate_to_dead_code_remover,
            IssueType.REFURB: self.delegate_to_refurb_transformer,
            IssueType.PERFORMANCE: self.delegate_to_performance_optimizer,
        }

        handler = delegation_map.get(issue.type)
        if handler:
            return await handler(issue, context)

        return await self._delegate_to_agent(
            agent_name="RefactoringAgent",
            issue=issue,
            context=context,
        )

    async def _delegate_to_agent(
        self,
        agent_name: str,
        issue: "Issue",
        context: "AgentContext",
        extra_params: dict[str, t.Any] | None = None,
    ) -> "FixResult":
        from crackerjack.agents.base import FixResult

        cache_key = self._create_cache_key(agent_name, issue, extra_params)

        if cache_key in self._delegation_cache:
            self._stats.cache_hits += 1
            self.logger.debug(f"Cache hit for {agent_name} on issue {issue.id[:8]}")
            return self._delegation_cache[cache_key]

        self._stats.cache_misses += 1

        if not self.coordinator.agents:
            self.coordinator.initialize_agents()

        agent = self._find_agent(agent_name)
        if agent is None:
            self.logger.warning(f"Agent {agent_name} not found for delegation")
            self._record_delegation(agent_name, success=False)
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Agent {agent_name} not available"],
            )

        start_time = time.perf_counter()
        try:
            result = await self._execute_agent(agent, issue, context)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            self._record_delegation(
                agent_name, success=result.success, latency_ms=elapsed_ms
            )

            if result.success and result.confidence > 0.7:
                self._delegation_cache[cache_key] = result
                self.logger.debug(
                    f"Cached successful result for {agent_name} on issue {issue.id[:8]}"
                )

            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._record_delegation(agent_name, success=False, latency_ms=elapsed_ms)
            self.logger.exception(f"Delegation to {agent_name} failed: {e}")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Delegation failed: {e}"],
            )

    def _find_agent(self, agent_name: str) -> "SubAgent | None":
        for agent in self.coordinator.agents:
            if agent.__class__.__name__ == agent_name:
                return agent
        return None

    async def _execute_agent(
        self,
        agent: "SubAgent",
        issue: "Issue",
        context: "AgentContext",
    ) -> "FixResult":
        confidence = await agent.can_handle(issue)
        if confidence < 0.3:
            from crackerjack.agents.base import FixResult

            self.logger.info(
                f"Agent {agent.name} declined issue (confidence: {confidence:.2f})"
            )
            return FixResult(
                success=False,
                confidence=confidence,
                remaining_issues=[
                    f"Agent {agent.name} declined (confidence: {confidence:.2f})"
                ],
            )

        self.logger.info(
            f"Delegating to {agent.name} (confidence: {confidence:.2f}): "
            f"{issue.file_path}:{issue.line_number}"
        )

        return await agent.analyze_and_fix(issue)

    def _create_cache_key(
        self,
        agent_name: str,
        issue: "Issue",
        extra_params: dict[str, t.Any] | None = None,
    ) -> str:
        content = (
            f"{agent_name}:{issue.type.value}:{issue.message}:"
            f"{issue.file_path}:{issue.line_number}"
        )
        if extra_params:
            sorted_params = sorted(extra_params.items())
            content += f":{sorted_params}"

        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

    def _record_delegation(
        self,
        agent_name: str,
        success: bool,
        latency_ms: float = 0.0,
    ) -> None:
        self._stats.total_delegations += 1
        self._stats.total_latency_ms += latency_ms

        if success:
            self._stats.successful_delegations += 1
        else:
            self._stats.failed_delegations += 1

        if agent_name not in self._stats.agents_used:
            self._stats.agents_used[agent_name] = 0
        self._stats.agents_used[agent_name] += 1

    def clear_cache(self) -> None:
        self._delegation_cache.clear()
        self.logger.info("Delegation cache cleared")

    def get_cache_size(self) -> int:
        return len(self._delegation_cache)
