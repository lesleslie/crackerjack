"""AST Transform Engine for automated code refactoring.

This module provides pattern-based AST transformations for reducing
cognitive complexity in Python code. It integrates with the PlanningAgent
to automatically fix complexity issues.

Example usage:
    from crackerjack.agents.helpers.ast_transform import ASTTransformEngine

    engine = ASTTransformEngine()
    result = engine.transform(issue, context)
    if result:
        # Apply the changes
        pass
"""

from .engine import ASTTransformEngine
from .exceptions import (
    AsyncPatternUnsupported,
    BehaviorChanged,
    BothSurgeonsFailed,
    ComplexityIncreased,
    ComplexityNotReduced,
    ComplexityTimeout,
    FormattingLost,
    NoPatternMatch,
    ParseError,
    TransformError,
    TransformFailed,
    ValidationFailed,
    WalrusOperatorConflict,
)
from .pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternMatcher,
    PatternPriority,
)
from .patterns import (
    DataProcessingPattern,
    DecomposeConditionalPattern,
    EarlyReturnPattern,
    ExtractMethodPattern,
    GuardClausePattern,
)
from .surgeons.base import BaseSurgeon, TransformResult
from .surgeons.libcst_surgeon import LibcstSurgeon
from .surgeons.redbaron_surgeon import RedbaronSurgeon
from .validator import TransformValidator, ValidationResult

__all__ = [
    # Engine
    "ASTTransformEngine",
    # Exceptions
    "TransformError",
    "ParseError",
    "NoPatternMatch",
    "TransformFailed",
    "ValidationFailed",
    "ComplexityNotReduced",
    "BehaviorChanged",
    "BothSurgeonsFailed",
    "ComplexityIncreased",
    "FormattingLost",
    "ComplexityTimeout",
    "WalrusOperatorConflict",
    "AsyncPatternUnsupported",
    # Pattern matching
    "BasePattern",
    "PatternMatch",
    "PatternMatcher",
    "PatternPriority",
    # Patterns
    "DataProcessingPattern",
    "DecomposeConditionalPattern",
    "EarlyReturnPattern",
    "ExtractMethodPattern",
    "GuardClausePattern",
    # Surgeons
    "BaseSurgeon",
    "TransformResult",
    "LibcstSurgeon",
    "RedbaronSurgeon",
    # Validation
    "TransformValidator",
    "ValidationResult",
]
