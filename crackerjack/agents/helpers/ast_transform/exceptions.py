from pathlib import Path


class TransformError(Exception):
    def __init__(self, message: str, file_path: Path | None = None) -> None:
        self.file_path = file_path
        super().__init__(message)


class ParseError(TransformError):
    def __init__(self, message: str, file_path: Path | None = None) -> None:
        super().__init__(f"Parse error: {message}", file_path)


class NoPatternMatch(TransformError):
    def __init__(
        self, message: str = "No pattern matched", file_path: Path | None = None
    ) -> None:
        super().__init__(message, file_path)


class TransformFailed(TransformError):
    def __init__(
        self,
        message: str,
        surgeon_name: str,
        file_path: Path | None = None,
    ) -> None:
        self.surgeon_name = surgeon_name
        super().__init__(f"{surgeon_name} transform failed: {message}", file_path)


class ValidationFailed(TransformError):
    def __init__(
        self,
        message: str,
        gate: str,
        file_path: Path | None = None,
    ) -> None:
        self.gate = gate
        super().__init__(f"Validation failed ({gate}): {message}", file_path)


class ComplexityNotReduced(TransformError):
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
    def __init__(self, message: str, file_path: Path | None = None) -> None:
        super().__init__(f"Behavior changed: {message}", file_path)


class BothSurgeonsFailed(TransformError):
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
    def __init__(
        self, message: str = "Formatting lost", file_path: Path | None = None
    ) -> None:
        super().__init__(message, file_path)


class ComplexityTimeout(TransformError):
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
    def __init__(
        self, message: str = "Walrus operator conflict", file_path: Path | None = None
    ) -> None:
        super().__init__(message, file_path)


class AsyncPatternUnsupported(TransformError):
    def __init__(self, pattern_name: str, file_path: Path | None = None) -> None:
        self.pattern_name = pattern_name
        super().__init__(
            f"Pattern '{pattern_name}' doesn't support async functions",
            file_path,
        )
