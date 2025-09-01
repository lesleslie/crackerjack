import typing as t
from abc import abstractmethod

from .base import AgentContext, FixResult, Issue, SubAgent


class ProactiveAgent(SubAgent):
    """Base class for agents that can plan before executing fixes.

    Proactive agents analyze the codebase and create architectural plans
    before applying fixes, preventing violations rather than just fixing them.
    """

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self._planning_cache: dict[str, dict[str, t.Any]] = {}
        self._pattern_cache: dict[str, t.Any] = {}

    @abstractmethod
    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        """Create an architectural plan before fixing the issue.

        Returns a plan dictionary with:
        - strategy: How to approach the fix
        - patterns: Recommended patterns to use
        - dependencies: Other changes needed
        - risks: Potential issues to watch for
        """
        pass

    async def analyze_and_fix_proactively(self, issue: Issue) -> FixResult:
        """Execute proactive fix with planning phase.

        1. Create architectural plan
        2. Apply fix following the plan
        3. Validate against plan
        4. Cache successful patterns
        """
        # Check planning cache first
        cache_key = self._get_planning_cache_key(issue)
        if cache_key in self._planning_cache:
            plan = self._planning_cache[cache_key]
            self.log(f"Using cached plan for {cache_key}")
        else:
            plan = await self.plan_before_action(issue)
            self._planning_cache[cache_key] = plan
            self.log(f"Created new plan for {cache_key}")

        # Execute the fix with the plan
        result = await self._execute_with_plan(issue, plan)

        # Cache successful patterns
        if result.success and result.confidence >= 0.8:
            self._cache_successful_pattern(issue, plan, result)

        return result

    async def _execute_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        """Execute the fix following the architectural plan."""
        # Default implementation falls back to standard analyze_and_fix
        # Subclasses should override to use the plan
        return await self.analyze_and_fix(issue)

    def _get_planning_cache_key(self, issue: Issue) -> str:
        """Generate cache key for planning."""
        return f"{issue.type.value}:{issue.file_path}:{issue.line_number}"

    def _cache_successful_pattern(
        self, issue: Issue, plan: dict[str, t.Any], result: FixResult
    ) -> None:
        """Cache successful patterns for future reuse."""
        pattern_key = f"{issue.type.value}_{plan.get('strategy', 'default')}"
        self._pattern_cache[pattern_key] = {
            "plan": plan,
            "confidence": result.confidence,
            "files_modified": result.files_modified,
            "fixes_applied": result.fixes_applied,
        }
        self.log(f"Cached successful pattern: {pattern_key}")

    def get_cached_patterns(self) -> dict[str, t.Any]:
        """Get all cached patterns for inspection."""
        return self._pattern_cache.copy()

    def clear_pattern_cache(self) -> None:
        """Clear the pattern cache."""
        self._pattern_cache.clear()
        self.log("Cleared pattern cache")

    def get_planning_confidence(self, issue: Issue) -> float:
        """Get confidence in planning ability for this issue."""
        # Check if we have cached patterns for this issue type
        issue_patterns = [
            key for key in self._pattern_cache if key.startswith(issue.type.value)
        ]

        if issue_patterns:
            # Higher confidence if we have successful patterns
            return min(0.9, 0.6 + (len(issue_patterns) * 0.1))

        # Base confidence from can_handle
        return 0.5
