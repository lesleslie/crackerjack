import ast
import typing as t
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict
from rich.console import Console

from .errors import ErrorCode, ExecutionError


class CleaningStepResult(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CleaningResult:
    file_path: Path
    success: bool
    steps_completed: list[str]
    steps_failed: list[str]
    warnings: list[str]
    original_size: int
    cleaned_size: int


class FileProcessorProtocol(Protocol):
    def read_file_safely(self, file_path: Path) -> str: ...
    def write_file_safely(self, file_path: Path, content: str) -> None: ...
    def backup_file(self, file_path: Path) -> Path: ...


class CleaningStepProtocol(Protocol):
    def __call__(self, code: str, file_path: Path) -> str: ...

    @property
    def name(self) -> str: ...


class ErrorHandlerProtocol(Protocol):
    def handle_file_error(
        self,
        file_path: Path,
        error: Exception,
        step: str,
    ) -> None: ...
    def log_cleaning_result(self, result: CleaningResult) -> None: ...


class FileProcessor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    console: Console
    logger: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner.file_processor")

    def read_file_safely(self, file_path: Path) -> str:
        try:
            return file_path.read_text(encoding="utf - 8")
        except UnicodeDecodeError:
            for encoding in ("latin1", "cp1252"):
                try:
                    content = file_path.read_text(encoding=encoding)
                    self.logger.warning(
                        f"File {file_path} read with {encoding} encoding",
                    )
                    return content
                except UnicodeDecodeError:
                    continue
            raise ExecutionError(
                message=f"Could not decode file {file_path}",
                error_code=ErrorCode.FILE_READ_ERROR,
            )
        except Exception as e:
            raise ExecutionError(
                message=f"Failed to read file {file_path}: {e}",
                error_code=ErrorCode.FILE_READ_ERROR,
            ) from e

    def write_file_safely(self, file_path: Path, content: str) -> None:
        try:
            file_path.write_text(content, encoding="utf - 8")
        except Exception as e:
            raise ExecutionError(
                message=f"Failed to write file {file_path}: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e

    def backup_file(self, file_path: Path) -> Path:
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
        try:
            backup_path.write_bytes(file_path.read_bytes())
            return backup_path
        except Exception as e:
            raise ExecutionError(
                message=f"Failed to create backup for {file_path}: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e


class CleaningErrorHandler(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    console: Console
    logger: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner.error_handler")

    def handle_file_error(self, file_path: Path, error: Exception, step: str) -> None:
        self.console.print(
            f"[bold bright_yellow]⚠️ Warning: {step} failed for {file_path}: {error}[/bold bright_yellow]",
        )

        self.logger.warning(
            "Cleaning step failed",
            extra={
                "file_path": str(file_path),
                "step": step,
                "error": str(error),
                "error_type": type(error).__name__,
            },
        )

    def log_cleaning_result(self, result: CleaningResult) -> None:
        if result.success:
            self.console.print(
                f"[green]✅ Cleaned {result.file_path}[/green] "
                f"({result.original_size} → {result.cleaned_size} bytes)",
            )
        else:
            self.console.print(
                f"[red]❌ Failed to clean {result.file_path}[/red] "
                f"({len(result.steps_failed)} steps failed)",
            )

        if result.warnings:
            for warning in result.warnings:
                self.console.print(f"[yellow]⚠️ {warning}[/yellow]")

        self.logger.info(
            "File cleaning completed",
            extra={
                "file_path": str(result.file_path),
                "success": result.success,
                "steps_completed": result.steps_completed,
                "steps_failed": result.steps_failed,
                "original_size": result.original_size,
                "cleaned_size": result.cleaned_size,
            },
        )


class CleaningPipeline(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_processor: t.Any
    error_handler: t.Any
    console: Console
    logger: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner.pipeline")

    def clean_file(
        self,
        file_path: Path,
        cleaning_steps: list[CleaningStepProtocol],
    ) -> CleaningResult:
        self.logger.info(f"Starting clean_file for {file_path}")
        try:
            original_code = self.file_processor.read_file_safely(file_path)
            original_size = len(original_code.encode("utf - 8"))

            result = self._apply_cleaning_pipeline(
                original_code,
                file_path,
                cleaning_steps,
            )

            if result.success and result.cleaned_code != original_code:
                self.file_processor.write_file_safely(file_path, result.cleaned_code)
                cleaned_size = len(result.cleaned_code.encode("utf - 8"))
            else:
                cleaned_size = original_size

            cleaning_result = CleaningResult(
                file_path=file_path,
                success=result.success,
                steps_completed=result.steps_completed,
                steps_failed=result.steps_failed,
                warnings=result.warnings,
                original_size=original_size,
                cleaned_size=cleaned_size,
            )

            self.error_handler.log_cleaning_result(cleaning_result)
            return cleaning_result

        except Exception as e:
            self.error_handler.handle_file_error(file_path, e, "file_processing")
            return CleaningResult(
                file_path=file_path,
                success=False,
                steps_completed=[],
                steps_failed=["file_processing"],
                warnings=[],
                original_size=0,
                cleaned_size=0,
            )

    @dataclass
    class PipelineResult:
        cleaned_code: str
        success: bool
        steps_completed: list[str]
        steps_failed: list[str]
        warnings: list[str]

    def _apply_cleaning_pipeline(
        self,
        code: str,
        file_path: Path,
        cleaning_steps: list[CleaningStepProtocol],
    ) -> PipelineResult:
        current_code = code
        steps_completed: list[str] = []
        steps_failed: list[str] = []
        warnings: list[str] = []
        overall_success = True

        for step in cleaning_steps:
            try:
                step_result = step(current_code, file_path)
                current_code = step_result
                steps_completed.append(step.name)

                self.logger.debug(
                    "Cleaning step completed",
                    extra={"step": step.name, "file_path": str(file_path)},
                )

            except Exception as e:
                self.error_handler.handle_file_error(file_path, e, step.name)
                steps_failed.append(step.name)
                warnings.append(f"{step.name} failed: {e}")

                self.logger.warning(
                    "Cleaning step failed, continuing with original code",
                    extra={
                        "step": step.name,
                        "file_path": str(file_path),
                        "error": str(e),
                    },
                )

        if steps_failed:
            success_ratio = len(steps_completed) / (
                len(steps_completed) + len(steps_failed)
            )
            overall_success = success_ratio >= 0.7

        return self.PipelineResult(
            cleaned_code=current_code,
            success=overall_success,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            warnings=warnings,
        )


class CodeCleaner(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    console: Console
    file_processor: t.Any = None
    error_handler: t.Any = None
    pipeline: t.Any = None
    logger: t.Any = None

    def model_post_init(self, _: t.Any) -> None:
        if self.logger is None:
            import logging

            self.logger = logging.getLogger("crackerjack.code_cleaner")

        if self.file_processor is None:
            self.file_processor = FileProcessor(console=self.console)

        if self.error_handler is None:
            self.error_handler = CleaningErrorHandler(console=self.console)

        if self.pipeline is None:
            self.pipeline = CleaningPipeline(
                file_processor=self.file_processor,
                error_handler=self.error_handler,
                console=self.console,
            )

    def clean_file(self, file_path: Path) -> CleaningResult:
        cleaning_steps = [
            self._create_line_comment_step(),
            self._create_docstring_step(),
            self._create_whitespace_step(),
            self._create_formatting_step(),
        ]

        return self.pipeline.clean_file(file_path, cleaning_steps)

    def clean_files(self, pkg_dir: Path | None = None) -> list[CleaningResult]:
        if pkg_dir is None:
            pkg_dir = Path.cwd()

        python_files = list(pkg_dir.rglob(" * .py"))
        results: list[CleaningResult] = []

        self.logger.info(f"Starting clean_files for {len(python_files)} files")
        for file_path in python_files:
            if self.should_process_file(file_path):
                result = self.clean_file(file_path)
                results.append(result)

        return results

    def should_process_file(self, file_path: Path) -> bool:
        ignore_patterns = {
            "__pycache__",
            ".git",
            ".venv",
            "site - packages",
            ".pytest_cache",
            "build",
            "dist",
        }

        for parent in file_path.parents:
            if parent.name in ignore_patterns:
                return False

        return not (file_path.name.startswith(".") or file_path.suffix != ".py")

    def _create_line_comment_step(self) -> CleaningStepProtocol:
        """Create a step for removing line comments while preserving special comments."""
        return self._LineCommentStep()

    def _create_docstring_step(self) -> CleaningStepProtocol:
        """Create a step for removing docstrings."""
        return self._DocstringStep()

    class _DocstringStep:
        """Step implementation for removing docstrings."""

        name = "remove_docstrings"

        def _is_docstring_node(self, node: ast.AST) -> bool:
            body = getattr(node, "body", None)
            return (
                hasattr(node, "body")
                and body is not None
                and len(body) > 0
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            )

        def _find_docstrings(self, tree: ast.AST) -> list[ast.AST]:
            docstring_nodes: list[ast.AST] = []
            finder = self._DocstringFinder(docstring_nodes, self._is_docstring_node)
            finder.visit(tree)
            return docstring_nodes

        class _DocstringFinder(ast.NodeVisitor):
            def __init__(
                self,
                docstring_nodes: list[ast.AST],
                is_docstring_node: t.Callable[[ast.AST], bool],
            ):
                self.docstring_nodes = docstring_nodes
                self.is_docstring_node = is_docstring_node

            def _add_if_docstring(self, node: ast.AST) -> None:
                if self.is_docstring_node(node) and hasattr(node, "body"):
                    body: list[ast.stmt] = getattr(node, "body")
                    self.docstring_nodes.append(body[0])
                self.generic_visit(node)

            def visit_Module(self, node: ast.Module) -> None:
                self._add_if_docstring(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._add_if_docstring(node)

        def __call__(self, code: str, file_path: Path) -> str:
            try:
                tree = ast.parse(code, filename=str(file_path))
            except SyntaxError:
                return self._regex_fallback_removal(code)

            docstring_nodes = self._find_docstrings(tree)

            if not docstring_nodes:
                return code

            lines = code.split("\n")
            lines_to_remove: set[int] = set()

            for node in docstring_nodes:
                # Most AST nodes have lineno and end_lineno attributes
                start_line = getattr(node, "lineno", 1)
                end_line = getattr(node, "end_lineno", start_line + 1)
                lines_to_remove.update(range(start_line, end_line))

            result_lines = [
                line for i, line in enumerate(lines, 1) if i not in lines_to_remove
            ]

            result = "\n".join(result_lines)
            return self._regex_fallback_removal(result)

        def _regex_fallback_removal(self, code: str) -> str:
            import re

            patterns = [
                r'^\s*""".*?"""\s*$',
                r"^\s*'''.*?'''\s*$",
                r'^\s*""".*?"""\s*$',
                r"^\s*'''.*?'''\s*$",
            ]
            result = code
            for pattern in patterns:
                result = re.sub(pattern, "", result, flags=re.MULTILINE | re.DOTALL)
            return result

    class _LineCommentStep:
        """Step implementation for removing line comments."""

        name = "remove_line_comments"

        def __call__(self, code: str, file_path: Path) -> str:
            lines = code.split("\n")
            # Performance: Use list comprehension instead of generator for small-to-medium files
            processed_lines = [self._process_line_for_comments(line) for line in lines]
            return "\n".join(processed_lines)

        def _process_line_for_comments(self, line: str) -> str:
            """Process a single line to remove comments while preserving strings."""
            if not line.strip() or self._is_preserved_comment_line(line):
                return line
            return self._remove_comment_from_line(line)

        def _is_preserved_comment_line(self, line: str) -> bool:
            """Check if this comment line should be preserved."""
            stripped = line.strip()
            if not stripped.startswith("#"):
                return False
            return self._has_preserved_pattern(stripped)

        def _has_preserved_pattern(self, stripped_line: str) -> bool:
            """Check if line contains preserved comment patterns."""
            preserved_patterns = ["coding: ", "encoding: ", "type: ", "noqa", "pragma"]
            return stripped_line.startswith("# !/ ") or any(
                pattern in stripped_line for pattern in preserved_patterns
            )

        def _remove_comment_from_line(self, line: str) -> str:
            """Remove comments from a line while preserving string literals."""
            result: list[str] = []
            string_state: dict[str, t.Any] = {"in_string": False, "quote_char": None}
            for i, char in enumerate(line):
                if self._should_break_at_comment(char, string_state):
                    break
                self._update_string_state(char, i, line, string_state)
                result.append(char)
            return "".join(result).rstrip()

        def _should_break_at_comment(self, char: str, state: dict[str, t.Any]) -> bool:
            """Check if we should break at a comment character."""
            return not state["in_string"] and char == "#"

        def _update_string_state(
            self,
            char: str,
            index: int,
            line: str,
            state: dict[str, t.Any],
        ) -> None:
            """Update string parsing state based on current character."""
            if self._is_string_start(char, state):
                state["in_string"], state["quote_char"] = True, char
            elif self._is_string_end(char, index, line, state):
                state["in_string"], state["quote_char"] = False, None

        def _is_string_start(self, char: str, state: dict[str, t.Any]) -> bool:
            """Check if character starts a string."""
            return not state["in_string"] and char in ('"', "'")

        def _is_string_end(
            self,
            char: str,
            index: int,
            line: str,
            state: dict[str, t.Any],
        ) -> bool:
            """Check if character ends a string."""
            return (
                state["in_string"]
                and char == state["quote_char"]
                and (index == 0 or line[index - 1] != "\\")
            )

    def _create_docstring_finder_class(
        self,
        docstring_nodes: list[ast.AST],
    ) -> type[ast.NodeVisitor]:
        class DocstringFinder(ast.NodeVisitor):
            def _is_docstring_node(self, node: ast.AST) -> bool:
                body = getattr(node, "body", None)
                return (
                    hasattr(node, "body")
                    and body is not None
                    and len(body) > 0
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                )

            def _add_if_docstring(self, node: ast.AST) -> None:
                if self._is_docstring_node(node) and hasattr(node, "body"):
                    body: list[ast.stmt] = getattr(node, "body")
                    docstring_nodes.append(body[0])
                self.generic_visit(node)

            def visit_Module(self, node: ast.Module) -> None:
                self._add_if_docstring(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._add_if_docstring(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._add_if_docstring(node)

        return DocstringFinder

    def _create_whitespace_step(self) -> CleaningStepProtocol:
        class WhitespaceStep:
            name = "remove_extra_whitespace"

            def __call__(self, code: str, file_path: Path) -> str:
                import re

                lines = code.split("\n")
                cleaned_lines: list[str] = []

                empty_line_count = 0

                for line in lines:
                    cleaned_line = line.rstrip()

                    if not cleaned_line.strip():
                        empty_line_count += 1
                        if empty_line_count <= 2:
                            cleaned_lines.append("")
                    else:
                        empty_line_count = 0

                        leading_whitespace = len(cleaned_line) - len(
                            cleaned_line.lstrip(),
                        )
                        content = cleaned_line.lstrip()

                        content = re.sub(r" {2, }", " ", content)

                        cleaned_line = cleaned_line[:leading_whitespace] + content
                        cleaned_lines.append(cleaned_line)

                while cleaned_lines and not cleaned_lines[-1].strip():
                    cleaned_lines.pop()

                result = "\n".join(cleaned_lines)
                if result and not result.endswith("\n"):
                    result += "\n"

                return result

        return WhitespaceStep()

    def _create_formatting_step(self) -> CleaningStepProtocol:
        class FormattingStep:
            name = "format_code"

            def __call__(self, code: str, file_path: Path) -> str:
                import re

                lines = code.split("\n")
                formatted_lines: list[str] = []

                for line in lines:
                    if line.strip():
                        leading_whitespace = len(line) - len(line.lstrip())
                        content = line.lstrip()

                        content = re.sub(
                            r"([ =+ \ -*/%<>!&|^ ])([ ^ =+ \ -*/%<>!&|^ ])",
                            r"\1 \2",
                            content,
                        )
                        content = re.sub(
                            r"([ ^ =+ \ -*/%<>!&|^ ])([ =+ \ -*/%<>!&|^ ])",
                            r"\1 \2",
                            content,
                        )

                        content = re.sub(r", ([ ^ \n])", r", \1", content)

                        content = re.sub(r": ([ ^ \n: ])", r": \1", content)

                        content = re.sub(r" {2, }", " ", content)

                        formatted_line = line[:leading_whitespace] + content
                        formatted_lines.append(formatted_line)
                    else:
                        formatted_lines.append(line)

                return "\n".join(formatted_lines)

        return FormattingStep()

    def remove_line_comments(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_line_comment_step()
        return step(code, file_path)

    def remove_docstrings(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_docstring_step()
        return step(code, file_path)

    def remove_extra_whitespace(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_whitespace_step()
        return step(code, file_path)

    def format_code(self, code: str, file_path: Path | None = None) -> str:
        file_path = file_path or Path("temp.py")
        step = self._create_formatting_step()
        return step(code, file_path)
