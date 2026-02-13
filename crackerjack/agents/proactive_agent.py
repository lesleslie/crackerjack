import typing as t
from abc import abstractmethod
from pathlib import Path

from .base import AgentContext, FixResult, Issue, IssueType, SubAgent
from .file_context import FileContextReader


class ProactiveAgent(SubAgent):
    MAX_DIFF_LINES = 50  # Maximum lines a fix should modify

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self._planning_cache: dict[str, dict[str, t.Any]] = {}
        self._pattern_cache: dict[str, t.Any] = {}
        self._file_reader = FileContextReader()

        self._type_specific_confidence: dict[str, float] = {
            "refurb": 0.85,
            "type_error": 0.75,
            "formatting": 0.90,
            "security": 0.60,
        }

    async def can_handle(self, issue: Issue) -> float:

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

        if issue.type in self._type_specific_confidence:
            return self._type_specific_confidence[issue.type]

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
        return {
            IssueType.FORMATTING,
            IssueType.TYPE_ERROR,
            IssueType.REFURB,
            IssueType.COMPLEXITY,
            IssueType.SECURITY,
            IssueType.IMPORT_ERROR,
        }

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        return {"strategy": "default"}

    def _validate_diff_size(self, old_code: str, new_code: str) -> bool:
        """Validate that diff size is within acceptable limits.

        Args:
            old_code: Original code
            new_code: Proposed new code

        Returns:
            True if diff size is acceptable, False otherwise

        Enforces MAX_DIFF_LINES to prevent risky large modifications.
        """
        old_lines = old_code.count("\n")
        new_lines = new_code.count("\n")
        diff_lines = abs(new_lines - old_lines)

        if diff_lines > ProactiveAgent.MAX_DIFF_LINES:
            if self is not None:
                self.log(
                    f"⚠️  Diff too large: {diff_lines} lines "
                    f"(max: {ProactiveAgent.MAX_DIFF_LINES})"
                )
            return False

        return True

    async def execute_with_plan(
        self,
        issue: Issue,
        plan: dict[str, t.Any],
    ) -> FixResult:

        return FixResult(
            success=True,
            confidence=0.5,
            fixes_applied=[],
            remaining_issues=[],
        )

    async def _read_file_context(self, file_path: str | Path) -> str:
        """
        Read full file context before generating any fix.

        This is MANDATORY before _generate_fix() to ensure agents have
        complete context and don't generate broken code.

        Args:
            file_path: Path to file to read

        Returns:
            Full file content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        return await self._file_reader.read_file(file_path)

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
