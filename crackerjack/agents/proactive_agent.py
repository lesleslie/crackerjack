import typing as t
from abc import ABC, abstractmethod
from .base import AgentContext, FixResult, Issue, IssueType, SubAgent
from crackerjack.agents.tracker import AgentTracker


class ProactiveAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self._planning_cache: dict[str, dict[str, t.Any]] = {}
        self._pattern_cache: dict[str, t.Any] = {}
        # Issue-specific confidence defaults for different problem types
        self._type_specific_confidence: dict[str, float] = {
            "refurb": 0.85,  # Style fixes are straightforward
            "type_error": 0.75,  # Type annotations are moderate confidence
            "formatting": 0.90,  # Formatting is high confidence
            "security": 0.60,  # Security needs analysis
        }

    async def can_handle(self, issue: Issue) -> float:
        # Issue-specific confidence: use specific default if available
        if issue.type in self._type_specific_confidence:
            return self._type_specific_confidence[issue.type]
        return 0.7 if issue.type in self.get_supported_types() else 0.0

    @abstractmethod
    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        pass

    @abstractmethod
    async def execute_with_plan(
        self,
        issue: Issue,
        plan: dict[str, t.Any],
    ) -> FixResult:
        pass

    async def analyze_and_fix_proactively(self, issue: Issue) -> FixResult:
        cache_key = self._get_planning_cache_key(issue)
        if cache_key in self._planning_cache:
            plan = self._planning_cache[cache_key]
            self.log(f"Using cached plan for {cache_key}")
        else:
            plan = await self.plan_before_action(issue)
            self._planning_cache[cache_key] = plan

        result = await self.execute_with_plan(issue, plan)

        if result.success and result.confidence >= 0.8:
            self._cache_successful_pattern(issue, plan, result)
        return result

    def _get_planning_cache_key(self, issue: Issue) -> str:
        return f"{issue.type.value}: {issue.file_path}: {issue.line_number}"

    def _cache_successful_pattern(
        self,
        issue: Issue,
        plan: dict[str, t.Any],
        result: FixResult,
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
        # Use issue-specific confidence if available, otherwise use base logic
        if issue.type in self._type_specific_confidence:
            return self._type_specific_confidence[issue.type]

        # Base logic: check cached patterns for this issue type
        pattern_prefix = f"{issue.type.value}_"
        confidences = [
            t.cast("float", pattern.get("confidence", 0.0))
            for key, pattern in self._pattern_cache.items()
            if key.startswith(pattern_prefix)
        ]

        if not confidences:
            return 0.5
        return max(confidences)

    def get_supported_types(self) -> set[IssueType]:
        """Return set of issue types this agent can handle."""
        return {
            IssueType.FORMATTING,
            IssueType.TYPE_ERROR,
            IssueType.REFURB,  # Added for Python style fixes
            IssueType.COMPLEXITY,
            IssueType.SECURITY,
            IssueType.IMPORT_ERROR,
        }

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        """Default implementation - agents can override."""
        return {"strategy": "default"}

    async def execute_with_plan(
        self,
        issue: Issue,
        plan: dict[str, t.Any],
    ) -> FixResult:
        """Default implementation - must be overridden by subclasses."""
        # By default, just return success without fixes
        return FixResult(
            success=True,
            confidence=0.5,  # Low confidence for default implementation
            fixes_applied=[],
            remaining_issues=[],
        )

    async def analyze_and_fix_proactively(self, issue: Issue) -> FixResult:
        """Analyze issue and attempt proactive fix with planning."""
        cache_key = self._get_planning_cache_key(issue)
        if cache_key in self._planning_cache:
            plan = self._planning_cache[cache_key]
            self.log(f"Using cached plan for {cache_key}")
        else:
            plan = await self.plan_before_action(issue)
            self._planning_cache[cache_key] = plan

        result = await self.execute_with_plan(issue, plan)

        if result.success and result.confidence >= 0.8:
            self._cache_successful_pattern(issue, plan, result)
        return result
