"""Base surgeon interface for AST transformations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TransformResult:
    """Result of a surgeon transformation attempt."""

    success: bool
    transformed_code: str | None = None
    error_message: str | None = None
    pattern_name: str | None = None


class BaseSurgeon(ABC):
    """Abstract base class for code transformation surgeons.

    Surgeons are responsible for applying actual code transformations
    once a pattern has been matched. Each surgeon has a different
    approach to preserving formatting and handling edge cases.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the surgeon name for logging/error messages."""
        ...

    @abstractmethod
    def apply(
        self,
        code: str,
        match_info: dict,
        file_path: Path | None = None,
    ) -> TransformResult:
        """Apply transformation to code based on pattern match.

        Args:
            code: Original source code
            match_info: Information from pattern matching (line numbers, nodes, etc.)
            file_path: Optional file path for error reporting

        Returns:
            TransformResult with success status and transformed code or error
        """
        ...

    def can_handle(self, match_info: dict) -> bool:
        """Check if this surgeon can handle the given match.

        Override to add surgeon-specific constraints.

        Args:
            match_info: Pattern match information

        Returns:
            True if this surgeon can handle the transformation
        """
        return True
