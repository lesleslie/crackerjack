"""Exception hierarchy for AST Transform Engine."""

from pathlib import Path


class TransformError(Exception):
    """Base exception for all transform errors."""

    def __init__(self, message: str, file_path: Path | None = None) -> None:
        self.file_path = file_path
        super().__init__(message)


class ParseError(TransformError):
    """Invalid Python syntax in source code."""

    def __init__(self, message: str, file_path: Path | None = None) -> None:
        super().__init__(f"Parse error: {message}", file_path)


class NoPatternMatch(TransformError):
    """Code doesn't match any known refactoring pattern."""

    def __init__(
        self, message: str = "No pattern matched", file_path: Path | None = None
    ) -> None:
        super().__init__(message, file_path)


class TransformFailed(TransformError):
    """Surgeon failed to apply transformation."""

    def __init__(
        self,
        message: str,
        surgeon_name: str,
        file_path: Path | None = None,
    ) -> None:
        self.surgeon_name = surgeon_name
        super().__init__(f"{surgeon_name} transform failed: {message}", file_path)


class ValidationFailed(TransformError):
    """Transform output failed validation gates."""

    def __init__(
        self,
        message: str,
        gate: str,
        file_path: Path | None = None,
    ) -> None:
        self.gate = gate
        super().__init__(f"Validation failed ({gate}): {message}", file_path)


class ComplexityNotReduced(TransformError):
    """Transform valid but complexity same or increased."""

    def __init__(
        self,
        original: int,
        transformed: int,
        file_path: Path | None = None,
    ) -> None:
        self.original_complexity = original
        self.transformed_complexity = transformed
        super().__init__(
            f"Complexity not reduced: {original} -> {transformed}",
            file_path,
        )


class BehaviorChanged(TransformError):
    """Transform changed function behavior/signature."""

    def __init__(self, message: str, file_path: Path | None = None) -> None:
        super().__init__(f"Behavior changed: {message}", file_path)


class BothSurgeonsFailed(TransformError):
    """Both libcst and redbaron surgeons failed."""

    def __init__(
        self,
        libcst_error: str,
        redbaron_error: str,
        file_path: Path | None = None,
    ) -> None:
        self.libcst_error = libcst_error
        self.redbaron_error = redbaron_error
        super().__init__(
            f"Both surgeons failed - libcst: {libcst_error}, redbaron: {redbaron_error}",
            file_path,
        )


class ComplexityIncreased(TransformError):
    """Transform made complexity WORSE."""

    def __init__(
        self,
        original: int,
        transformed: int,
        file_path: Path | None = None,
    ) -> None:
        self.original_complexity = original
        self.transformed_complexity = transformed
        super().__init__(
            f"Complexity INCREASED: {original} -> {transformed}",
            file_path,
        )


class FormattingLost(TransformError):
    """Comments/whitespace destroyed by transform."""

    def __init__(
        self, message: str = "Formatting lost", file_path: Path | None = None
    ) -> None:
        super().__init__(message, file_path)


class ComplexityTimeout(TransformError):
    """Complexity calculation exceeded timeout."""

    def __init__(
        self,
        timeout_seconds: float,
        file_path: Path | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Complexity calculation timed out after {timeout_seconds}s",
            file_path,
        )


class WalrusOperatorConflict(TransformError):
    """Guard clause conflicts with walrus operator."""

    def __init__(
        self, message: str = "Walrus operator conflict", file_path: Path | None = None
    ) -> None:
        super().__init__(message, file_path)


class AsyncPatternUnsupported(TransformError):
    """Pattern doesn't support async/await."""

    def __init__(self, pattern_name: str, file_path: Path | None = None) -> None:
        self.pattern_name = pattern_name
        super().__init__(
            f"Pattern '{pattern_name}' doesn't support async functions",
            file_path,
        )
