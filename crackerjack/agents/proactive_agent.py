import typing as t
from abc import abstractmethod

from .base import AgentContext, FixResult, Issue, SubAgent


class ProactiveAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self._planning_cache: dict[str, dict[str, t.Any]] = {}
        self._pattern_cache: dict[str, t.Any] = {}

    @abstractmethod
    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        pass

    async def can_handle(self, issue: Issue) -> float:
        return 0.7 if issue.type in self.get_supported_types() else 0.0

    async def analyze_and_fix_proactively(self, issue: Issue) -> FixResult:
        cache_key = self._get_planning_cache_key(issue)
        if cache_key in self._planning_cache:
            plan = self._planning_cache[cache_key]
            self.log(f"Using cached plan for {cache_key}")
        else:
            plan = await self.plan_before_action(issue)
            self._planning_cache[cache_key] = plan
            self.log(f"Created new plan for {cache_key}")

        result = await self._execute_with_plan(issue, plan)

        if result.success and result.confidence >= 0.8:
            self._cache_successful_pattern(issue, plan, result)

        return result

    async def _execute_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        return await self.analyze_and_fix(issue)

    def _get_planning_cache_key(self, issue: Issue) -> str:
        return f"{issue.type.value}: {issue.file_path}: {issue.line_number}"

    def _cache_successful_pattern(
        self, issue: Issue, plan: dict[str, t.Any], result: FixResult
    ) -> None:
        pattern_key = f"{issue.type.value}_{plan.get('strategy', 'default')}"
        self._pattern_cache[pattern_key] = {
            "plan": plan,
            "confidence": result.confidence,
            "files_modified": result.files_modified,
            "fixes_applied": result.fixes_applied,
        }
        self.log(f"Cached successful pattern: {pattern_key}")

    def get_cached_patterns(self) -> dict[str, t.Any]:
        return self._pattern_cache.copy()

    def get_planning_confidence(self, issue: Issue) -> float:
        """Return a confidence score based on cached patterns for the issue type."""
        pattern_prefix = f"{issue.type.value}_"
        confidences = [
            t.cast(float, pattern.get("confidence", 0.0))
            for key, pattern in self._pattern_cache.items()
            if key.startswith(pattern_prefix)
        ]
        if not confidences:
            return 0.5
        return max(confidences)
