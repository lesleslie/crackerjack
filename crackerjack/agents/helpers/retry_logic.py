import logging
import typing as t
from enum import StrEnum

from ..base import AgentContext, FixResult, Issue


class FixStrategy(StrEnum):
    MINIMAL_EDIT = "minimal_edit"
    FUNCTION_REPLACEMENT = "function_replacement"
    ADD_ANNOTATION = "add_annotation"
    SAFE_MERGE = "safe_merge"
    CONSERVATIVE = "conservative"


class RetryConfig:
    MAX_ATTEMPTS = 3
    ENABLE_FALLBACKS = True
    VALIDATE_AFTER_EACH_ATTEMPT = True


logger = logging.getLogger(__name__)


class AgentRetryManager:
    def __init__(self, context: AgentContext, config: RetryConfig | None = None):
        self.context = context
        self.config = config or RetryConfig()
        self.attempt_history: list[dict[str, t.Any]] = []

    async def fix_with_strategies(
        self,
        issue: Issue,
        strategies: list[FixStrategy],
        fix_fn: t.Callable[[Issue, FixStrategy], t.Awaitable[FixResult]],
    ) -> FixResult:
        last_result = None

        for attempt_num, strategy in enumerate(strategies, 1):
            logger.info(
                f"Attempt {attempt_num}/{len(strategies)}: Using {strategy.value} strategy"
            )

            try:
                result = await fix_fn(issue, strategy)

                self.attempt_history.append(
                    {
                        "attempt": attempt_num,
                        "strategy": strategy.value,
                        "success": result.success,
                        "confidence": result.confidence,
                    }
                )

                if result.success:
                    logger.info(f"✅ Success with {strategy.value} strategy")
                    return result

                if result.confidence >= 0.7:
                    logger.info(
                        f"✅ Accepting partial success with {strategy.value} (confidence: {result.confidence})"
                    )
                    return result

                last_result = result

            except Exception as e:
                logger.error(f"❌ Exception with {strategy.value} strategy: {e}")
                last_result = FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"Exception during {strategy.value}: {e}"],
                )

        if last_result:
            logger.warning(f"All {len(strategies)} strategies failed")
            return last_result

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["All strategies failed to fix issue"],
            recommendations=["Consider manual intervention for this issue"],
        )

    def get_attempt_summary(self) -> dict[str, t.Any]:
        strategies_tried = [a["strategy"] for a in self.attempt_history]
        unique_strategies = list(dict.fromkeys(strategies_tried))
        return {
            "total_attempts": len(self.attempt_history),
            "strategies_tried": unique_strategies,
            "success_rate": sum(1 for a in self.attempt_history if a["success"])
            / max(len(self.attempt_history), 1),
        }


def create_retry_manager(
    context: AgentContext, config: RetryConfig | None = None
) -> AgentRetryManager:
    return AgentRetryManager(context, config)


def get_default_strategies_for_issue(issue: Issue) -> list[FixStrategy]:
    if issue.type == IssueType.TYPE_ERROR:
        if (
            "annotation" in issue.message.lower()
            or "has no attribute" in issue.message.lower()
        ):
            return [FixStrategy.ADD_ANNOTATION, FixStrategy.MINIMAL_EDIT]
        elif "await" in issue.message.lower():
            return [FixStrategy.MINIMAL_EDIT, FixStrategy.FUNCTION_REPLACEMENT]

        return [FixStrategy.MINIMAL_EDIT, FixStrategy.ADD_ANNOTATION]

    if issue.type == IssueType.COMPLEXITY:
        return [FixStrategy.FUNCTION_REPLACEMENT, FixStrategy.SAFE_MERGE]

    if issue.type == IssueType.DRY_VIOLATION:
        return [FixStrategy.SAFE_MERGE, FixStrategy.MINIMAL_EDIT]

    return [FixStrategy.CONSERVATIVE, FixStrategy.MINIMAL_EDIT]


from ..base import IssueType


def create_fix_strategy_instructions(strategy: FixStrategy) -> str:
    instructions = {
        FixStrategy.MINIMAL_EDIT: """
CRITICAL: MINIMAL EDIT STRATEGY
- ONLY modify the specific lines mentioned in the error message
- DO NOT regenerate entire functions or classes
- DO NOT add new helper methods or functions
- Preserve all existing code structure
- Make the smallest possible change to fix the error
""",
        FixStrategy.FUNCTION_REPLACEMENT: """
FUNCTION REPLACEMENT STRATEGY
- Replace ONLY the target function mentioned in the error
- DO NOT modify other functions in the file
- DO NOT add new helper methods (use existing ones)
- Preserve all imports and class structure
- Generate complete, syntactically valid function replacement
""",
        FixStrategy.ADD_ANNOTATION: """
TYPE ANNOTATION STRATEGY
- ONLY add type hints or annotations to fix the error
- DO NOT change function logic or structure
- DO NOT regenerate existing code
- Use proper typing imports (Any, Dict, List, Optional, etc.)
""",
        FixStrategy.SAFE_MERGE: """
SAFE MERGE STRATEGY
- Carefully merge new code with existing code
- DO NOT create duplicate function definitions
- Check if function/method already exists before adding
- Preserve existing implementations
""",
        FixStrategy.CONSERVATIVE: """
CONSERVATIVE STRATEGY
- Make minimal, safe changes
- Prioritize correctness over completeness
- DO NOT refactor or optimize existing code
- When in doubt, leave code as-is
""",
    }

    return instructions.get(strategy, "")
