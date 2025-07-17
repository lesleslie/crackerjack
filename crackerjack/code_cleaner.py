import asyncio
import re
import subprocess
import typing as t
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from functools import lru_cache
from pathlib import Path

import aiofiles
from pydantic import BaseModel
from rich.console import Console

from .errors import ErrorCode, ExecutionError, handle_error


class CodeCleaner(BaseModel, arbitrary_types_allowed=True):
    console: Console

    def _analyze_workload_characteristics(self, files: list[Path]) -> dict[str, t.Any]:
        if not files:
            return {
                "total_files": 0,
                "total_size": 0,
                "avg_file_size": 0,
                "complexity": "low",
            }
        total_size = 0
        large_files = 0
        for file_path in files:
            try:
                size = file_path.stat().st_size
                total_size += size
                if size > 50_000:
                    large_files += 1
            except (OSError, PermissionError):
                continue
        avg_file_size = total_size / len(files) if files else 0
        large_file_ratio = large_files / len(files) if files else 0
        if len(files) > 100 or avg_file_size > 20_000 or large_file_ratio > 0.3:
            complexity = "high"
        elif len(files) > 50 or avg_file_size > 10_000 or large_file_ratio > 0.1:
            complexity = "medium"
        else:
            complexity = "low"

        return {
            "total_files": len(files),
            "total_size": total_size,
            "avg_file_size": avg_file_size,
            "large_files": large_files,
            "large_file_ratio": large_file_ratio,
            "complexity": complexity,
        }

    def _calculate_optimal_workers(self, workload: dict[str, t.Any]) -> int:
        import os

        cpu_count = os.cpu_count() or 4
        if workload["complexity"] == "high":
            max_workers = min(cpu_count // 2, 3)
        elif workload["complexity"] == "medium":
            max_workers = min(cpu_count, 6)
        else:
            max_workers = min(cpu_count + 2, 8)

        return min(max_workers, workload["total_files"])

    def clean_files(self, pkg_dir: Path | None) -> None:
        if pkg_dir is None:
            return
        python_files = [
            file_path
            for file_path in pkg_dir.rglob("*.py")
            if not str(file_path.parent).startswith("__")
        ]
        if not python_files:
            return
        workload = self._analyze_workload_characteristics(python_files)
        max_workers = self._calculate_optimal_workers(workload)
        if len(python_files) > 10:
            self.console.print(
                f"[dim]Cleaning {workload['total_files']} files "
                f"({workload['complexity']} complexity) with {max_workers} workers[/dim]"
            )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.clean_file, file_path): file_path
                for file_path in python_files
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    future.result()
                except Exception as e:
                    self.console.print(
                        f"[bold bright_red]❌ Error cleaning {file_path}: {e}[/bold bright_red]"
                    )
        self._cleanup_cache_directories(pkg_dir)

    def _cleanup_cache_directories(self, pkg_dir: Path) -> None:
        with suppress(PermissionError, OSError):
            pycache_dir = pkg_dir / "__pycache__"
            if pycache_dir.exists():
                for cache_file in pycache_dir.iterdir():
                    with suppress(PermissionError, OSError):
                        cache_file.unlink()
                pycache_dir.rmdir()
            parent_pycache = pkg_dir.parent / "__pycache__"
            if parent_pycache.exists():
                for cache_file in parent_pycache.iterdir():
                    with suppress(PermissionError, OSError):
                        cache_file.unlink()
                parent_pycache.rmdir()

    def clean_file(self, file_path: Path) -> None:
        try:
            code = file_path.read_text(encoding="utf-8")
            original_code = code
            cleaning_failed = False
            try:
                code = self.remove_line_comments_streaming(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove line comments from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.remove_docstrings_streaming(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove docstrings from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.remove_extra_whitespace_streaming(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove extra whitespace from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.reformat_code(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to reformat {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            file_path.write_text(code, encoding="utf-8")
            if cleaning_failed:
                self.console.print(
                    f"[bold yellow]⚡ Partially cleaned:[/bold yellow] [dim bright_white]{file_path}[/dim bright_white]"
                )
            else:
                self.console.print(
                    f"[bold green]✨ Cleaned:[/bold green] [dim bright_white]{file_path}[/dim bright_white]"
                )
        except PermissionError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Permission denied)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Permission denied while cleaning {file_path}",
                    error_code=ErrorCode.PERMISSION_ERROR,
                    details=str(e),
                    recovery=f"Check file permissions for {file_path} and ensure you have write access",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except OSError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (File system error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"File system error while cleaning {file_path}",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                    details=str(e),
                    recovery=f"Check that {file_path} exists and is not being used by another process",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except UnicodeDecodeError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Encoding error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Encoding error while reading {file_path}",
                    error_code=ErrorCode.FILE_READ_ERROR,
                    details=str(e),
                    recovery=f"File {file_path} contains non-UTF-8 characters. Please check the file encoding.",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except Exception as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Unexpected error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Unexpected error while cleaning {file_path}",
                    error_code=ErrorCode.UNEXPECTED_ERROR,
                    details=str(e),
                    recovery="This is an unexpected error. Please report this issue with the file content if possible.",
                ),
                console=self.console,
                exit_on_error=False,
            )

    def _initialize_docstring_state(self) -> dict[str, t.Any]:
        return {
            "in_docstring": False,
            "delimiter": None,
            "waiting": False,
            "function_indent": 0,
            "removed_docstring": False,
            "in_multiline_def": False,
        }

    def _handle_function_definition(
        self, line: str, stripped: str, state: dict[str, t.Any]
    ) -> bool:
        if self._is_function_or_class_definition(stripped):
            state["waiting"] = True
            state["function_indent"] = len(line) - len(line.lstrip())
            state["removed_docstring"] = False
            state["in_multiline_def"] = not stripped.endswith(":")
            return True
        return False

    def _handle_multiline_definition(
        self, line: str, stripped: str, state: dict[str, t.Any]
    ) -> bool:
        if state["in_multiline_def"]:
            if stripped.endswith(":"):
                state["in_multiline_def"] = False
            return True
        return False

    def _handle_waiting_docstring(
        self, lines: list[str], i: int, stripped: str, state: dict[str, t.Any]
    ) -> tuple[bool, str | None]:
        if state["waiting"] and stripped:
            if self._handle_docstring_start(stripped, state):
                pass_line = None
                if not state["in_docstring"]:
                    function_indent: int = state["function_indent"]
                    if self._needs_pass_statement(lines, i + 1, function_indent):
                        pass_line = " " * (function_indent + 4) + "pass"
                state["removed_docstring"] = True
                return True, pass_line
            else:
                state["waiting"] = False
        return False, None

    def _handle_docstring_content(
        self, lines: list[str], i: int, stripped: str, state: dict[str, t.Any]
    ) -> tuple[bool, str | None]:
        if state["in_docstring"]:
            if self._handle_docstring_end(stripped, state):
                pass_line = None
                function_indent: int = state["function_indent"]
                if self._needs_pass_statement(lines, i + 1, function_indent):
                    pass_line = " " * (function_indent + 4) + "pass"
                state["removed_docstring"] = False
                return True, pass_line
            else:
                return True, None
        return False, None

    def _process_line(
        self, lines: list[str], i: int, line: str, state: dict[str, t.Any]
    ) -> tuple[bool, str | None]:
        stripped = line.strip()
        if self._handle_function_definition(line, stripped, state):
            return True, line
        if self._handle_multiline_definition(line, stripped, state):
            return True, line
        handled, pass_line = self._handle_waiting_docstring(lines, i, stripped, state)
        if handled:
            return True, pass_line
        handled, pass_line = self._handle_docstring_content(lines, i, stripped, state)
        if handled:
            return True, pass_line
        if state["removed_docstring"] and stripped:
            state["removed_docstring"] = False
        return False, line

    def remove_docstrings(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines: list[str] = []
        docstring_state = self._initialize_docstring_state()
        for i, line in enumerate(lines):
            handled, result_line = self._process_line(lines, i, line, docstring_state)
            if handled:
                if result_line is not None:
                    cleaned_lines.append(result_line)
            else:
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def _is_function_or_class_definition(self, stripped_line: str) -> bool:
        return stripped_line.startswith(("def ", "class ", "async def "))

    def _handle_docstring_start(self, stripped: str, state: dict[str, t.Any]) -> bool:
        if not stripped.startswith(('"""', "'''", '"', "'")):
            return False
        if stripped.startswith(('"""', "'''")):
            delimiter = stripped[:3]
        else:
            delimiter = stripped[0]
        state["delimiter"] = delimiter
        if self._is_single_line_docstring(stripped, delimiter):
            state["waiting"] = False
            return True
        else:
            state["in_docstring"] = True
            state["waiting"] = False
            return True

    def _is_single_line_docstring(self, stripped: str, delimiter: str) -> bool:
        return stripped.endswith(delimiter) and len(stripped) > len(delimiter)

    def _handle_docstring_end(self, stripped: str, state: dict[str, t.Any]) -> bool:
        if state["delimiter"] and stripped.endswith(state["delimiter"]):
            state["in_docstring"] = False
            state["delimiter"] = None
            return True
        return False

    def _needs_pass_statement(
        self, lines: list[str], start_index: int, function_indent: int
    ) -> bool:
        for i in range(start_index, len(lines)):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                continue
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= function_indent:
                return True
            if line_indent > function_indent:
                return False
        return True

    def remove_line_comments(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines: list[str] = []
        for line in lines:
            if not line.strip():
                cleaned_lines.append(line)
                continue
            cleaned_line = self._process_line_for_comments(line)
            if cleaned_line or not line.strip():
                cleaned_lines.append(cleaned_line or line)
        return "\n".join(cleaned_lines)

    def _process_line_for_comments(self, line: str) -> str:
        result: list[str] = []
        string_state = {"in_string": None}
        for i, char in enumerate(line):
            if self._handle_string_character(char, i, line, string_state, result):
                continue
            elif self._handle_comment_character(char, i, line, string_state, result):
                break
            else:
                result.append(char)
        return "".join(result).rstrip()

    def _handle_string_character(
        self,
        char: str,
        index: int,
        line: str,
        string_state: dict[str, t.Any],
        result: list[str],
    ) -> bool:
        if char not in ("'", '"'):
            return False
        if index > 0 and line[index - 1] == "\\":
            return False
        if string_state["in_string"] is None:
            string_state["in_string"] = char
        elif string_state["in_string"] == char:
            string_state["in_string"] = None
        result.append(char)
        return True

    def _handle_comment_character(
        self,
        char: str,
        index: int,
        line: str,
        string_state: dict[str, t.Any],
        result: list[str],
    ) -> bool:
        if char != "#" or string_state["in_string"] is not None:
            return False
        comment = line[index:].strip()
        if self._is_special_comment_line(comment):
            result.append(line[index:])
        return True

    def _is_special_comment_line(self, comment: str) -> bool:
        special_comment_pattern = (
            r"^#\s*(?:type:\s*ignore(?:\[.*?\])?|noqa|nosec|pragma:\s*no\s*cover"
            r"|pylint:\s*disable|mypy:\s*ignore)"
        )
        return bool(re.match(special_comment_pattern, comment))

    def remove_extra_whitespace(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines: list[str] = []
        function_tracker = {"in_function": False, "function_indent": 0}
        import_tracker = {"in_imports": False, "last_import_type": None}
        for i, line in enumerate(lines):
            line = line.rstrip()
            stripped_line = line.lstrip()
            self._update_function_state(line, stripped_line, function_tracker)
            self._update_import_state(line, stripped_line, import_tracker)
            if not line:
                if self._should_skip_empty_line(
                    i, lines, cleaned_lines, function_tracker, import_tracker
                ):
                    continue
            cleaned_lines.append(line)
        return "\n".join(self._remove_trailing_empty_lines(cleaned_lines))

    def remove_docstrings_streaming(self, code: str) -> str:
        if len(code) < 10000:
            return self.remove_docstrings(code)

        def process_lines():
            lines = code.split("\n")
            docstring_state = self._initialize_docstring_state()
            for i, line in enumerate(lines):
                handled, result_line = self._process_line(
                    lines, i, line, docstring_state
                )
                if handled:
                    if result_line is not None:
                        yield result_line
                else:
                    yield line

        return "\n".join(process_lines())

    def remove_line_comments_streaming(self, code: str) -> str:
        if len(code) < 10000:
            return self.remove_line_comments(code)

        def process_lines():
            for line in code.split("\n"):
                if not line.strip():
                    yield line
                    continue
                cleaned_line = self._process_line_for_comments(line)
                if cleaned_line or not line.strip():
                    yield cleaned_line or line

        return "\n".join(process_lines())

    def remove_extra_whitespace_streaming(self, code: str) -> str:
        if len(code) < 10000:
            return self.remove_extra_whitespace(code)

        def process_lines():
            lines = code.split("\n")
            function_tracker: dict[str, t.Any] = {
                "in_function": False,
                "function_indent": 0,
            }
            import_tracker: dict[str, t.Any] = {
                "in_imports": False,
                "last_import_type": None,
            }
            previous_lines: list[str] = []
            for i, line in enumerate(lines):
                line = line.rstrip()
                stripped_line = line.lstrip()
                self._update_function_state(line, stripped_line, function_tracker)
                self._update_import_state(line, stripped_line, import_tracker)
                if not line:
                    if self._should_skip_empty_line(
                        i, lines, previous_lines, function_tracker, import_tracker
                    ):
                        continue
                previous_lines.append(line)
                yield line

        processed_lines = list(process_lines())
        return "\n".join(self._remove_trailing_empty_lines(processed_lines))

    def _update_function_state(
        self, line: str, stripped_line: str, function_tracker: dict[str, t.Any]
    ) -> None:
        if stripped_line.startswith(("def ", "async def ")):
            function_tracker["in_function"] = True
            function_tracker["function_indent"] = len(line) - len(stripped_line)
        elif self._is_function_end(line, stripped_line, function_tracker):
            function_tracker["in_function"] = False
            function_tracker["function_indent"] = 0

    def _update_import_state(
        self, line: str, stripped_line: str, import_tracker: dict[str, t.Any]
    ) -> None:
        if stripped_line.startswith(("import ", "from ")):
            import_tracker["in_imports"] = True
            if self._is_stdlib_import(stripped_line):
                current_type = "stdlib"
            elif self._is_local_import(stripped_line):
                current_type = "local"
            else:
                current_type = "third_party"
            import_tracker["last_import_type"] = current_type
        elif stripped_line and not stripped_line.startswith("#"):
            import_tracker["in_imports"] = False
            import_tracker["last_import_type"] = None

    @staticmethod
    @lru_cache(maxsize=256)
    def _is_stdlib_module(module: str) -> bool:
        stdlib_modules = {
            "os",
            "sys",
            "re",
            "json",
            "datetime",
            "time",
            "pathlib",
            "typing",
            "collections",
            "itertools",
            "functools",
            "operator",
            "math",
            "random",
            "uuid",
            "urllib",
            "http",
            "html",
            "xml",
            "email",
            "csv",
            "sqlite3",
            "subprocess",
            "threading",
            "multiprocessing",
            "asyncio",
            "contextlib",
            "dataclasses",
            "enum",
            "abc",
            "io",
            "tempfile",
            "shutil",
            "glob",
            "pickle",
            "copy",
            "heapq",
            "bisect",
            "array",
            "struct",
            "zlib",
            "hashlib",
            "hmac",
            "secrets",
            "base64",
            "binascii",
            "codecs",
            "locale",
            "platform",
            "socket",
            "ssl",
            "ipaddress",
            "logging",
            "warnings",
            "inspect",
            "ast",
            "dis",
            "tokenize",
            "keyword",
            "linecache",
            "traceback",
            "weakref",
            "gc",
            "ctypes",
            "unittest",
            "doctest",
            "pdb",
            "profile",
            "cProfile",
            "timeit",
            "trace",
            "calendar",
            "decimal",
            "fractions",
            "statistics",
            "tomllib",
        }
        return module in stdlib_modules

    def _is_stdlib_import(self, stripped_line: str) -> bool:
        try:
            if stripped_line.startswith("from "):
                module = stripped_line.split()[1].split(".")[0]
            else:
                module = stripped_line.split()[1].split(".")[0]
        except IndexError:
            return False
        return CodeCleaner._is_stdlib_module(module)

    def _is_local_import(self, stripped_line: str) -> bool:
        return stripped_line.startswith("from .") or " . " in stripped_line

    def _is_function_end(
        self, line: str, stripped_line: str, function_tracker: dict[str, t.Any]
    ) -> bool:
        return (
            function_tracker["in_function"]
            and bool(line)
            and (len(line) - len(stripped_line) <= function_tracker["function_indent"])
            and (not stripped_line.startswith(("@", "#")))
        )

    def _should_skip_empty_line(
        self,
        line_idx: int,
        lines: list[str],
        cleaned_lines: list[str],
        function_tracker: dict[str, t.Any],
        import_tracker: dict[str, t.Any],
    ) -> bool:
        if line_idx > 0 and cleaned_lines and (not cleaned_lines[-1]):
            return True

        if self._is_import_section_separator(line_idx, lines, import_tracker):
            return False

        if function_tracker["in_function"]:
            return self._should_skip_function_empty_line(line_idx, lines)
        return False

    def _is_import_section_separator(
        self, line_idx: int, lines: list[str], import_tracker: dict[str, t.Any]
    ) -> bool:
        if not import_tracker["in_imports"]:
            return False

        next_line_idx = line_idx + 1
        while next_line_idx < len(lines) and not lines[next_line_idx].strip():
            next_line_idx += 1

        if next_line_idx >= len(lines):
            return False

        next_line = lines[next_line_idx].strip()
        if not next_line.startswith(("import ", "from ")):
            return False

        if self._is_stdlib_import(next_line):
            next_type = "stdlib"
        elif self._is_local_import(next_line):
            next_type = "local"
        else:
            next_type = "third_party"

        return import_tracker["last_import_type"] != next_type

    def _should_skip_function_empty_line(self, line_idx: int, lines: list[str]) -> bool:
        next_line_idx = line_idx + 1
        if next_line_idx >= len(lines):
            return False
        next_line = lines[next_line_idx].strip()
        return not self._is_significant_next_line(next_line)

    def _is_significant_next_line(self, next_line: str) -> bool:
        if next_line.startswith(("return", "class ", "def ", "async def ", "@")):
            return True
        if next_line in ("pass", "break", "continue", "raise"):
            return True
        return self._is_special_comment(next_line)

    def _is_special_comment(self, line: str) -> bool:
        if not line.startswith("#"):
            return False
        special_patterns = ("type:", "noqa", "nosec", "pragma:", "pylint:", "mypy:")
        return any(pattern in line for pattern in special_patterns)

    def _remove_trailing_empty_lines(self, lines: list[str]) -> list[str]:
        while lines and (not lines[-1]):
            lines.pop()
        return lines

    def reformat_code(self, code: str) -> str:
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w+", delete=False
            ) as temp:
                temp_path = Path(temp.name)
                temp_path.write_text(code)
            try:
                result = subprocess.run(
                    ["uv", "run", "ruff", "format", str(temp_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    formatted_code = temp_path.read_text()
                else:
                    self.console.print(
                        f"[bold bright_yellow]⚠️  Ruff formatting failed: {result.stderr}[/bold bright_yellow]"
                    )
                    handle_error(
                        ExecutionError(
                            message="Code formatting failed",
                            error_code=ErrorCode.FORMATTING_ERROR,
                            details=result.stderr,
                            recovery="Check Ruff configuration and formatting rules",
                        ),
                        console=self.console,
                        exit_on_error=False,
                    )
                    formatted_code = code
            except Exception as e:
                self.console.print(
                    f"[bold bright_red]❌ Error running Ruff: {e}[/bold bright_red]"
                )
                handle_error(
                    ExecutionError(
                        message="Error running Ruff",
                        error_code=ErrorCode.FORMATTING_ERROR,
                        details=str(e),
                        recovery="Verify Ruff is installed and configured correctly",
                    ),
                    console=self.console,
                    exit_on_error=False,
                )
                formatted_code = code
            finally:
                with suppress(FileNotFoundError):
                    temp_path.unlink()
            return formatted_code
        except Exception as e:
            self.console.print(
                f"[bold bright_red]❌ Error during reformatting: {e}[/bold bright_red]"
            )
            handle_error(
                ExecutionError(
                    message="Error during reformatting",
                    error_code=ErrorCode.FORMATTING_ERROR,
                    details=str(e),
                    recovery="Check file permissions and disk space",
                ),
                console=self.console,
            )
            return code

    async def clean_files_async(self, pkg_dir: Path | None) -> None:
        if pkg_dir is None:
            return
        python_files = [
            file_path
            for file_path in pkg_dir.rglob("*.py")
            if not str(file_path.parent).startswith("__")
        ]
        if not python_files:
            return
        max_concurrent = min(len(python_files), 8)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def clean_with_semaphore(file_path: Path) -> None:
            async with semaphore:
                await self.clean_file_async(file_path)

        tasks = [clean_with_semaphore(file_path) for file_path in python_files]
        await asyncio.gather(*tasks, return_exceptions=True)

        await self._cleanup_cache_directories_async(pkg_dir)

    async def clean_file_async(self, file_path: Path) -> None:
        try:
            async with aiofiles.open(file_path, encoding="utf-8") as f:  # type: ignore[misc]
                code: str = await f.read()  # type: ignore[misc]
            original_code: str = code
            cleaning_failed = False
            try:
                code = self.remove_line_comments_streaming(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove line comments from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.remove_docstrings_streaming(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove docstrings from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.remove_extra_whitespace_streaming(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove extra whitespace from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = await self.reformat_code_async(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to reformat {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:  # type: ignore[misc]
                await f.write(code)  # type: ignore[misc]
            if cleaning_failed:
                self.console.print(
                    f"[bold yellow]⚡ Partially cleaned:[/bold yellow] [dim bright_white]{file_path}[/dim bright_white]"
                )
            else:
                self.console.print(
                    f"[bold green]✨ Cleaned:[/bold green] [dim bright_white]{file_path}[/dim bright_white]"
                )
        except PermissionError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Permission denied)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Permission denied while cleaning {file_path}",
                    error_code=ErrorCode.PERMISSION_ERROR,
                    details=str(e),
                    recovery=f"Check file permissions for {file_path} and ensure you have write access",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except OSError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (File system error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"File system error while cleaning {file_path}",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                    details=str(e),
                    recovery=f"Check that {file_path} exists and is not being used by another process",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except UnicodeDecodeError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Encoding error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Encoding error while cleaning {file_path}",
                    error_code=ErrorCode.FILE_READ_ERROR,
                    details=str(e),
                    recovery=f"Check the file encoding of {file_path} - it may not be UTF-8",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except Exception as e:
            self.console.print(f"[red]Unexpected error cleaning {file_path}: {e}[/red]")
            handle_error(
                ExecutionError(
                    message=f"Unexpected error while cleaning {file_path}",
                    error_code=ErrorCode.UNEXPECTED_ERROR,
                    details=str(e),
                    recovery="Please report this issue with the full error details",
                ),
                console=self.console,
                exit_on_error=False,
            )

    async def reformat_code_async(self, code: str) -> str:
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w+", delete=False
            ) as temp:
                temp_path = Path(temp.name)
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:  # type: ignore[misc]
                await f.write(code)  # type: ignore[misc]
            try:
                proc = await asyncio.create_subprocess_exec(
                    "uv",
                    "run",
                    "ruff",
                    "format",
                    str(temp_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0:
                    async with aiofiles.open(temp_path, encoding="utf-8") as f:  # type: ignore[misc]
                        formatted_code = await f.read()  # type: ignore[misc]
                else:
                    self.console.print(
                        f"[bold bright_yellow]⚠️  Warning: Ruff format failed with return code {proc.returncode}[/bold bright_yellow]"
                    )
                    if stderr:
                        self.console.print(f"[dim]Ruff stderr: {stderr.decode()}[/dim]")
                    formatted_code = code
            except Exception as e:
                self.console.print(
                    f"[bold bright_red]❌ Error running Ruff: {e}[/bold bright_red]"
                )
                handle_error(
                    ExecutionError(
                        message="Error running Ruff",
                        error_code=ErrorCode.FORMATTING_ERROR,
                        details=str(e),
                        recovery="Verify Ruff is installed and configured correctly",
                    ),
                    console=self.console,
                    exit_on_error=False,
                )
                formatted_code = code
            finally:
                with suppress(FileNotFoundError):
                    temp_path.unlink()

            return formatted_code
        except Exception as e:
            self.console.print(
                f"[bold bright_red]❌ Error during reformatting: {e}[/bold bright_red]"
            )
            handle_error(
                ExecutionError(
                    message="Error during reformatting",
                    error_code=ErrorCode.FORMATTING_ERROR,
                    details=str(e),
                    recovery="Check file permissions and disk space",
                ),
                console=self.console,
                exit_on_error=False,
            )
            return code

    async def _cleanup_cache_directories_async(self, pkg_dir: Path) -> None:
        def cleanup_sync() -> None:
            with suppress(PermissionError, OSError):
                pycache_dir = pkg_dir / "__pycache__"
                if pycache_dir.exists():
                    for cache_file in pycache_dir.iterdir():
                        with suppress(PermissionError, OSError):
                            cache_file.unlink()
                    pycache_dir.rmdir()
                parent_pycache = pkg_dir.parent / "__pycache__"
                if parent_pycache.exists():
                    for cache_file in parent_pycache.iterdir():
                        with suppress(PermissionError, OSError):
                            cache_file.unlink()
                    parent_pycache.rmdir()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cleanup_sync)
